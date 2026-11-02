"""Transações e Dashboard."""
from __future__ import annotations

import re
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..deps import con
from ..services import fatura_cartao, painel, transacoes

router = APIRouter(prefix="/api", tags=["movimento"])
COMPETENCIA = r"^\d{4}-(0[1-9]|1[0-2])$"


class TransacaoIn(BaseModel):
    tipo: Literal["receita", "despesa", "despesa_cartao", "transferencia",
                  "pagamento_fatura", "ajuste"]
    descricao: str = Field(min_length=1)
    valor_centavos: int = Field(gt=0)
    data: date
    pago: bool = True
    conta_id: int | None = None
    conta_destino_id: int | None = None
    cartao_id: int | None = None
    parcelas: int = Field(default=1, ge=1, le=72)
    fatura_competencia: str | None = Field(default=None, pattern=COMPETENCIA)
    categoria_id: int | None = None
    estabelecimento_id: int | None = None
    ajuste_negativo: bool = False
    ignorar: bool = False
    observacao: str | None = None
    tags: list[int] = []


@router.get("/transacoes")
def listar(competencia: str = Query(pattern=COMPETENCIA), conta_id: int | None = None,
           tipo: str | None = None, c=Depends(con)):
    ano, mes = competencia.split("-")
    sql = """
        SELECT t.*, c.nome AS categoria, co.nome AS conta, ca.nome AS cartao,
               (SELECT group_concat(tg.nome, ', ') FROM transacao_tag tt
                  JOIN tag tg ON tg.id = tt.tag_id WHERE tt.transacao_id = t.id) AS tags,
               (SELECT COUNT(*) FROM item i WHERE i.transacao_id = t.id) AS itens
        FROM transacao t
        LEFT JOIN categoria c ON c.id = t.categoria_id
        LEFT JOIN conta co ON co.id = t.conta_id
        LEFT JOIN cartao ca ON ca.id = t.cartao_id
        WHERE strftime('%Y-%m', t.data) = ?
    """
    args: list = [f"{ano}-{mes}"]
    if conta_id:
        sql += " AND t.conta_id = ?"
        args.append(conta_id)
    if tipo:
        sql += " AND t.tipo = ?"
        args.append(tipo)
    sql += " ORDER BY t.data DESC, t.id DESC"
    return [dict(r) for r in c.execute(sql, args)]


@router.post("/transacoes", status_code=201)
def criar(dados: TransacaoIn, c=Depends(con)):
    try:
        ids = transacoes.criar(c, transacoes.NovaTransacao(**dados.model_dump()))
    except transacoes.RegraViolada as e:
        raise HTTPException(422, str(e)) from e
    marcas = ", ".join("?" for _ in ids)
    return [dict(r) for r in c.execute(f"SELECT * FROM transacao WHERE id IN ({marcas})", ids)]


class ReajusteIn(BaseModel):
    saldo_centavos: int
    data: date = Field(default_factory=date.today)
    no_saldo_inicial: bool = False   # True: corrige o saldo de abertura em vez de lançar ajuste


@router.post("/contas/{id_}/reajuste", status_code=201)
def reajustar(id_: int, dados: ReajusteIn, c=Depends(con)):
    """Acerta o saldo da conta lançando um ajuste com a diferença."""
    try:
        return transacoes.reajustar_saldo(c, id_, dados.saldo_centavos, dados.data,
                                          dados.no_saldo_inicial)
    except transacoes.RegraViolada as e:
        raise HTTPException(404, str(e)) from e


class EdicaoIn(BaseModel):
    """Só os campos enviados mudam."""
    descricao: str | None = None
    valor_centavos: int | None = Field(default=None, gt=0)
    data: date | None = None
    conta_id: int | None = None
    cartao_id: int | None = None
    categoria_id: int | None = None
    observacao: str | None = None
    conferido: bool | None = None
    pago: bool | None = None
    ignorar: bool | None = None
    fatura_competencia: str | None = Field(default=None, pattern=COMPETENCIA)
    tags: list[int] | None = None


@router.patch("/transacoes/{id_}")
def editar(id_: int, dados: EdicaoIn, c=Depends(con)):
    mudancas = dados.model_dump(exclude_unset=True)
    for k in ("conferido", "pago", "ignorar"):
        if k in mudancas and mudancas[k] is not None:
            mudancas[k] = int(mudancas[k])
    try:
        return transacoes.editar(c, id_, mudancas)
    except transacoes.RegraViolada as e:
        raise HTTPException(422, str(e)) from e


@router.get("/cartoes/{id_}/fatura")
def fatura(id_: int, competencia: str = Query(pattern=COMPETENCIA), c=Depends(con)):
    try:
        return fatura_cartao.detalhe(c, id_, competencia)
    except transacoes.RegraViolada as e:
        raise HTTPException(404, str(e)) from e


class ValorBancoIn(BaseModel):
    valor_centavos: int | None = Field(default=None, ge=0)


@router.put("/cartoes/{id_}/fatura/{competencia}/valor-banco")
def valor_banco(id_: int, competencia: str, dados: ValorBancoIn, c=Depends(con)):
    if not re.match(COMPETENCIA, competencia):
        raise HTTPException(422, "Competência inválida")
    try:
        fatura_cartao.informar_valor_banco(c, id_, competencia, dados.valor_centavos)
    except transacoes.RegraViolada as e:
        raise HTTPException(422, str(e)) from e
    return fatura_cartao.detalhe(c, id_, competencia)


@router.delete("/transacoes/{id_}", status_code=204)
def apagar(id_: int, c=Depends(con)):
    linha = c.execute("SELECT transferencia_par_id FROM transacao WHERE id = ?", (id_,)).fetchone()
    if linha is None:
        raise HTTPException(404, "Transação não encontrada")
    with c:
        # Transferência apaga as duas pernas juntas.
        par = linha["transferencia_par_id"]
        c.execute("UPDATE transacao SET transferencia_par_id = NULL WHERE id IN (?, ?)", (id_, par))
        c.execute("DELETE FROM transacao WHERE id IN (?, ?)", (id_, par))


@router.get("/dashboard")
def dashboard(competencia: str | None = Query(default=None, pattern=COMPETENCIA), c=Depends(con)):
    competencia = competencia or f"{date.today():%Y-%m}"
    if not re.match(COMPETENCIA, competencia):
        raise HTTPException(422, "Competência inválida")
    return painel.resumo(c, competencia)
