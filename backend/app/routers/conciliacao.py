"""Conciliação bancária: subir um extrato OFX e cruzar com os lançamentos da conta."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..deps import con
from ..services import conciliacao
from ..services.transacoes import RegraViolada

router = APIRouter(prefix="/api/conciliacao", tags=["conciliacao"])


@router.post("/analisar")
async def analisar(arquivos: list[UploadFile] = File(...), conta_id: int = Form(...),
                   tolerancia_dias: int = Form(3), c=Depends(con)):
    """Não grava nada: lê um ou vários OFX (vários meses) e devolve os quatro baldes.

    Junta os arquivos num texto só — o leitor varre todos os STMTTRN — e remove
    duplicatas por FITID, caso os períodos se sobreponham.
    """
    try:
        conteudo = b"\n".join([await a.read() for a in arquivos])
        linhas = conciliacao.ler_ofx(conteudo)
        resultado = conciliacao.conciliar(c, conta_id, linhas, tolerancia_dias)
    except conciliacao.OFXInvalido as e:
        raise HTTPException(422, str(e)) from e
    return {**resultado, "arquivos": [a.filename for a in arquivos]}


class CriarLinha(BaseModel):
    data: date
    valor_centavos: int           # com sinal: negativo = saída
    descricao: str = ""
    categoria_id: int | None = None


class RenomearItem(BaseModel):
    id: int
    descricao: str


class AplicarIn(BaseModel):
    conta_id: int
    conferir_ids: list[int] = []
    criar: list[CriarLinha] = []
    renomear: list[RenomearItem] = []


@router.post("/aplicar")
def aplicar(dados: AplicarIn, c=Depends(con)):
    """Marca os casados como conferidos, renomeia os ajustados e cria os que faltavam."""
    try:
        return conciliacao.aplicar(c, dados.conta_id, dados.conferir_ids,
                                   [l.model_dump() for l in dados.criar],
                                   [r.model_dump() for r in dados.renomear])
    except RegraViolada as e:
        raise HTTPException(422, str(e)) from e
