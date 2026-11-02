"""Traz as faturas de cartão do Mobills (relatório "RELATORIO_CARTOES_*.xlsx").

No Mobills, cada item da fatura foi lançado como DESPESA DA CONTA no dia do
vencimento. O relatório de transações já trouxe esses itens como despesas das
contas; este script os transforma em compras no cartão, sem duplicar:

  * Item que já existe como despesa da conta (mesma descrição, valor, data e conta)
    -> vira compra no cartão, na fatura do mês do vencimento (mês da data).
  * Para cada (cartão, conta, data) convertido e pago -> um PAGAMENTO DE FATURA
    com a soma dos itens. O saldo das contas não muda nem um centavo.
  * Item que ainda não existe e está "Pendente" (parcelas futuras) -> compra nova
    no cartão, na fatura do mês da data. Pula se já houver na mesma fatura uma
    compra de mesmo valor lançada no app (ex.: cupom).
  * Item "Pago" que não está no banco -> só aparece no relatório.

Uso (pasta backend, venv ativo):
    python -m app.importacao.mobills_cartoes ARQUIVO.xlsx --simular
    python -m app.importacao.mobills_cartoes ARQUIVO.xlsx
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from .. import db, seed
from ..services import painel
from ..services import transacoes as svc
from ..services.fatura_cartao import fatura_por_competencia
from .mobills import RE_PARCELA, Cadastros, _cabecalho, _centavos, _data, _reais, _tags, _texto, carregar_mapa

ORIGEM = "mobills_cartoes"


@dataclass
class Item:
    numero: int
    data: date
    descricao: str
    valor_centavos: int          # positivo
    conta: str
    pago: bool
    categoria: str | None
    subcategoria: str | None
    tags: list[str]
    origem_id: str = ""


def ler(arquivo: Path) -> list[Item]:
    from openpyxl import load_workbook

    wb = load_workbook(arquivo, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    col = _cabecalho(ws)
    faltando = {"data", "descrição", "valor", "conta"} - col.keys()
    if faltando:
        raise ValueError(f"Colunas ausentes: {sorted(faltando)}")
    pega = lambda r, nome: r[col[nome]] if nome in col and col[nome] < len(r) else None  # noqa: E731
    itens: list[Item] = []
    vistos: Counter[str] = Counter()
    for n, r in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        d, valor = _data(pega(r, "data")), _centavos(pega(r, "valor"))
        if d is None or not valor or not _texto(pega(r, "conta")):
            continue
        it = Item(numero=n, data=d, descricao=_texto(pega(r, "descrição")) or "(sem descrição)",
                  valor_centavos=abs(valor), conta=_texto(pega(r, "conta")),
                  pago=_texto(pega(r, "situação")).lower() != "pendente",
                  categoria=_texto(pega(r, "categoria")) or None,
                  subcategoria=_texto(pega(r, "subcategoria")) or None,
                  tags=_tags(pega(r, "tags")))
        chave = "|".join([d.isoformat(), it.descricao.lower(), str(it.valor_centavos), it.conta.lower()])
        vistos[chave] += 1
        it.origem_id = hashlib.sha1(f"{chave}#{vistos[chave]}".encode()).hexdigest()[:20]
        itens.append(it)
    wb.close()
    return itens


@dataclass
class Relatorio:
    lidos: int = 0
    convertidos: Counter = field(default_factory=Counter)        # por cartão
    novos: Counter = field(default_factory=Counter)
    ja_estavam: int = 0
    duplicatas: list[str] = field(default_factory=list)
    sem_cartao: Counter = field(default_factory=Counter)          # por conta
    pagos_nao_encontrados: list[str] = field(default_factory=list)
    pagamentos: list[str] = field(default_factory=list)
    saldos_antes: dict = field(default_factory=dict)
    saldos_depois: dict = field(default_factory=dict)
    faturas: dict = field(default_factory=dict)                   # (cartão, AAAA-MM) -> total


def _contas(con, mapa) -> dict[str, int]:
    renomes = {k.lower(): v for k, v in mapa.get("contas", {}).items()}
    por_nome = {r["nome"].lower(): r["id"] for r in con.execute("SELECT id, nome FROM conta")}
    return {**por_nome, **{k: por_nome[v.lower()] for k, v in renomes.items() if v and v.lower() in por_nome}}


def _cartao_da_conta(con, conta_nome: str, conta_id: int | None, mapa: dict) -> int | None:
    """Cartão pelo mapa, pelos 4 dígitos no nome da conta, ou o único pago por ela."""
    nome = mapa.get("cartoes_por_conta", {}).get(conta_nome)
    if nome:
        r = con.execute("SELECT id FROM cartao WHERE lower(nome) = lower(?)", (nome,)).fetchone()
        return r["id"] if r else None
    for final in re.findall(r"\b(\d{4})\b", conta_nome):
        r = con.execute("SELECT id FROM cartao WHERE final = ? AND ativo = 1", (final,)).fetchall()
        if len(r) == 1:
            return r[0]["id"]
    if conta_id:
        r = con.execute("SELECT id FROM cartao WHERE conta_pagamento_id = ? AND ativo = 1",
                        (conta_id,)).fetchall()
        if len(r) == 1:
            return r[0]["id"]
    return None


def importar(con: sqlite3.Connection, itens: list[Item], mapa: dict) -> Relatorio:
    rel = Relatorio(lidos=len(itens))
    rel.saldos_antes = {s["nome"]: s["saldo_atual"] for s in painel.saldos_contas(con)}
    contas = _contas(con, mapa)
    cad = Cadastros(con, mapa, date(2026, 1, 1))
    tag_ignorar = mapa.get("tag_ignorar", "ignorar transação").lower()
    novos_ja = {r[0] for r in con.execute("SELECT origem_id FROM transacao WHERE origem = ?", (ORIGEM,))}
    usados: set[int] = set()
    a_pagar: dict[tuple, int] = defaultdict(int)     # (cartão, conta, data) -> centavos

    for it in itens:
        conta_id = contas.get(it.conta.lower())
        cartao = _cartao_da_conta(con, it.conta, conta_id, mapa)
        if cartao is None:
            rel.sem_cartao[it.conta] += 1
            continue
        comp = f"{it.data:%Y-%m}"
        # 1) Já está no app como despesa da conta -> converte.
        r = con.execute(
            """SELECT id, pago FROM transacao WHERE tipo = 'despesa' AND trim(descricao) = ?
               AND valor_centavos = ? AND data = ? AND conta_id = ? ORDER BY id""",
            (it.descricao, it.valor_centavos, it.data.isoformat(), conta_id)).fetchall()
        r = [x for x in r if x["id"] not in usados]
        if r:
            tid = r[0]["id"]
            usados.add(tid)
            fatura = fatura_por_competencia(con, cartao, comp)
            con.execute("""UPDATE transacao SET tipo = 'despesa_cartao', conta_id = NULL, cartao_id = ?,
                           fatura_id = ? WHERE id = ?""", (cartao, fatura, tid))
            if r[0]["pago"]:
                a_pagar[(cartao, conta_id, it.data.isoformat())] += it.valor_centavos
            rel.convertidos[cartao] += 1
            continue
        # 2) Já convertido numa rodada anterior, ou já importado como novo.
        if it.origem_id in novos_ja or con.execute(
                """SELECT 1 FROM transacao WHERE tipo = 'despesa_cartao' AND trim(descricao) = ?
                   AND valor_centavos = ? AND data = ? AND cartao_id = ?""",
                (it.descricao, it.valor_centavos, it.data.isoformat(), cartao)).fetchone():
            rel.ja_estavam += 1
            continue
        if it.pago:
            rel.pagos_nao_encontrados.append(f"{it.data:%d/%m/%Y} {_reais(it.valor_centavos):>12}  "
                                             f"{it.conta} | {it.descricao}")
            continue
        # 3) Parcela futura: compra nova, salvo se a fatura já tem compra de mesmo valor.
        fatura = fatura_por_competencia(con, cartao, comp)
        # Só compara com o que foi lançado no próprio app (cupom, tela da fatura): parcelas
        # iguais vindas do Mobills são legítimas.
        dup = con.execute("""SELECT descricao FROM transacao WHERE tipo = 'despesa_cartao'
                             AND fatura_id = ? AND valor_centavos = ? AND origem IS NULL""",
                          (fatura, it.valor_centavos)).fetchone()
        if dup:
            rel.duplicatas.append(f"{it.data:%d/%m/%Y} {_reais(it.valor_centavos):>12}  {it.descricao} "
                                  f"= já lançado como \"{dup['descricao']}\"")
            continue
        ignorar = any(t.lower() == tag_ignorar for t in it.tags)
        cat_id, extras, _ = cad.classificar("despesa", it.categoria, it.subcategoria)
        nomes = [t for t in it.tags if t.lower() != tag_ignorar] + extras
        n = svc.NovaTransacao(tipo="despesa_cartao", descricao=it.descricao,
                              valor_centavos=it.valor_centavos, data=it.data, cartao_id=cartao,
                              fatura_competencia=comp, categoria_id=cat_id, ignorar=ignorar)
        n.tags = list(dict.fromkeys(cad.tag(t) for t in nomes))
        ids = svc.criar(con, n)
        con.execute("UPDATE transacao SET origem = ?, origem_id = ? WHERE id = ?", (ORIGEM, it.origem_id, ids[0]))
        m = RE_PARCELA.search(it.descricao)
        if m and 1 <= int(m[1]) <= int(m[2]) and int(m[2]) > 1:
            con.execute("UPDATE transacao SET parcela = ?, total_parcelas = ? WHERE id = ?",
                        (int(m[1]), int(m[2]), ids[0]))
        rel.novos[cartao] += 1

    # 4) Pagamentos: o dinheiro que já saiu das contas agora paga a fatura.
    nomes_cartao = {r["id"]: r["nome"] for r in con.execute("SELECT id, nome FROM cartao")}
    for (cartao, conta_id, dia), valor in sorted(a_pagar.items(), key=lambda x: x[0][2]):
        oid = f"pag|{cartao}|{conta_id}|{dia}"
        existe = con.execute("SELECT id FROM transacao WHERE origem = ? AND origem_id = ?", (ORIGEM, oid)).fetchone()
        if existe:
            con.execute("UPDATE transacao SET valor_centavos = valor_centavos + ? WHERE id = ?", (valor, existe["id"]))
        else:
            ids = svc.criar(con, svc.NovaTransacao(
                tipo="pagamento_fatura", descricao=f"Fatura {nomes_cartao[cartao]}", valor_centavos=valor,
                data=date.fromisoformat(dia), conta_id=conta_id, cartao_id=cartao, fatura_competencia=dia[:7]))
            con.execute("UPDATE transacao SET origem = ?, origem_id = ? WHERE id = ?", (ORIGEM, oid, ids[0]))
        rel.pagamentos.append(f"{date.fromisoformat(dia):%d/%m/%Y} {_reais(valor):>12}  {nomes_cartao[cartao]}")
    con.commit()

    rel.saldos_depois = {s["nome"]: s["saldo_atual"] for s in painel.saldos_contas(con)}
    for r in con.execute("""SELECT ca.nome, f.competencia,
               SUM(CASE WHEN t.tipo = 'credito_cartao' THEN -t.valor_centavos ELSE t.valor_centavos END) AS total
               FROM fatura f JOIN cartao ca ON ca.id = f.cartao_id
               JOIN transacao t ON t.fatura_id = f.id AND t.tipo IN ('despesa_cartao', 'credito_cartao')
               GROUP BY 1, 2 ORDER BY 1, 2"""):
        rel.faturas[(r["nome"], r["competencia"])] = r["total"]
    rel.nomes_cartao = nomes_cartao
    return rel


def texto_relatorio(rel: Relatorio, simulacao: bool) -> str:
    nc = rel.nomes_cartao
    s = ["SIMULAÇÃO: nada foi gravado." if simulacao else "IMPORTAÇÃO GRAVADA.", "",
         f"Linhas lidas: {rel.lidos}",
         f"Convertidas de despesa da conta para compra no cartão: {sum(rel.convertidos.values())}"]
    s += [f"   {nc[k]}: {v}" for k, v in rel.convertidos.items()]
    s += [f"Compras novas (parcelas futuras): {sum(rel.novos.values())}"]
    s += [f"   {nc[k]}: {v}" for k, v in rel.novos.items()]
    s += [f"Já estavam nos cartões (rodada anterior): {rel.ja_estavam}",
          f"Pagamentos de fatura criados: {len(rel.pagamentos)}"]
    if rel.sem_cartao:
        s += ["", "SEM CARTÃO CADASTRADO (continuam como despesa da conta, nada mudou):"]
        s += [f"   {k}: {v} linhas" for k, v in rel.sem_cartao.items()]
    if rel.duplicatas:
        s += ["", "PULADAS por já existir compra de mesmo valor na fatura:"] + [f"   {x}" for x in rel.duplicatas]
    if rel.pagos_nao_encontrados:
        s += ["", "PAGAS NO MOBILLS MAS NÃO ENCONTRADAS NO APP (não importadas):"]
        s += [f"   {x}" for x in rel.pagos_nao_encontrados]
    s += ["", "SALDO DAS CONTAS (antes -> depois):"]
    iguais = True
    for nome, antes in rel.saldos_antes.items():
        depois = rel.saldos_depois.get(nome)
        ok = antes == depois
        iguais &= ok
        s.append(f"   {'OK ' if ok else '!! '}{nome:<45} {_reais(antes):>14} -> {_reais(depois or 0):>14}")
    s.append("   Todos os saldos ficaram iguais." if iguais else "   ATENÇÃO: algum saldo mudou.")
    s += ["", "FATURAS POR CARTÃO (mês do vencimento: total):"]
    atual = None
    for (cartao, comp), total in rel.faturas.items():
        if cartao != atual:
            s.append(f"   {cartao}")
            atual = cartao
        s.append(f"      {comp}: {_reais(total):>12}")
    return "\n".join(s)


def executar(con: sqlite3.Connection, arquivo: Path, mapa: dict | None = None,
             simular: bool = False) -> tuple[Relatorio, str]:
    itens = ler(arquivo)
    alvo = con
    if simular:
        alvo = db.conectar(":memory:")
        con.backup(alvo)
    rel = importar(alvo, itens, mapa or carregar_mapa())
    texto = texto_relatorio(rel, simular)
    if simular:
        alvo.close()
    return rel, texto


def main(argv: list[str] | None = None) -> int:
    from ..config import carregar
    from ..services import backup

    p = argparse.ArgumentParser(description="Traz as faturas de cartão do Mobills.")
    p.add_argument("arquivo", type=Path)
    p.add_argument("--simular", action="store_true")
    p.add_argument("--saida", type=Path)
    a = p.parse_args(argv)
    cfg = carregar()
    con = db.conectar(cfg.arquivo_banco)
    db.migrar(con)
    seed.popular(con)
    if not a.simular:
        print(f"Backup antes da importação: {backup.fazer(con, cfg.pasta_backup)}")
    _, texto = executar(con, a.arquivo, simular=a.simular)
    print(texto)
    if a.saida:
        a.saida.write_text(texto, encoding="utf-8")
        print(f"\nRelatório salvo em {a.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
