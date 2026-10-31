"""Importação do histórico exportado do Mobills (Excel).

Uso (na pasta backend, com o venv ativo):
    python -m app.importacao.mobills ARQUIVO.xlsx --simular   # não grava nada, só relata
    python -m app.importacao.mobills ARQUIVO.xlsx             # grava (faz backup antes)

Como funciona:
  * Aba "Receitas e Despesas": valor negativo = despesa, positivo = receita.
  * Aba "Transferências": vira transferência com as duas pernas.
  * Tag "ignorar transação" -> ignorar=1 (mexe no saldo, fica fora dos relatórios).
  * "(2/12)" na descrição -> parcela 2 de 12.
  * Categorias passam pelo mapa mobills_mapa.json; "projetos" viram tags.
  * Cada linha ganha um origem_id estável (hash do conteúdo), então rodar de novo
    com um Excel mais novo só acrescenta o que ainda não existe.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from .. import db, seed
from ..services import transacoes as svc
from ..services.transacoes import NovaTransacao

ORIGEM = "mobills"
MAPA_PADRAO = Path(__file__).with_name("mobills_mapa.json")
ABA_MOVIMENTOS = "Receitas e Despesas"
ABA_TRANSFERENCIAS = "Transferências"
RE_PARCELA = re.compile(r"\(\s*(\d{1,3})\s*/\s*(\d{1,3})\s*\)")


# --------------------------------------------------------------------------- leitura
@dataclass
class Linha:
    aba: str
    numero: int                 # linha no Excel (para mensagens)
    data: date
    descricao: str
    valor_centavos: int         # com sinal (despesa < 0); transferência sempre > 0
    conta: str
    conta_destino: str | None = None
    categoria: str | None = None
    subcategoria: str | None = None
    tags: list[str] = field(default_factory=list)
    origem_id: str = ""


def _texto(v) -> str:
    return "" if v is None else str(v).strip()


def _data(v) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    t = _texto(v)
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", t)
    return date(int(m[3]), int(m[2]), int(m[1])) if m else None


def _centavos(v) -> int | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return round(float(v) * 100)
    t = _texto(v).replace("R$", "").replace(".", "").replace(",", ".").strip()
    try:
        return round(float(t) * 100)
    except ValueError:
        return None


def _tags(v) -> list[str]:
    return [t.strip() for t in re.split(r"[;,]", _texto(v)) if t.strip()]


def _cabecalho(ws) -> dict[str, int]:
    primeira = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
    return {_texto(n).lower(): i for i, n in enumerate(primeira) if _texto(n)}


def _carimbar(linhas: list[Linha]) -> None:
    """origem_id = hash do conteúdo + nº da ocorrência (linhas idênticas são legítimas)."""
    vistos: Counter[str] = Counter()
    for ln in linhas:
        chave = "|".join([ln.aba, ln.data.isoformat(), ln.descricao.lower(),
                          str(ln.valor_centavos), ln.conta.lower(),
                          (ln.conta_destino or "").lower()])
        vistos[chave] += 1
        ln.origem_id = hashlib.sha1(f"{chave}#{vistos[chave]}".encode()).hexdigest()[:20]


def ler(arquivo: Path) -> tuple[list[Linha], list[str]]:
    """Lê as duas abas. Devolve as linhas válidas e avisos sobre as descartadas."""
    from openpyxl import load_workbook

    wb = load_workbook(arquivo, read_only=True, data_only=True)
    linhas: list[Linha] = []
    avisos: list[str] = []

    if ABA_MOVIMENTOS not in wb.sheetnames:
        raise ValueError(f"Aba '{ABA_MOVIMENTOS}' não encontrada. Abas: {wb.sheetnames}")
    ws = wb[ABA_MOVIMENTOS]
    col = _cabecalho(ws)
    faltando = {"data", "descrição", "valor", "conta"} - col.keys()
    if faltando:
        raise ValueError(f"Colunas ausentes em '{ABA_MOVIMENTOS}': {sorted(faltando)}")
    pega = lambda r, nome: r[col[nome]] if nome in col and col[nome] < len(r) else None  # noqa: E731
    for n, r in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        d = _data(pega(r, "data"))
        if d is None:
            if any(c not in (None, "") for c in r):
                avisos.append(f"{ABA_MOVIMENTOS} linha {n}: sem data válida, ignorada "
                              f"({_texto(pega(r, 'data'))[:30]!r})")
            continue
        valor = _centavos(pega(r, "valor"))
        if not valor:
            avisos.append(f"{ABA_MOVIMENTOS} linha {n}: valor zero ou vazio, ignorada")
            continue
        linhas.append(Linha(
            aba="mov", numero=n, data=d, descricao=_texto(pega(r, "descrição")) or "(sem descrição)",
            valor_centavos=valor, conta=_texto(pega(r, "conta")),
            categoria=_texto(pega(r, "categoria")) or None,
            subcategoria=_texto(pega(r, "subcategoria")) or None,
            tags=_tags(pega(r, "tags")),
        ))

    if ABA_TRANSFERENCIAS in wb.sheetnames:
        ws = wb[ABA_TRANSFERENCIAS]
        col = _cabecalho(ws)
        for n, r in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            d = _data(pega(r, "data"))
            valor = _centavos(pega(r, "valor"))
            if d is None or not valor:
                if d is None and any(c not in (None, "") for c in r) \
                        and not _texto(r[0]).lower().startswith("total"):
                    avisos.append(f"{ABA_TRANSFERENCIAS} linha {n}: sem data válida, ignorada")
                continue
            origem, destino = _texto(pega(r, "conta origem")), _texto(pega(r, "conta destino"))
            linhas.append(Linha(
                aba="transf", numero=n, data=d,
                descricao=f"Transferência {origem} → {destino}",
                valor_centavos=abs(valor), conta=origem, conta_destino=destino,
                tags=_tags(pega(r, "tags")),
            ))
    wb.close()
    _carimbar(linhas)
    return linhas, avisos


def carregar_mapa(arquivo: Path | None = None) -> dict:
    return json.loads((arquivo or MAPA_PADRAO).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- cadastros
class Cadastros:
    """Acha ou cria contas, categorias e tags, sem diferenciar maiúsculas."""

    def __init__(self, con: sqlite3.Connection, mapa: dict, data_inicial: date):
        self.con, self.mapa, self.data_inicial = con, mapa, data_inicial
        self.criados: dict[str, list[str]] = defaultdict(list)
        self._contas: dict[str, int] = {}
        self._tags: dict[str, int] = {}
        self._cats: dict[tuple, int] = {}
        self.viram_tag = {n.lower(): n for n in mapa.get("categorias_viram_tag", [])}

    # Contas -----------------------------------------------------------------
    def conta(self, nome: str) -> int:
        nome = self.mapa.get("contas", {}).get(nome, nome) or "Sem conta"
        chave = nome.lower()
        if chave in self._contas:
            return self._contas[chave]
        r = self.con.execute("SELECT id FROM conta WHERE lower(nome) = ?", (chave,)).fetchone()
        if r is None:
            investimento = any(p.lower() in chave for p in self.mapa.get("contas_investimento", []))
            inst = self._instituicao(nome)
            cid = self.con.execute(
                "INSERT INTO conta (nome, instituicao_id, tipo, saldo_inicial_centavos, "
                "data_saldo_inicial, compoe_saldo_disponivel) VALUES (?, ?, ?, 0, ?, ?)",
                (nome, inst, "investimento" if investimento else "corrente",
                 self.data_inicial.isoformat(), 0 if investimento else 1)).lastrowid
            self.criados["contas"].append(nome)
        else:
            cid = r["id"]
            # Conta já cadastrada com saldo inicial zerado: o histórico passa a contar.
            self.con.execute(
                "UPDATE conta SET data_saldo_inicial = ? WHERE id = ? "
                "AND saldo_inicial_centavos = 0 AND data_saldo_inicial > ?",
                (self.data_inicial.isoformat(), cid, self.data_inicial.isoformat()))
        self._contas[chave] = cid
        return cid

    def _instituicao(self, nome_conta: str) -> int | None:
        for trecho, inst in self.mapa.get("instituicoes", {}).items():
            if trecho.lower() in nome_conta.lower():
                r = self.con.execute("SELECT id FROM instituicao WHERE nome = ?", (inst,)).fetchone()
                if r:
                    return r["id"]
                self.criados["instituições"].append(inst)
                return self.con.execute("INSERT INTO instituicao (nome) VALUES (?)",
                                        (inst,)).lastrowid
        return None

    # Tags -------------------------------------------------------------------
    def tag(self, nome: str) -> int:
        nome = self.viram_tag.get(nome.lower(), nome)
        chave = nome.lower()
        if chave not in self._tags:
            r = self.con.execute("SELECT id FROM tag WHERE lower(nome) = ?", (chave,)).fetchone()
            if r is None:
                self._tags[chave] = self.con.execute("INSERT INTO tag (nome) VALUES (?)",
                                                     (nome,)).lastrowid
                self.criados["tags"].append(nome)
            else:
                self._tags[chave] = r["id"]
        return self._tags[chave]

    # Categorias -------------------------------------------------------------
    def _categoria(self, tipo: str, caminho: str) -> int:
        """'Mãe > Filha' -> id, criando o que faltar."""
        pai = None
        for parte in [p.strip() for p in caminho.split(">") if p.strip()]:
            chave = (tipo, pai, parte.lower())
            if chave not in self._cats:
                r = self.con.execute(
                    "SELECT id FROM categoria WHERE tipo = ? AND pai_id IS ? AND lower(nome) = ?",
                    chave).fetchone()
                if r is None:
                    self._cats[chave] = self.con.execute(
                        "INSERT INTO categoria (nome, tipo, pai_id) VALUES (?, ?, ?)",
                        (parte, tipo, pai)).lastrowid
                    self.criados["categorias"].append(f"{tipo}: {caminho}")
                else:
                    self._cats[chave] = r["id"]
            pai = self._cats[chave]
        return pai

    def _procurar(self, tipo: str, cat: str, sub: str) -> str | None:
        regras = {k.lower(): v for k, v in self.mapa.get(tipo, {}).items()}
        for chave in (f"{cat}|{sub}", f"{cat}|*", f"*|{sub}"):
            if chave.lower() in regras:
                return regras[chave.lower()]
        return None

    def classificar(self, tipo: str, cat: str | None, sub: str | None) -> tuple[int, list[str], str]:
        """Devolve (categoria_id, tags extras, caminho usado)."""
        outras = "Outras despesas" if tipo == "despesa" else "Outras receitas"
        cat, sub = cat or "", sub or ""
        tags: list[str] = []
        if cat.lower() in self.viram_tag:
            tags.append(cat)
            caminho = (self._procurar(tipo, "", sub) if sub else None) or (sub or outras)
        else:
            caminho = self._procurar(tipo, cat, sub)
            if caminho is None:
                caminho = " > ".join(p for p in (cat, sub) if p) or outras
        return self._categoria(tipo, caminho), tags, caminho


# --------------------------------------------------------------------------- importação
@dataclass
class Relatorio:
    linhas_lidas: int = 0
    importadas: int = 0
    ja_existiam: int = 0
    por_tipo: Counter = field(default_factory=Counter)
    ignoradas_relatorio: int = 0
    parceladas: int = 0
    de_para: Counter = field(default_factory=Counter)   # (tipo, 'Cat/Sub', caminho, tag) -> qtd
    criados: dict = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)
    periodo: tuple[str, str] | None = None


def _gravar_origem(con: sqlite3.Connection, ids: list[int], origem_id: str) -> None:
    sufixos = [""] if len(ids) == 1 else [":saida", ":entrada"]
    for tid, suf in zip(ids, sufixos):
        con.execute("UPDATE transacao SET origem = ?, origem_id = ? WHERE id = ?",
                    (ORIGEM, origem_id + suf, tid))


def importar(con: sqlite3.Connection, linhas: list[Linha], mapa: dict) -> Relatorio:
    rel = Relatorio(linhas_lidas=len(linhas))
    if not linhas:
        return rel
    datas = sorted(ln.data for ln in linhas)
    rel.periodo = (datas[0].isoformat(), datas[-1].isoformat())
    cad = Cadastros(con, mapa, datas[0])
    tag_ignorar = mapa.get("tag_ignorar", "ignorar transação").lower()
    existentes = {r[0] for r in con.execute(
        "SELECT origem_id FROM transacao WHERE origem = ?", (ORIGEM,))}

    for ln in linhas:
        if ln.origem_id in existentes or f"{ln.origem_id}:saida" in existentes:
            rel.ja_existiam += 1
            continue
        ignorar = any(t.lower() == tag_ignorar for t in ln.tags)
        nomes_tags = [t for t in ln.tags if t.lower() != tag_ignorar]
        if ln.aba == "transf":
            n = NovaTransacao(tipo="transferencia", descricao=ln.descricao,
                              valor_centavos=ln.valor_centavos, data=ln.data,
                              conta_id=cad.conta(ln.conta),
                              conta_destino_id=cad.conta(ln.conta_destino or ""),
                              ignorar=ignorar)
        else:
            tipo = "despesa" if ln.valor_centavos < 0 else "receita"
            cat_id, extras, caminho = cad.classificar(tipo, ln.categoria, ln.subcategoria)
            nomes_tags += extras
            origem_txt = "/".join(p for p in (ln.categoria, ln.subcategoria) if p) or "(vazia)"
            rel.de_para[(tipo, origem_txt, caminho, ", ".join(extras))] += 1
            n = NovaTransacao(tipo=tipo, descricao=ln.descricao,
                              valor_centavos=abs(ln.valor_centavos), data=ln.data,
                              conta_id=cad.conta(ln.conta), categoria_id=cat_id,
                              ignorar=ignorar)
        n.tags = list(dict.fromkeys(cad.tag(t) for t in nomes_tags))
        ids = svc.criar(con, n)
        with con:
            _gravar_origem(con, ids, ln.origem_id)
            m = RE_PARCELA.search(ln.descricao)
            if m and ln.aba == "mov" and 1 <= int(m[1]) <= int(m[2]) and int(m[2]) > 1:
                con.execute("UPDATE transacao SET parcela = ?, total_parcelas = ? WHERE id = ?",
                            (int(m[1]), int(m[2]), ids[0]))
                rel.parceladas += 1
        rel.importadas += 1
        rel.por_tipo[n.tipo] += 1
        rel.ignoradas_relatorio += int(ignorar)
    con.commit()
    rel.criados = {k: sorted(set(v)) for k, v in cad.criados.items()}
    return rel


# --------------------------------------------------------------------------- conferência
def totais_do_mes(con: sqlite3.Connection, competencia: str, com_ignoradas: bool) -> dict:
    filtro = "" if com_ignoradas else "AND ignorar = 0"
    r = con.execute(f"""
        SELECT COALESCE(SUM(CASE WHEN tipo = 'receita' THEN valor_centavos END), 0) AS receitas,
               COALESCE(SUM(CASE WHEN tipo = 'despesa' THEN valor_centavos END), 0) AS despesas
        FROM transacao WHERE origem = ? AND substr(data, 1, 7) = ? {filtro}""",
                    (ORIGEM, competencia)).fetchone()
    return dict(r)


def _reais(c: int) -> str:
    s = f"{abs(c) / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if c < 0 else "") + "R$ " + s


def texto_relatorio(con: sqlite3.Connection, rel: Relatorio, simulacao: bool) -> str:
    from ..services.painel import saldos_contas

    out = [("SIMULAÇÃO (nada foi gravado)" if simulacao else "IMPORTAÇÃO CONCLUÍDA"), ""]
    if rel.periodo:
        out.append(f"Período: {rel.periodo[0]} a {rel.periodo[1]}")
    out += [f"Linhas lidas: {rel.linhas_lidas}  |  importadas: {rel.importadas}  |  "
            f"já existiam: {rel.ja_existiam}",
            "Por tipo: " + ", ".join(f"{k} {v}" for k, v in rel.por_tipo.most_common()),
            f"Marcadas 'ignorar' (fora dos relatórios): {rel.ignoradas_relatorio}",
            f"Com parcela identificada (n/m): {rel.parceladas}", ""]
    for k, v in rel.criados.items():
        out.append(f"Novos(as) {k} ({len(v)}): " + "; ".join(v))
    out += ["", "DE-PARA DE CATEGORIAS (qtd | tipo | Mobills -> app | tag)"]
    for (tipo, de, para, tag), q in sorted(rel.de_para.items(), key=lambda x: -x[1]):
        out.append(f"{q:5d} | {tipo:7s} | {de} -> {para}" + (f" | tag {tag}" if tag else ""))
    meses = sorted({r[0] for r in con.execute(
        "SELECT DISTINCT substr(data,1,7) FROM transacao WHERE origem = ?", (ORIGEM,))})
    if meses:
        out += ["", "TOTAIS POR MÊS (compare com o Mobills)",
                "mês     | receitas       | despesas       | despesas sem 'ignorar'"]
        for m in meses[-6:]:
            t, s = totais_do_mes(con, m, True), totais_do_mes(con, m, False)
            out.append(f"{m} | {_reais(t['receitas']):>14} | {_reais(t['despesas']):>14} | "
                       f"{_reais(s['despesas']):>14}")
    out += ["", "SALDO POR CONTA (saldo inicial 0; ajuste depois com 'Reajustar saldo')"]
    for c in saldos_contas(con):
        out.append(f"{_reais(c['saldo_atual']):>16}  {c['nome']}")
    if rel.avisos:
        out += ["", f"AVISOS ({len(rel.avisos)}):"] + rel.avisos[:30]
    return "\n".join(out)


def executar(con: sqlite3.Connection, arquivo: Path, mapa: dict | None = None,
             simular: bool = False) -> tuple[Relatorio, str]:
    """Importa (ou simula numa cópia em memória) e devolve o relatório."""
    linhas, avisos = ler(arquivo)
    alvo = con
    if simular:
        alvo = db.conectar(":memory:")
        con.backup(alvo)
    rel = importar(alvo, linhas, mapa or carregar_mapa())
    rel.avisos = avisos
    texto = texto_relatorio(alvo, rel, simular)
    if simular:
        alvo.close()
    return rel, texto


def main(argv: list[str] | None = None) -> int:
    from ..config import carregar
    from ..services import backup

    p = argparse.ArgumentParser(description="Importa o Excel exportado do Mobills.")
    p.add_argument("arquivo", type=Path)
    p.add_argument("--simular", action="store_true", help="não grava; só mostra o relatório")
    p.add_argument("--mapa", type=Path, help="mapa de categorias (padrão: mobills_mapa.json)")
    p.add_argument("--saida", type=Path, help="salva o relatório neste arquivo .txt")
    a = p.parse_args(argv)

    cfg = carregar()
    cfg.pasta_dados.mkdir(parents=True, exist_ok=True)
    con = db.conectar(cfg.arquivo_banco)
    db.migrar(con)
    seed.popular(con)
    if not a.simular:
        destino = backup.fazer(con, cfg.pasta_backup)
        print(f"Backup antes da importação: {destino}")
    _, texto = executar(con, a.arquivo, carregar_mapa(a.mapa), simular=a.simular)
    print(texto)
    if a.saida:
        a.saida.write_text(texto, encoding="utf-8")
        print(f"\nRelatório salvo em {a.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
