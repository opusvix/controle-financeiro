"""Comparação de preços (Fase 3): acompanha o preço de cada produto ao longo do tempo
e entre as lojas, sem olhar a marca.

Ideia (como uma análise de BI): cada item de cupom é um "fato" com preço, data e loja.
Agrupamos os fatos por PRODUTO (o texto da nota, normalizado — tiramos acento, unidade
e código) e por UNIDADE de compra (kg, l, un). Dentro de cada produto comparamos:
- o preço por unidade base (R$/kg, R$/l, R$/un), que é o único jeito justo de comparar
  quantidades diferentes ("1,130 kg de laranja" vira R$/kg);
- a compra mais recente contra a anterior (está subindo ou caindo?);
- a última compra em cada loja (onde saiu mais barato?).

Observação: ainda não usamos a tabela `produto`/`produto_alias`. A identidade do produto
é o texto normalizado da nota. Dá para evoluir depois para mesclar sinônimos
("LARANJA PERA" × "LARANJA PÊRA KG") sem mudar esta interface.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from collections import Counter

# Tokens que não ajudam a identificar o produto (unidade/embalagem). Removidos das pontas.
_SUFIXOS = {
    "KG", "KGS", "K", "G", "GR", "GRS", "GRAMA", "GRAMAS",
    "UN", "UND", "UNID", "UNIDADE", "PC", "PCT", "PACOTE", "PCTE",
    "L", "LT", "LTR", "LITRO", "LITROS", "ML", "CX", "CXA", "FD", "FARDO",
    "DZ", "DZA", "DUZIA", "BDJ", "BANDEJA", "MACO", "MOLHO", "GARRAFA",
}
_UNIDADE = {"KG": "kg", "G": "kg", "GR": "kg", "L": "l", "LT": "l", "ML": "l",
            "UN": "un", "UND": "un", "UNID": "un"}


def _sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")


def _chave_produto(descricao: str) -> str:
    """Texto da nota -> identidade estável do produto (maiúsculas, sem acento/unidade/código)."""
    s = _sem_acento(descricao).upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    toks = [t for t in s.split() if t]
    while toks and (toks[-1] in _SUFIXOS or toks[-1].isdigit()):
        toks.pop()
    while toks and toks[0].isdigit():      # código da loja no começo
        toks.pop(0)
    return " ".join(toks)


def _nome_bonito(descricao: str) -> str:
    """Nome para exibir: o texto original sem código/unidade, mas mantendo acentos. Ex.: 'MAÇÃ GALA KG' -> 'Maçã Gala'."""
    toks = [t for t in re.split(r"\s+", (descricao or "").strip()) if t]
    while toks and (_sem_acento(toks[-1]).upper() in _SUFIXOS or _sem_acento(toks[-1]).isdigit()):
        toks.pop()
    while toks and _sem_acento(toks[0]).isdigit():
        toks.pop(0)
    return " ".join(toks).title() or "(sem nome)"


def _unidade_base(unidade: str) -> str:
    return _UNIDADE.get((unidade or "").strip().upper(), (unidade or "un").strip().lower())


def _variacao(atual: int, anterior: int | None) -> float | None:
    if not anterior:
        return None
    return round((atual / anterior - 1) * 100, 1)


def painel(con: sqlite3.Connection, meses: int = 24) -> dict:
    """Agrupa os itens de cupom por produto e devolve, por categoria, a evolução de preço."""
    linhas = con.execute(
        """SELECT i.descricao_lida, i.unidade, i.quantidade_milesimos,
                  (i.valor_total_centavos - i.desconto_centavos) AS liquido,
                  COALESCE(t.data, substr(d.data_emissao, 1, 10)) AS data,
                  COALESCE(e.nome, 'Loja não identificada') AS loja,
                  c.nome AS categoria, COALESCE(m.nome, c.nome) AS categoria_mae, c.id AS categoria_id
           FROM item i
           LEFT JOIN transacao t ON t.id = i.transacao_id
           LEFT JOIN documento d ON d.id = i.documento_id
           LEFT JOIN estabelecimento e ON e.id = COALESCE(t.estabelecimento_id, d.estabelecimento_id)
           LEFT JOIN categoria c ON c.id = i.categoria_id
           LEFT JOIN categoria m ON m.id = c.pai_id
           WHERE i.quantidade_milesimos > 0
             AND ((t.id IS NOT NULL AND t.ignorar = 0) OR (i.transacao_id IS NULL AND d.id IS NOT NULL))
           ORDER BY data""").fetchall()

    # Agrupa por (produto, unidade base). Unidades diferentes do mesmo texto viram produtos
    # separados (ex.: ovo "por dúzia" × ovo "por unidade") para não comparar coisas incomparáveis.
    produtos: dict[tuple[str, str], dict] = {}
    for r in linhas:
        chave = _chave_produto(r["descricao_lida"])
        if not chave:
            continue
        unid = _unidade_base(r["unidade"])
        preco = round(r["liquido"] * 1000 / r["quantidade_milesimos"])   # centavos por 1 kg/l/un
        if preco <= 0:
            continue
        p = produtos.setdefault((chave, unid), {
            "unidade": unid, "nomes": Counter(),
            "categorias": Counter(), "maes": Counter(), "serie": []})
        p["nomes"][_nome_bonito(r["descricao_lida"])] += 1
        p["serie"].append({"data": r["data"], "loja": r["loja"],
                           "preco_centavos": preco, "qtd_milesimos": r["quantidade_milesimos"]})
        if r["categoria"]:
            p["categorias"][r["categoria"]] += 1
            p["maes"][r["categoria_mae"] or r["categoria"]] += 1

    lista = [_resumir_produto(p) for p in produtos.values()]
    lista = [p for p in lista if p["compras"] >= 1]
    lista.sort(key=lambda p: (-p["compras"], p["nome"]))

    # Agrupa os produtos por categoria (a filha, ex.: Frutas), com a mãe para rótulo.
    grupos: dict[str, dict] = {}
    for p in lista:
        g = grupos.setdefault(p["categoria"] or "(sem categoria)", {
            "categoria": p["categoria"] or "(sem categoria)",
            "categoria_mae": p["categoria_mae"], "produtos": []})
        g["produtos"].append(p)
    ordem = sorted(grupos.values(), key=lambda g: (g["categoria"] == "(sem categoria)", g["categoria"]))

    resumo = {
        "produtos": len(lista),
        "compras": sum(p["compras"] for p in lista),
        "lojas": len({s["loja"] for p in produtos.values() for s in p["serie"]}),
        "com_historico": sum(1 for p in lista if p["compras"] >= 2),
        "subindo": sum(1 for p in lista if (p["variacao_pct"] or 0) > 0),
        "caindo": sum(1 for p in lista if (p["variacao_pct"] or 0) < 0),
    }
    return {"grupos": ordem, "resumo": resumo}


def _resumir_produto(p: dict) -> dict:
    serie = sorted(p["serie"], key=lambda s: s["data"])
    precos = [s["preco_centavos"] for s in serie]
    atual = serie[-1]
    # "Anterior" = a compra anterior em data diferente da última (ignora outra loja no mesmo dia).
    anterior = next((s for s in reversed(serie[:-1]) if s["data"] != atual["data"]), None)
    # Último preço por loja (para "onde está mais barato").
    por_loja: dict[str, dict] = {}
    for s in serie:
        if s["loja"] not in por_loja or s["data"] >= por_loja[s["loja"]]["data"]:
            por_loja[s["loja"]] = s
    por_loja_lista = sorted(por_loja.values(), key=lambda s: s["preco_centavos"])
    menor = min(serie, key=lambda s: s["preco_centavos"])
    maior = max(serie, key=lambda s: s["preco_centavos"])
    categoria = p["categorias"].most_common(1)[0][0] if p["categorias"] else None
    mae = p["maes"].most_common(1)[0][0] if p["maes"] else None
    nome = p["nomes"].most_common(1)[0][0] if p["nomes"] else "(sem nome)"
    return {
        "nome": nome, "unidade": p["unidade"], "compras": len(serie),
        "categoria": categoria, "categoria_mae": mae,
        "preco_atual_centavos": atual["preco_centavos"], "data_atual": atual["data"], "loja_atual": atual["loja"],
        "preco_anterior_centavos": anterior["preco_centavos"] if anterior else None,
        "data_anterior": anterior["data"] if anterior else None,
        "variacao_pct": _variacao(atual["preco_centavos"], anterior["preco_centavos"] if anterior else None),
        "menor_centavos": menor["preco_centavos"], "menor_loja": menor["loja"], "menor_data": menor["data"],
        "maior_centavos": maior["preco_centavos"],
        "media_centavos": round(sum(precos) / len(precos)),
        "melhor_loja": por_loja_lista[0]["loja"] if len(por_loja_lista) > 1 else None,
        "lojas": len(por_loja),
        "por_loja": [{"loja": s["loja"], "preco_centavos": s["preco_centavos"], "data": s["data"]}
                     for s in por_loja_lista],
        "serie": serie,
    }
