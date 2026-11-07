"""Saúde, backup e leitura de QR Code de NFC-e."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from .. import seed_demo
from ..deps import cfg, con
from ..services import backup, nfce

router = APIRouter(prefix="/api", tags=["sistema"])


@router.get("/saude")
def saude(c=Depends(con), config=Depends(cfg)):
    return {
        "ok": c.execute("SELECT 1").fetchone()[0] == 1,
        "banco": str(config.arquivo_banco),
        "ultimo_backup": backup.ultimo(c),
        "leitura_ia_configurada": config.anthropic_api_key is not None,
        "modo_demo": config.modo_demo,
    }


@router.post("/demo/reiniciar")
def reiniciar_demo(c=Depends(con), config=Depends(cfg)):
    """Devolve a demonstração ao estado de exemplo. Só existe no modo demo."""
    if not config.modo_demo:
        raise HTTPException(404, "Disponível apenas na versão de demonstração")
    seed_demo.reiniciar(c)
    return {"ok": True}


@router.post("/backup")
def fazer_backup(c=Depends(con), config=Depends(cfg)):
    return backup.executar(c, config.pasta_backup, config.pasta_backup_drive)


@router.post("/nfce/chave")
def interpretar_chave(chave: str):
    try:
        return nfce.interpretar_chave(chave).como_dict()
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@router.post("/nfce/qr")
async def ler_qr(arquivo: UploadFile):
    conteudo = await arquivo.read()
    try:
        textos = nfce.ler_qr(conteudo)
    except Exception as e:  # imagem corrompida ou formato não suportado
        raise HTTPException(422, f"Não consegui abrir a imagem: {e}") from e
    notas = []
    for texto in textos:
        try:
            chave = nfce.interpretar_chave(nfce.chave_da_url(texto))
        except ValueError:
            continue  # QR que não é de nota fiscal
        # O próprio QR é o link de consulta da SEFAZ: a tela abre no navegador do usuário,
        # que resolve o captcha e salva a página (Ctrl+S) para importar.
        url = texto if texto.lower().startswith(("http://", "https://")) else None
        notas.append({**chave.como_dict(), "url_consulta": url})
    return {"arquivo": arquivo.filename, "notas": notas}
