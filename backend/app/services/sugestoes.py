"""Autocompletar a Descrição ao cadastrar uma transação (estilo Mobills).

Aprende sozinho com o histórico: conforme a pessoa digita, sugere descrições já
usadas antes (as mais frequentes e recentes primeiro) e, de brinde, a categoria
que ela costuma usar naquela descrição — sem gravar nada, é só um palpite para a
tela já vir preenchida. Mesma filosofia da sugestão de categoria na conciliação.
"""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from collections import Counter

# Qual tipo de categoria (receita/despesa) combina com o tipo da transação.
_CATEGORIA_DE = {
    "receita": "receita",
    "despesa": "despesa",
    "despesa_cartao": "despesa",
    "credito_cartao": "despesa",
}


def _chave(texto: str) -> str:
    """Normaliza para casar textos parecidos: sem acentos, sem dígitos nem pontuação,
    espaços colapsados, maiúsculas. 'Mercado 123' e 'MERCADO' caem na mesma chave."""
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    t = re.sub(r"[0-9]+", " ", t)
    t = re.sub(r"[^A-Za-z ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip().upper()


def descricoes(con: sqlite3.Connection, tipo: str, termo: str, limite: int = 8) -> list[dict]:
    """Sugere descrições do histórico que combinam com o que foi digitado.

    Casa pela forma normalizada (ignora acento/número/caixa). Quem COMEÇA com o termo
    vem antes de quem só CONTÉM; depois desempata por frequência e pela data mais recente.
    Cada sugestão traz `categoria_id` = a categoria mais usada naquela descrição (do tipo
    certo), ou None. Devolve no máximo `limite` itens; termo com menos de 2 letras → vazio."""
    chave_termo = _chave(termo)
    if len(chave_termo) < 2:
        return []

    cat_tipo = _CATEGORIA_DE.get(tipo)
    # Agrupa por descrição EXATA (como foi digitada), guardando quantas vezes apareceu,
    # a data mais recente e a contagem de categorias por tipo certo.
    grupos: dict[str, dict] = {}
    for r in con.execute(
            "SELECT descricao, data, categoria_id, "
            "       (SELECT tipo FROM categoria WHERE id = t.categoria_id) AS cat_tipo "
            "FROM transacao t WHERE descricao IS NOT NULL AND descricao <> ''"):
        desc = (r["descricao"] or "").strip()
        if not desc:
            continue
        g = grupos.setdefault(desc, {"n": 0, "ultima": "", "cats": Counter()})
        g["n"] += 1
        if (r["data"] or "") > g["ultima"]:
            g["ultima"] = r["data"] or ""
        if r["categoria_id"] and r["cat_tipo"] == cat_tipo:
            g["cats"][r["categoria_id"]] += 1

    candidatos = []
    for desc, g in grupos.items():
        chave = _chave(desc)
        if chave_termo not in chave:
            continue
        prefixo = chave.startswith(chave_termo)
        candidatos.append((0 if prefixo else 1, -g["n"], -_num_data(g["ultima"]), desc, g))

    candidatos.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
    saida = []
    for _, _, _, desc, g in candidatos[:limite]:
        cat = g["cats"].most_common(1)[0][0] if g["cats"] else None
        saida.append({"descricao": desc, "categoria_id": cat})
    return saida


def _num_data(data: str) -> int:
    """AAAA-MM-DD -> 20261118 (0 se vazia), para ordenar da mais recente para a mais antiga."""
    digitos = re.sub(r"\D", "", data or "")
    return int(digitos) if digitos else 0
