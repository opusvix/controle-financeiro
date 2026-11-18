"""Cupons: ler a página salva da SEFAZ (ou o .json de um pedido) e lançar com itens."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from ..deps import con
from ..services import cupons, pasta_local
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


class PastaIn(BaseModel):
    pasta: str
    arquivo: str


@router.post("/ler-da-pasta")
def ler_da_pasta(dados: PastaIn, c=Depends(con)):
    """Lê UM cupom (foto/PDF) escolhido de uma pasta do próprio PC. A tela guarda a última pasta."""
    nome, conteudo = pasta_local.ler_arquivo(
        dados.pasta, dados.arquivo, [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".pdf"])
    try:
        cupom = cupons.ler_arquivo(nome, conteudo)
    except cupons.CupomInvalido as e:
        raise HTTPException(422, str(e)) from e
    return {**cupons.preparar(c, cupom), "arquivo": nome}


class LancarIn(BaseModel):
    cupom: dict
    conta_id: int | None = None
    cartao_id: int | None = None
    data: date | None = None
    descricao: str | None = None
    categorias: dict[int, int] = {}
    arquivo: str = ""
    so_precos: bool = False     # cupom antigo: só histórico de preços, sem criar despesa


@router.post("/lancar", status_code=201)
def lancar(dados: LancarIn, c=Depends(con)):
    try:
        return cupons.lancar(c, dados.cupom, conta_id=dados.conta_id, cartao_id=dados.cartao_id,
                             data=dados.data, descricao=dados.descricao,
                             categorias=dados.categorias, arquivo=dados.arquivo,
                             so_precos=dados.so_precos)
    except RegraViolada as e:
        raise HTTPException(422, str(e)) from e
