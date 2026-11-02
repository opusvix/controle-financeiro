"""Cupons: ler a página salva da SEFAZ (ou o .json de um pedido) e lançar com itens."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from ..deps import con
from ..services import cupons
from ..services.transacoes import RegraViolada

router = APIRouter(prefix="/api/cupons", tags=["cupons"])


@router.post("/ler")
async def ler(arquivo: UploadFile, c=Depends(con)):
    """Não grava nada: devolve o cupom para a tela de revisão."""
    try:
        cupom = cupons.ler_arquivo(arquivo.filename or "", await arquivo.read())
    except cupons.CupomInvalido as e:
        raise HTTPException(422, str(e)) from e
    return {**cupons.preparar(c, cupom), "arquivo": arquivo.filename}


class LancarIn(BaseModel):
    cupom: dict
    conta_id: int | None = None
    cartao_id: int | None = None
    data: date | None = None
    descricao: str | None = None
    categorias: dict[int, int] = {}
    arquivo: str = ""


@router.post("/lancar", status_code=201)
def lancar(dados: LancarIn, c=Depends(con)):
    try:
        return cupons.lancar(c, dados.cupom, conta_id=dados.conta_id, cartao_id=dados.cartao_id,
                             data=dados.data, descricao=dados.descricao,
                             categorias=dados.categorias, arquivo=dados.arquivo)
    except RegraViolada as e:
        raise HTTPException(422, str(e)) from e
