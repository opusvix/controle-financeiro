"""Saúde, backup e leitura de QR Code de NFC-e."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile

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
    }


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
        chaves = nfce.chaves_da_imagem(conteudo)
    except Exception as e:  # imagem corrompida ou formato não suportado
        raise HTTPException(422, f"Não consegui abrir a imagem: {e}") from e
    return {"arquivo": arquivo.filename, "notas": [k.como_dict() for k in chaves]}
