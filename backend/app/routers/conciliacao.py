"""Conciliação bancária: subir um extrato OFX e cruzar com os lançamentos da conta."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..deps import con
from ..services import conciliacao, conciliacao_fatura, fatura_leitor, pasta_local
from ..services.transacoes import RegraViolada

router = APIRouter(prefix="/api/conciliacao", tags=["conciliacao"])


@router.post("/analisar")
async def analisar(arquivos: list[UploadFile] = File(...), conta_id: int = Form(...),
                   tolerancia_dias: int = Form(5), c=Depends(con)):
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


class PastaIn(BaseModel):
    pasta: str
    conta_id: int
    tolerancia_dias: int = 5


@router.post("/analisar-pasta")
def analisar_pasta(dados: PastaIn, c=Depends(con)):
    """Lê todos os .ofx de uma pasta do próprio computador (o servidor é local), como o
    `analisar` por upload — mas aqui a pessoa informa o caminho UMA vez e a tela guarda a
    última pasta usada, para não ter de procurar o extrato toda vez.
    """
    caminho = dados.pasta.strip().strip('"').strip("'")
    if not caminho:
        raise HTTPException(422, "Informe o caminho da pasta dos extratos.")
    pasta = Path(caminho)
    if not pasta.is_dir():
        raise HTTPException(422, f"Não encontrei a pasta: {caminho}")
    ofxs = sorted(p for p in pasta.iterdir() if p.is_file() and p.suffix.lower() == ".ofx")
    if not ofxs:
        raise HTTPException(422, f"A pasta não tem nenhum extrato .ofx: {pasta}")
    try:
        conteudo = b"\n".join(p.read_bytes() for p in ofxs)
        linhas = conciliacao.ler_ofx(conteudo)
        resultado = conciliacao.conciliar(c, dados.conta_id, linhas, dados.tolerancia_dias)
    except conciliacao.OFXInvalido as e:
        raise HTTPException(422, str(e)) from e
    return {**resultado, "arquivos": [p.name for p in ofxs], "pasta": str(pasta)}


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
        lido = fatura_leitor.ler(arquivo.filename or "", await arquivo.read(), competencia)
        resultado = conciliacao_fatura.conciliar(c, cartao_id, competencia, lido)
    except fatura_leitor.FaturaInvalida as e:
        raise HTTPException(422, str(e)) from e
    except RegraViolada as e:
        raise HTTPException(422, str(e)) from e
    return {**resultado, "arquivo": arquivo.filename}


class FaturaPastaIn(BaseModel):
    pasta: str
    arquivo: str
    cartao_id: int
    competencia: str


@router.post("/fatura/analisar-pasta")
def analisar_fatura_pasta(dados: FaturaPastaIn, c=Depends(con)):
    """Lê UM arquivo de fatura (.csv/.pdf) escolhido de uma pasta do próprio PC e cruza
    com a fatura da competência. A tela guarda a última pasta usada."""
    nome, conteudo = pasta_local.ler_arquivo(dados.pasta, dados.arquivo, [".csv", ".pdf"])
    try:
        lido = fatura_leitor.ler(nome, conteudo, dados.competencia)
        resultado = conciliacao_fatura.conciliar(c, dados.cartao_id, dados.competencia, lido)
    except fatura_leitor.FaturaInvalida as e:
        raise HTTPException(422, str(e)) from e
    except RegraViolada as e:
        raise HTTPException(422, str(e)) from e
    return {**resultado, "arquivo": nome, "pasta": dados.pasta}


class CriarLinhaFatura(BaseModel):
    data: date
    valor_centavos: int           # com sinal: negativo = crédito/estorno
    descricao: str = ""
    categoria_id: int | None = None


class AjusteFatura(BaseModel):
    id: int
    valor_centavos: int           # com sinal (ponto de vista da fatura)


class AplicarFaturaIn(BaseModel):
    cartao_id: int
    competencia: str
    conferir_ids: list[int] = []
    criar: list[CriarLinhaFatura] = []
    ajustar: list[AjusteFatura] = []
    valor_banco: int | None = None


@router.post("/fatura/aplicar")
def aplicar_fatura(dados: AplicarFaturaIn, c=Depends(con)):
    """Confere os casados, lança na fatura o que faltou e grava o total do extrato."""
    try:
        return conciliacao_fatura.aplicar(c, dados.cartao_id, dados.competencia,
                                          dados.conferir_ids,
                                          [l.model_dump() for l in dados.criar],
                                          dados.valor_banco,
                                          [a.model_dump() for a in dados.ajustar])
    except RegraViolada as e:
        raise HTTPException(422, str(e)) from e
