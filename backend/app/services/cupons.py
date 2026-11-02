"""Cupons: leitura da página da SEFAZ salva (Ctrl+S) e lançamento com itens.

Formato comum de um "cupom lido" (vale também para o arquivo .json que o
Claude gera ao ler a foto de um pedido sem QR):

    {
      "origem": "sefaz" | "foto",
      "tipo_documento": "nfce" | "pedido" | "outro",
      "chave": "44 dígitos" | null,
      "emitente": {"nome": "...", "cnpj": "só dígitos" | null, "cidade": "...", "uf": "ES"},
      "numero": "379430", "serie": "13", "emissao": "2026-10-21T16:45:12",
      "itens": [{"descricao": "PAO FRANCES KG", "codigo": "4", "quantidade_milesimos": 172,
                 "unidade": "KG", "preco_unitario_centavos": 2390,
                 "valor_total_centavos": 411, "desconto_centavos": 0}],
      "valor_total_centavos": 2917,   # soma bruta dos itens
      "desconto_centavos": 0,
      "valor_pagar_centavos": 2917
    }
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from datetime import date, datetime
from decimal import Decimal

from . import transacoes as svc
from .transacoes import NovaTransacao, RegraViolada


class CupomInvalido(ValueError):
    """O arquivo não é uma página de NFC-e reconhecível."""


# --------------------------------------------------------------------------- números
def _decimal_br(texto: str) -> Decimal:
    t = (texto or "").replace("\xa0", " ").strip()
    t = re.sub(r"[^\d,.\-]", "", t)
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    return Decimal(t or "0")


def _centavos(texto: str) -> int:
    return int((_decimal_br(texto) * 100).quantize(Decimal("1")))


def _milesimos(texto: str) -> int:
    return int((_decimal_br(texto) * 1000).quantize(Decimal("1")))


def _limpo(texto: str | None) -> str:
    return re.sub(r"\s+", " ", (texto or "").replace("\xa0", " ")).strip()


# --------------------------------------------------------------------------- SEFAZ
def ler_sefaz_html(html: str | bytes) -> dict:
    """Extrai a nota da página de consulta pública da NFC-e (layout nacional do DANFE).

    Testado com a SEFAZ-ES; outros estados que usam o mesmo layout
    (tabela #tabResult, spans txtTit/Rqtd/RUN/RvlUnit) também funcionam.
    """
    from bs4 import BeautifulSoup

    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")
    sopa = BeautifulSoup(html, "html.parser")
    tabela = sopa.find(id="tabResult")
    if tabela is None:
        if "captcha" in html.lower() or "turnstile" in html.lower():
            raise CupomInvalido("A página foi salva antes de resolver o captcha: "
                                "resolva e salve de novo quando a lista de itens aparecer.")
        raise CupomInvalido("Não encontrei a lista de itens. Salve a página da SEFAZ "
                            "com Ctrl+S quando os itens estiverem na tela.")

    itens = []
    for seq, tr in enumerate(tabela.find_all("tr"), start=1):
        nome = tr.find(class_="txtTit")
        if nome is None:
            continue
        def campo(cls: str) -> str:
            el = tr.find(class_=cls)
            if el is None:
                return ""
            forte = el.find("strong")
            if forte:
                forte.extract()
            return _limpo(el.get_text())
        cod = re.search(r"C[óo]digo:\s*([^\s)]+)", campo("RCod") or "")
        valor = tr.find(class_="valor")
        itens.append({
            "seq": seq,
            "descricao": _limpo(nome.get_text()),
            "codigo": cod.group(1) if cod else None,
            "quantidade_milesimos": _milesimos(campo("Rqtd")) or 1000,
            "unidade": campo("RUN").upper() or "UN",
            "preco_unitario_centavos": _centavos(campo("RvlUnit")),
            "valor_total_centavos": _centavos(valor.get_text() if valor else "0"),
            "desconto_centavos": 0,
        })
    if not itens:
        raise CupomInvalido("A lista de itens está vazia.")

    # Totais: cada linha é "rótulo: valor".
    totais: dict[str, str] = {}
    caixa = sopa.find(id="totalNota")
    if caixa is not None:
        for linha in caixa.find_all(id=re.compile("linhaTotal")):
            rot, val = linha.find("label"), linha.find(class_="totalNumb")
            if rot and val:
                totais[_limpo(rot.get_text()).lower()] = _limpo(val.get_text())

    def total(*rotulos: str) -> int | None:
        for chave, val in totais.items():
            if any(r in chave for r in rotulos) and re.search(r"\d", val):
                return _centavos(val)
        return None

    bruto = sum(i["valor_total_centavos"] for i in itens)
    desconto = total("desconto") or 0
    pagar = total("valor a pagar") or (total("valor total") or bruto) - desconto
    _ratear_desconto(itens, desconto)

    # Emitente e dados gerais.
    topo = sopa.find(class_="txtCenter")
    textos = [_limpo(d.get_text()) for d in topo.find_all("div", class_="text")] if topo else []
    nome_emit = _limpo(sopa.find(class_="txtTopo").get_text()) if sopa.find(class_="txtTopo") else ""
    cnpj = next((re.sub(r"\D", "", t) for t in textos if "CNPJ" in t.upper()), None)
    endereco = next((t for t in textos if "CNPJ" not in t.upper()), "")
    partes = [p.strip() for p in endereco.split(",") if p.strip()]
    infos = _limpo(sopa.find(id="infos").get_text(" ")) if sopa.find(id="infos") else _limpo(sopa.get_text(" "))
    num = re.search(r"N[úu]mero:\s*(\d+)", infos)
    serie = re.search(r"S[ée]rie:\s*(\d+)", infos)
    emis = re.search(r"Emiss[ãa]o:\s*(\d{2})/(\d{2})/(\d{4})\s+(\d{2}:\d{2}:\d{2})", infos)
    chave = re.search(r"Chave de acesso:\s*([\d ]{44,60})", infos)

    return {
        "origem": "sefaz",
        "tipo_documento": "nfce",
        "chave": re.sub(r"\D", "", chave.group(1))[:44] if chave else None,
        "emitente": {"nome": nome_emit, "cnpj": cnpj or None,
                     "cidade": partes[-2] if len(partes) >= 2 else None,
                     "uf": partes[-1] if partes else None},
        "numero": num.group(1) if num else None,
        "serie": serie.group(1) if serie else None,
        "emissao": (f"{emis[3]}-{emis[2]}-{emis[1]}T{emis[4]}" if emis else None),
        "itens": itens,
        "valor_total_centavos": bruto,
        "desconto_centavos": desconto,
        "valor_pagar_centavos": pagar,
    }


def _ratear_desconto(itens: list[dict], desconto: int) -> None:
    """Desconto só no total: distribui proporcionalmente (centavos que sobram no maior item)."""
    if desconto <= 0 or any(i.get("desconto_centavos") for i in itens):
        return
    bruto = sum(i["valor_total_centavos"] for i in itens) or 1
    for i in itens:
        i["desconto_centavos"] = desconto * i["valor_total_centavos"] // bruto
    sobra = desconto - sum(i["desconto_centavos"] for i in itens)
    max(itens, key=lambda i: i["valor_total_centavos"])["desconto_centavos"] += sobra


def normalizar_json(dados: dict) -> dict:
    """Valida um cupom vindo de .json (pedido lido da foto) e completa campos."""
    if not isinstance(dados, dict) or not dados.get("itens"):
        raise CupomInvalido("O arquivo .json precisa ter a lista 'itens'.")
    itens = []
    for seq, i in enumerate(dados["itens"], start=1):
        try:
            itens.append({
                "seq": seq, "descricao": _limpo(i["descricao"]), "codigo": i.get("codigo"),
                "quantidade_milesimos": int(i.get("quantidade_milesimos") or 1000),
                "unidade": (i.get("unidade") or "UN").upper(),
                "preco_unitario_centavos": int(i.get("preco_unitario_centavos") or 0),
                "valor_total_centavos": int(i["valor_total_centavos"]),
                "desconto_centavos": int(i.get("desconto_centavos") or 0),
            })
        except (KeyError, TypeError, ValueError) as e:
            raise CupomInvalido(f"Item {seq} incompleto: {e}") from e
    bruto = sum(i["valor_total_centavos"] for i in itens)
    desconto = int(dados.get("desconto_centavos") or 0)
    _ratear_desconto(itens, desconto)
    emit = dados.get("emitente") or {}
    return {
        "origem": dados.get("origem") or "foto",
        "tipo_documento": dados.get("tipo_documento") or "pedido",
        "chave": dados.get("chave"),
        "emitente": {"nome": emit.get("nome") or "", "cnpj": re.sub(r"\D", "", emit.get("cnpj") or "") or None,
                     "cidade": emit.get("cidade"), "uf": emit.get("uf")},
        "numero": dados.get("numero"), "serie": dados.get("serie"), "emissao": dados.get("emissao"),
        "itens": itens,
        "valor_total_centavos": bruto,
        "desconto_centavos": sum(i["desconto_centavos"] for i in itens),
        "valor_pagar_centavos": int(dados.get("valor_pagar_centavos")
                                    or bruto - sum(i["desconto_centavos"] for i in itens)),
    }


def ler_arquivo(nome: str, conteudo: bytes) -> dict:
    if nome.lower().endswith(".json"):
        try:
            return normalizar_json(json.loads(conteudo.decode("utf-8")))
        except json.JSONDecodeError as e:
            raise CupomInvalido(f"JSON inválido: {e}") from e
    return ler_sefaz_html(conteudo)


# --------------------------------------------------------------------------- conferência
def conferir(cupom: dict) -> dict:
    """Controle de qualidade: itens − descontos devem bater com o valor a pagar."""
    liquido = sum(i["valor_total_centavos"] - i["desconto_centavos"] for i in cupom["itens"])
    diferenca = cupom["valor_pagar_centavos"] - liquido
    return {"liquido_itens": liquido, "valor_pagar": cupom["valor_pagar_centavos"],
            "diferenca": diferenca, "confere": diferenca == 0}


def ja_lancado(con: sqlite3.Connection, cupom: dict) -> dict | None:
    if not cupom.get("chave"):
        return None
    r = con.execute("""SELECT d.id, d.status, t.id AS transacao_id, t.data FROM documento d
                       LEFT JOIN transacao t ON t.documento_id = d.id
                       WHERE d.chave_nfce = ?""", (cupom["chave"],)).fetchone()
    return dict(r) if r else None


def sugerir_categorias(con: sqlite3.Connection, cupom: dict) -> None:
    """Preenche categoria_sugerida em cada item, aprendendo com os lançamentos anteriores.

    Ordem: mesmo código na mesma loja → mesma descrição em qualquer loja →
    categoria mais usada nessa loja → vazio (você escolhe na revisão).
    """
    cnpj = (cupom.get("emitente") or {}).get("cnpj")
    loja = con.execute("SELECT id FROM estabelecimento WHERE cnpj = ?", (cnpj,)).fetchone() if cnpj else None
    padrao_loja = None
    if loja:
        r = con.execute("""SELECT i.categoria_id, COUNT(*) n FROM item i JOIN transacao t ON t.id = i.transacao_id
                           WHERE t.estabelecimento_id = ? AND i.categoria_id IS NOT NULL
                           GROUP BY 1 ORDER BY n DESC LIMIT 1""", (loja["id"],)).fetchone() \
            or con.execute("""SELECT categoria_id, COUNT(*) n FROM transacao WHERE estabelecimento_id = ?
                              AND categoria_id IS NOT NULL GROUP BY 1 ORDER BY n DESC LIMIT 1""",
                           (loja["id"],)).fetchone()
        padrao_loja = r[0] if r else None
    for i in cupom["itens"]:
        sug = None
        if loja and i.get("codigo"):
            r = con.execute("""SELECT i.categoria_id FROM item i JOIN transacao t ON t.id = i.transacao_id
                               WHERE t.estabelecimento_id = ? AND i.codigo = ? AND i.categoria_id IS NOT NULL
                               ORDER BY i.id DESC LIMIT 1""", (loja["id"], i["codigo"])).fetchone()
            sug = r[0] if r else None
        if sug is None:
            r = con.execute("""SELECT categoria_id FROM item WHERE upper(descricao_lida) = upper(?)
                               AND categoria_id IS NOT NULL ORDER BY id DESC LIMIT 1""",
                            (i["descricao"],)).fetchone()
            sug = r[0] if r else None
        i["categoria_sugerida"] = sug or padrao_loja


def preparar(con: sqlite3.Connection, cupom: dict) -> dict:
    """O que a tela de revisão recebe: cupom + conferência + duplicidade + sugestões."""
    sugerir_categorias(con, cupom)
    return {"cupom": cupom, "conferencia": conferir(cupom), "ja_lancado": ja_lancado(con, cupom)}


# --------------------------------------------------------------------------- lançamento
def _estabelecimento(con: sqlite3.Connection, emit: dict) -> int | None:
    nome = _limpo(emit.get("nome"))
    if not nome:
        return None
    cnpj = emit.get("cnpj")
    if cnpj:
        r = con.execute("SELECT id FROM estabelecimento WHERE cnpj = ?", (cnpj,)).fetchone()
    else:
        r = con.execute("SELECT id FROM estabelecimento WHERE cnpj IS NULL AND upper(nome) = upper(?)",
                        (nome,)).fetchone()
    if r:
        return r["id"]
    return con.execute("INSERT INTO estabelecimento (cnpj, nome, cidade, uf) VALUES (?, ?, ?, ?)",
                       (cnpj, nome, emit.get("cidade"), emit.get("uf"))).lastrowid


def lancar(con: sqlite3.Connection, cupom: dict, *, conta_id: int | None = None,
           cartao_id: int | None = None, data: date | None = None, descricao: str | None = None,
           categorias: dict[int, int] | None = None, arquivo: str = "") -> dict:
    """Grava documento + transação (despesa ou despesa_cartao) + itens com categoria.

    categorias: {seq do item: categoria_id}. Item sem categoria fica com a categoria
    mais frequente da compra.
    """
    if bool(conta_id) == bool(cartao_id):
        raise RegraViolada("Escolha uma conta OU um cartão para pagar o cupom")
    if ja_lancado(con, cupom):
        raise RegraViolada("Este cupom já foi lançado (mesma chave de acesso)")
    categorias = categorias or {}
    itens = cupom["itens"]
    for i in itens:
        i["categoria_id"] = categorias.get(i["seq"]) or i.get("categoria_sugerida")
    # Mesmo produto repetido no cupom (ex.: dois pacotes pesados) herda a categoria do irmão.
    por_produto = {(i.get("codigo") or i["descricao"]): i["categoria_id"] for i in itens if i["categoria_id"]}
    for i in itens:
        i["categoria_id"] = i["categoria_id"] or por_produto.get(i.get("codigo") or i["descricao"])
    usadas = Counter(i["categoria_id"] for i in itens if i["categoria_id"])
    principal = usadas.most_common(1)[0][0] if usadas else None
    for i in itens:
        i["categoria_id"] = i["categoria_id"] or principal
    if principal is None:
        raise RegraViolada("Escolha a categoria de pelo menos um item")

    valor = sum(i["valor_total_centavos"] - i["desconto_centavos"] for i in itens)
    if valor <= 0:
        raise RegraViolada("O valor líquido do cupom precisa ser maior que zero")
    if data is None:
        data = (datetime.fromisoformat(cupom["emissao"]).date() if cupom.get("emissao") else date.today())
    emit = cupom.get("emitente") or {}

    with con:
        loja = _estabelecimento(con, emit)
        doc = con.execute(
            "INSERT INTO documento (tipo, arquivo, chave_nfce, estabelecimento_id, data_emissao, "
            "valor_total_centavos, status, leitura_json) VALUES (?, ?, ?, ?, ?, ?, 'lancado', ?)",
            (cupom.get("tipo_documento") or "outro", arquivo or "(sem arquivo)", cupom.get("chave"),
             loja, cupom.get("emissao"), valor, json.dumps(cupom, ensure_ascii=False))).lastrowid
    ids = svc.criar(con, NovaTransacao(
        tipo="despesa_cartao" if cartao_id else "despesa",
        descricao=descricao or _limpo(emit.get("nome")) or "Cupom",
        valor_centavos=valor, data=data, conta_id=conta_id, cartao_id=cartao_id,
        categoria_id=principal if len(usadas) <= 1 else None,
        estabelecimento_id=loja, documento_id=doc))
    with con:
        con.executemany(
            "INSERT INTO item (transacao_id, documento_id, seq, codigo, descricao_lida, "
            "quantidade_milesimos, unidade, preco_unitario_centavos, desconto_centavos, "
            "valor_total_centavos, categoria_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(ids[0], doc, i["seq"], i.get("codigo"), i["descricao"], i["quantidade_milesimos"],
              i["unidade"], i["preco_unitario_centavos"], i["desconto_centavos"],
              i["valor_total_centavos"], i["categoria_id"]) for i in itens])
    return {"documento_id": doc, "transacao_id": ids[0], "valor_centavos": valor,
            "itens": len(itens), "categorias": len(usadas)}
