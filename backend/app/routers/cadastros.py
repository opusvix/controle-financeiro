"""Contas, cartões, categorias, tags e instituições."""
from __future__ import annotations

import sqlite3
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..deps import con

router = APIRouter(prefix="/api", tags=["cadastros"])


def _linhas(c: sqlite3.Connection, sql: str, *args) -> list[dict]:
    return [dict(r) for r in c.execute(sql, args)]


def _gravar(c: sqlite3.Connection, tabela: str, dados: dict, id_: int | None = None) -> dict:
    try:
        with c:
            if id_ is None:
                cols = ", ".join(dados)
                id_ = c.execute(f"INSERT INTO {tabela} ({cols}) VALUES "
                                f"({', '.join('?' for _ in dados)})", tuple(dados.values())).lastrowid
            else:
                sets = ", ".join(f"{k} = ?" for k in dados)
                if c.execute(f"UPDATE {tabela} SET {sets} WHERE id = ?",
                             (*dados.values(), id_)).rowcount == 0:
                    raise HTTPException(404, f"{tabela} {id_} não encontrada")
    except sqlite3.IntegrityError as e:
        raise HTTPException(422, f"Dados inválidos: {e}") from e
    return dict(c.execute(f"SELECT * FROM {tabela} WHERE id = ?", (id_,)).fetchone())


class ContaIn(BaseModel):
    nome: str = Field(min_length=1)
    instituicao_id: int | None = None
    tipo: Literal["corrente", "poupanca", "investimento", "carteira", "outro"] = "corrente"
    saldo_inicial_centavos: int = 0
    data_saldo_inicial: date = Field(default_factory=date.today)
    cor: str = "#6b7280"
    compoe_saldo_disponivel: bool = True
    ativa: bool = True


class CartaoIn(BaseModel):
    nome: str = Field(min_length=1)
    instituicao_id: int | None = None
    bandeira: str
    final: str = Field(pattern=r"^\d{4}$", description="4 últimos dígitos")
    limite_centavos: int = 0
    dia_fechamento: int = Field(ge=1, le=31)
    dia_vencimento: int = Field(ge=1, le=31)
    conta_pagamento_id: int | None = None
    cor: str = "#6b7280"
    ativo: bool = True


class CategoriaIn(BaseModel):
    nome: str = Field(min_length=1)
    tipo: Literal["receita", "despesa"]
    pai_id: int | None = None
    icone: str | None = None
    cor: str = "#6b7280"


class TagIn(BaseModel):
    nome: str = Field(min_length=1)
    cor: str = "#6b7280"


def _dump(m: BaseModel) -> dict:
    d = m.model_dump()
    return {k: (v.isoformat() if isinstance(v, date) else int(v) if isinstance(v, bool) else v)
            for k, v in d.items()}


@router.get("/instituicoes")
def listar_instituicoes(c=Depends(con)):
    return _linhas(c, "SELECT * FROM instituicao ORDER BY nome")


@router.get("/contas")
def listar_contas(c=Depends(con)):
    return _linhas(c, "SELECT * FROM conta ORDER BY ativa DESC, nome")


@router.post("/contas", status_code=201)
def criar_conta(dados: ContaIn, c=Depends(con)):
    return _gravar(c, "conta", _dump(dados))


@router.put("/contas/{id_}")
def editar_conta(id_: int, dados: ContaIn, c=Depends(con)):
    return _gravar(c, "conta", _dump(dados), id_)


@router.get("/cartoes")
def listar_cartoes(c=Depends(con)):
    return _linhas(c, "SELECT * FROM cartao ORDER BY ativo DESC, nome")


@router.post("/cartoes", status_code=201)
def criar_cartao(dados: CartaoIn, c=Depends(con)):
    return _gravar(c, "cartao", _dump(dados))


@router.put("/cartoes/{id_}")
def editar_cartao(id_: int, dados: CartaoIn, c=Depends(con)):
    return _gravar(c, "cartao", _dump(dados), id_)


@router.get("/categorias")
def listar_categorias(tipo: Literal["receita", "despesa"] | None = None, c=Depends(con)):
    if tipo:
        return _linhas(c, "SELECT * FROM categoria WHERE tipo = ? ORDER BY COALESCE(pai_id, id), "
                          "pai_id IS NOT NULL, nome", tipo)
    return _linhas(c, "SELECT * FROM categoria ORDER BY tipo, COALESCE(pai_id, id), "
                      "pai_id IS NOT NULL, nome")


@router.post("/categorias", status_code=201)
def criar_categoria(dados: CategoriaIn, c=Depends(con)):
    if dados.pai_id is not None:
        pai = c.execute("SELECT tipo, pai_id FROM categoria WHERE id = ?", (dados.pai_id,)).fetchone()
        if pai is None or pai["tipo"] != dados.tipo or pai["pai_id"] is not None:
            raise HTTPException(422, "A categoria-mãe deve existir, ser do mesmo tipo e "
                                     "não ser uma subcategoria")
    return _gravar(c, "categoria", _dump(dados))


@router.get("/tags")
def listar_tags(c=Depends(con)):
    return _linhas(c, "SELECT * FROM tag ORDER BY nome")


@router.post("/tags", status_code=201)
def criar_tag(dados: TagIn, c=Depends(con)):
    return _gravar(c, "tag", _dump(dados))
