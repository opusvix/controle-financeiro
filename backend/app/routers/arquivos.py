"""Listar arquivos de uma pasta do próprio computador, para os campos "pasta que
lembra o último local" (o servidor roda local, então consegue ver a pasta)."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..services import pasta_local

router = APIRouter(prefix="/api/arquivos", tags=["arquivos"])


class ListarIn(BaseModel):
    pasta: str
    extensoes: list[str]


@router.post("/listar")
def listar(dados: ListarIn):
    """Nomes dos arquivos da pasta que batem com as extensões (ex.: .csv, .pdf)."""
    pasta, nomes = pasta_local.listar(dados.pasta, dados.extensoes)
    return {"pasta": str(pasta), "arquivos": nomes}
