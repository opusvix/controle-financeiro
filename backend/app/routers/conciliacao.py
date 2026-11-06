"""Conciliação bancária: subir um extrato OFX e cruzar com os lançamentos da conta."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..deps import con
from ..services import conciliacao
from ..services.transacoes import RegraViolada

router = APIRouter(prefix="/api/conciliacao", tags=["conciliacao"])


@router.post("/analisar")
async def analisar(arquivo: UploadFile, conta_id: int = Form(...),
                   tolerancia_dias: int = Form(3), c=Depends(con)):
    """Não grava nada: lê o OFX e devolve os quatro baldes para a tela revisar."""
    try:
        linhas = conciliacao.ler_ofx(await arquivo.read())
        resultado = conciliacao.conciliar(c, conta_id, linhas, tolerancia_dias)
    except conciliacao.OFXInvalido as e:
        raise HTTPException(422, str(e)) from e
    return {**resultado, "arquivo": arquivo.filename}


class CriarLinha(BaseModel):
    data: date
    valor_centavos: int           # com sinal: negativo = saída
    descricao: str = ""
    categoria_id: int | None = None


class AplicarIn(BaseModel):
    conta_id: int
    conferir_ids: list[int] = []
    criar: list[CriarLinha] = []


@router.post("/aplicar")
def aplicar(dados: AplicarIn, c=Depends(con)):
    """Marca os casados como conferidos e cria os lançamentos que faltavam."""
    try:
        return conciliacao.aplicar(c, dados.conta_id, dados.conferir_ids,
                                   [l.model_dump() for l in dados.criar])
    except RegraViolada as e:
        raise HTTPException(422, str(e)) from e
