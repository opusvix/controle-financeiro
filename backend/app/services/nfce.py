"""Leitura do QR Code e da chave de acesso da NFC-e (modelo 65).

A chave de 44 dígitos já traz UF, ano/mês, CNPJ do emitente, série e número.
Os ITENS não vêm no QR: o portal da SEFAZ-ES exige captcha, então os itens
são lidos da imagem do cupom (próxima etapa, com IA).
"""
from __future__ import annotations

import io
import re
from dataclasses import asdict, dataclass
from urllib.parse import parse_qs, urlparse

UFS = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
       "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
       "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
       "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}


@dataclass
class Chave:
    chave: str
    uf: str
    ano_mes: str        # 'AAAA-MM'
    cnpj: str
    modelo: str         # 65 = NFC-e, 55 = NF-e
    serie: int
    numero: int
    tipo_emissao: str
    codigo: str
    dv: int
    valida: bool

    def como_dict(self) -> dict:
        return asdict(self)


def digito_verificador(chave43: str) -> int:
    """Módulo 11 com pesos 2..9 da direita para a esquerda."""
    soma, peso = 0, 2
    for d in reversed(chave43):
        soma += int(d) * peso
        peso = 2 if peso == 9 else peso + 1
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def interpretar_chave(texto: str) -> Chave:
    chave = re.sub(r"\D", "", texto)
    if len(chave) != 44:
        raise ValueError(f"A chave precisa ter 44 dígitos (veio {len(chave)})")
    dv = int(chave[43])
    return Chave(
        chave=chave,
        uf=UFS.get(chave[0:2], chave[0:2]),
        ano_mes=f"20{chave[2:4]}-{chave[4:6]}",
        cnpj=chave[6:20],
        modelo=chave[20:22],
        serie=int(chave[22:25]),
        numero=int(chave[25:34]),
        tipo_emissao=chave[34],
        codigo=chave[35:43],
        dv=dv,
        valida=digito_verificador(chave[:43]) == dv,
    )


def chave_da_url(url: str) -> str:
    """Extrai a chave do conteúdo do QR (URL ...?p=CHAVE|2|1|1|HASH)."""
    url = url.lstrip("﻿").strip()
    p = parse_qs(urlparse(url).query).get("p") or parse_qs(urlparse(url).query).get("chNFe")
    candidato = p[0].split("|")[0] if p else url
    digitos = re.sub(r"\D", "", candidato)
    if len(digitos) < 44:
        raise ValueError("Não encontrei uma chave de 44 dígitos no QR Code")
    return digitos[:44]


def ler_qr(conteudo: bytes) -> list[str]:
    """Textos de QR Code encontrados na imagem.

    Cupom térmico desbotado costuma falhar na primeira leitura; por isso
    tenta várias escalas e uma versão binarizada (Otsu) antes de desistir.
    """
    import cv2
    import numpy as np
    import zxingcpp
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = None
    cinza = np.array(Image.open(io.BytesIO(conteudo)).convert("L"))
    encontrados: list[str] = []
    for escala in (1.0, 0.5, 0.35, 0.25):
        img = cinza if escala == 1.0 else cv2.resize(
            cinza, None, fx=escala, fy=escala, interpolation=cv2.INTER_AREA)
        suave = cv2.GaussianBlur(img, (3, 3), 0)
        _, otsu = cv2.threshold(suave, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        for variante in (img, otsu):
            for r in zxingcpp.read_barcodes(variante):
                texto = r.text.lstrip("﻿")
                if r.format == zxingcpp.BarcodeFormat.QRCode and texto not in encontrados:
                    encontrados.append(texto)
    return encontrados


def chaves_da_imagem(conteudo: bytes) -> list[Chave]:
    chaves = []
    for texto in ler_qr(conteudo):
        try:
            chaves.append(interpretar_chave(chave_da_url(texto)))
        except ValueError:
            continue  # QR que não é de nota fiscal
    return chaves
