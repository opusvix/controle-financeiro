"""Contas da casa em PDF: subir as faturas (luz, água, plano…), conferir o que foi lido e gravar as fichas.

Mesmo leitor do script `scripts\\importar_contas.bat`, agora por uma tela no app: funciona
tanto pelo atalho (navegador) quanto pelo .exe. Não guarda nada em disco — o PDF é lido em
memória, num arquivo temporário apagado logo depois.
"""
from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..deps import con
from ..importacao import contas_pdf
from ..services import transacoes
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


def _analisar_um(c, nome: str, ler) -> dict:
    """Lê uma fatura (a função `ler` devolve Fatura|None ou levanta erro) e monta o resultado da tela."""
    try:
        f = ler()
    except PermissionError:
        return {"arquivo": nome, "status": "senha", "mensagem": None, "fatura": None, "lancamento": None}
    except Exception as e:                            # um PDF ruim não derruba a leitura dos outros
        return {"arquivo": nome, "status": "erro", "mensagem": str(e), "fatura": None, "lancamento": None}
    if f is None:
        return {"arquivo": nome, "status": "sem_leitor", "mensagem": None, "fatura": None, "lancamento": None}
    t = contas_pdf.achar_lancamento(c, f)
    lancamento = None
    if t is not None:
        ja = c.execute("SELECT 1 FROM conta_ficha WHERE transacao_id = ?", (t["id"],)).fetchone()
        lancamento = {"id": t["id"], "data": t["data"], "descricao": t["descricao"],
                      "valor_centavos": t["valor_centavos"], "ja_tem_ficha": ja is not None}
    return {"arquivo": nome, "status": "ok", "mensagem": None,
            "fatura": _fatura_json(f), "lancamento": lancamento}


def _ordenar(contas: list[dict]) -> None:
    """Para a tela: primeiro os que acharam lançamento, depois o resto."""
    contas.sort(key=lambda x: (x["status"] != "ok", x["lancamento"] is None, x["arquivo"]))


@router.post("/analisar")
async def analisar(arquivos: list[UploadFile], senha: str = Form(""), c=Depends(con)):
    """Não grava nada: lê cada PDF enviado e procura o lançamento já pago que ele preenche.

    `senha` (opcional) atende os PDFs protegidos (EDP Solar, Claro); várias separadas por ";".
    """
    contas = []
    for a in arquivos:
        nome = a.filename or "arquivo.pdf"
        if not nome.lower().endswith(".pdf"):
            continue                                  # a seleção pode ter outros arquivos; só PDF interessa
        conteudo = await a.read()
        contas.append(_analisar_um(c, nome, lambda n=nome, b=conteudo: _ler_bytes(n, b, senha or None)))
    _ordenar(contas)
    return {"contas": contas}


class PastaIn(BaseModel):
    pasta: str
    senha: str = ""


@router.post("/analisar-pasta")
def analisar_pasta(dados: PastaIn, c=Depends(con)):
    """Lê todos os PDFs de uma pasta do próprio computador (o servidor é local).

    É o jeito confiável de "escolher a pasta" nos dois modos (navegador e .exe): o seletor nativo
    de pasta do navegador é instável, então aqui a pessoa informa o caminho e o app varre a pasta.
    """
    caminho = dados.pasta.strip().strip('"').strip("'")
    if not caminho:
        raise HTTPException(422, "Informe o caminho da pasta.")
    pasta = Path(caminho)
    if not pasta.is_dir():
        raise HTTPException(422, f"Não encontrei a pasta: {caminho}")
    senha = dados.senha or None
    pdfs = sorted(p for p in pasta.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")
    contas = [_analisar_um(c, p.name, lambda p=p: contas_pdf.ler(p, senha)) for p in pdfs]
    _ordenar(contas)
    return {"contas": contas, "pasta": str(pasta), "total_pdf": len(pdfs)}


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


class CriarDespesa(BaseModel):
    """Criar a despesa que falta, direto pela tela, e já anexar a ficha nela."""
    conta_id: int
    categoria_id: int | None = None
    pago: bool = False          # a conta pode estar a vencer; quem decide é o usuário


class ItemGravar(BaseModel):
    fatura: FaturaIn
    transacao_id: int | None = None       # anexar a este lançamento já existente
    criar: CriarDespesa | None = None     # ou criar a despesa que falta


class GravarIn(BaseModel):
    itens: list[ItemGravar] = []


@router.post("/gravar")
def gravar(dados: GravarIn, c=Depends(con)):
    """Grava a ficha de cada fatura confirmada. Se o lançamento faltar, cria a despesa antes.

    Cada item traz ou `transacao_id` (lançamento já existente) ou `criar` (a conta que pagou e,
    opcional, a categoria): aí lançamos uma despesa paga de mesmo valor, datada no vencimento.
    """
    gravadas = criadas = 0
    for it in dados.itens:
        p = it.fatura
        f = contas_pdf.Fatura(
            emissor=p.emissor, tipo=p.tipo, referencia=p.referencia, vencimento=p.vencimento,
            total_centavos=p.total_centavos, ficha=p.ficha,
            historico=[tuple(h) for h in p.historico], itens=[tuple(i) for i in p.itens],
            arquivo=p.arquivo)
        try:
            if it.criar is not None:
                ids = transacoes.criar(c, transacoes.NovaTransacao(
                    tipo="despesa", descricao=f.emissor, valor_centavos=f.total_centavos,
                    data=date.fromisoformat(f.vencimento), pago=it.criar.pago,
                    conta_id=it.criar.conta_id, categoria_id=it.criar.categoria_id))
                t = c.execute("SELECT * FROM transacao WHERE id = ?", (ids[0],)).fetchone()
                criadas += 1
            else:
                t = c.execute("SELECT * FROM transacao WHERE id = ?", (it.transacao_id,)).fetchone()
                if t is None:
                    raise HTTPException(422, f"Lançamento {it.transacao_id} não encontrado.")
            contas_pdf.aplicar_ficha(c, t, f)
        except RegraViolada as e:
            raise HTTPException(422, str(e)) from e
        contas_pdf.gravar_historico(c, f.tipo, f.historico)
        gravadas += 1
    return {"gravadas": gravadas, "criadas": criadas}
