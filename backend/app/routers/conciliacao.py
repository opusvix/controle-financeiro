"""Conciliação bancária: subir um extrato OFX e cruzar com os lançamentos da conta."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..deps import con
from ..services import conciliacao, conciliacao_fatura, fatura_leitor
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


# --- Conciliação da FATURA do cartão (arquivo do banco × lançamentos da fatura) ---

@router.post("/fatura/analisar")
async def analisar_fatura(arquivo: UploadFile = File(...), cartao_id: int = Form(...),
                          competencia: str = Form(...), c=Depends(con)):
    """Não grava nada: lê o arquivo da fatura e cruza com a fatura do cartão na competência."""
    try:
        lido = fatura_leitor.ler(arquivo.filename or "", await arquivo.read())
        resultado = conciliacao_fatura.conciliar(c, cartao_id, competencia, lido)
    except fatura_leitor.FaturaInvalida as e:
        raise HTTPException(422, str(e)) from e
    except RegraViolada as e:
        raise HTTPException(422, str(e)) from e
    return {**resultado, "arquivo": arquivo.filename}


class CriarLinhaFatura(BaseModel):
    data: date
    valor_centavos: int           # com sinal: negativo = crédito/estorno
    descricao: str = ""
    categoria_id: int | None = None


class AplicarFaturaIn(BaseModel):
    cartao_id: int
    competencia: str
    conferir_ids: list[int] = []
    criar: list[CriarLinhaFatura] = []
    valor_banco: int | None = None


@router.post("/fatura/aplicar")
def aplicar_fatura(dados: AplicarFaturaIn, c=Depends(con)):
    """Confere os casados, lança na fatura o que faltou e grava o total do extrato."""
    try:
        return conciliacao_fatura.aplicar(c, dados.cartao_id, dados.competencia,
                                          dados.conferir_ids,
                                          [l.model_dump() for l in dados.criar],
                                          dados.valor_banco)
    except RegraViolada as e:
        raise HTTPException(422, str(e)) from e
