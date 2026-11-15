"""Contas da casa em PDF: subir as faturas (luz, água, plano…), conferir o que foi lido e gravar as fichas.

Mesmo leitor do script `scripts\\importar_contas.bat`, agora por uma tela no app: funciona
tanto pelo atalho (navegador) quanto pelo .exe. Não guarda nada em disco — o PDF é lido em
memória, num arquivo temporário apagado logo depois.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..deps import con
from ..importacao import contas_pdf
from ..services import contas_casa
from ..services.transacoes import RegraViolada

router = APIRouter(prefix="/api/contas-pdf", tags=["contas-pdf"])


def _ler_bytes(nome: str, conteudo: bytes, senha: str | None) -> contas_pdf.Fatura | None:
    """Lê uma fatura a partir dos bytes enviados (grava num arquivo temporário e apaga em seguida)."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(conteudo)
        caminho = Path(tmp.name)
    try:
        f = contas_pdf.ler(caminho, senha)
    finally:
        caminho.unlink(missing_ok=True)
    if f is not None:
        f.arquivo = nome          # guarda o nome real, não o do arquivo temporário
    return f


def _fatura_json(f: contas_pdf.Fatura) -> dict:
    return {"emissor": f.emissor, "tipo": f.tipo, "referencia": f.referencia,
            "vencimento": f.vencimento, "total_centavos": f.total_centavos,
            "ficha": f.ficha, "historico": [list(h) for h in f.historico],
            "itens": [list(i) for i in f.itens], "arquivo": f.arquivo}


@router.post("/analisar")
async def analisar(arquivos: list[UploadFile], senha: str = Form(""), c=Depends(con)):
    """Não grava nada: lê cada PDF e, para cada um, procura o lançamento já pago que ele preenche.

    `senha` (opcional) atende os PDFs protegidos (EDP Solar, Claro); várias separadas por ";".
    """
    contas = []
    for a in arquivos:
        nome = a.filename or "arquivo.pdf"
        if not nome.lower().endswith(".pdf"):
            continue                                  # a pasta pode ter outros arquivos; só PDF interessa
        try:
            f = _ler_bytes(nome, await a.read(), senha or None)
        except PermissionError:
            contas.append({"arquivo": nome, "status": "senha", "mensagem": None,
                           "fatura": None, "lancamento": None})
            continue
        except Exception as e:                        # um PDF ruim não derruba a leitura dos outros
            contas.append({"arquivo": nome, "status": "erro", "mensagem": str(e),
                           "fatura": None, "lancamento": None})
            continue
        if f is None:
            contas.append({"arquivo": nome, "status": "sem_leitor", "mensagem": None,
                           "fatura": None, "lancamento": None})
            continue
        t = contas_pdf.achar_lancamento(c, f)
        lancamento = None
        if t is not None:
            ja = c.execute("SELECT 1 FROM conta_ficha WHERE transacao_id = ?", (t["id"],)).fetchone()
            lancamento = {"id": t["id"], "data": t["data"], "descricao": t["descricao"],
                          "valor_centavos": t["valor_centavos"], "ja_tem_ficha": ja is not None}
        contas.append({"arquivo": nome, "status": "ok", "mensagem": None,
                       "fatura": _fatura_json(f), "lancamento": lancamento})
    # Ordena para a tela: primeiro os que acharam lançamento, depois o resto.
    contas.sort(key=lambda x: (x["status"] != "ok", x["lancamento"] is None, x["arquivo"]))
    return {"contas": contas}


class FaturaIn(BaseModel):
    emissor: str
    tipo: str
    referencia: str
    vencimento: str
    total_centavos: int
    ficha: dict = {}
    historico: list[tuple[str, float | None, int | None]] = []
    itens: list[tuple[str, str, int]] = []
    arquivo: str = ""


class ItemGravar(BaseModel):
    fatura: FaturaIn
    transacao_id: int


class GravarIn(BaseModel):
    itens: list[ItemGravar] = []


@router.post("/gravar")
def gravar(dados: GravarIn, c=Depends(con)):
    """Grava a ficha de cada fatura confirmada no lançamento escolhido (e o histórico de consumo)."""
    gravadas = 0
    for it in dados.itens:
        t = c.execute("SELECT * FROM transacao WHERE id = ?", (it.transacao_id,)).fetchone()
        if t is None:
            raise HTTPException(422, f"Lançamento {it.transacao_id} não encontrado.")
        p = it.fatura
        f = contas_pdf.Fatura(
            emissor=p.emissor, tipo=p.tipo, referencia=p.referencia, vencimento=p.vencimento,
            total_centavos=p.total_centavos, ficha=p.ficha,
            historico=[tuple(h) for h in p.historico], itens=[tuple(i) for i in p.itens],
            arquivo=p.arquivo)
        try:
            contas_pdf.aplicar_ficha(c, t, f)
        except RegraViolada as e:
            raise HTTPException(422, str(e)) from e
        contas_pdf.gravar_historico(c, f.tipo, f.historico)
        gravadas += 1
    return {"gravadas": gravadas}
