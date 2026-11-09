"""Ler o cupom/pedido impresso (foto ou PDF-imagem) por OCR local, sem internet.

Pensado para o "pedido" da Frescor (sem QR, SEM VALOR FISCAL), cujo layout é bem
regular:

    Codigo Descricao                               Total
    Qtd UN  Unit
    0103 CENOURA                                    3,86
    0,775 KG 4,99
    0069 BATATA DOCE                                7,93
    1,135 KG 6,99
    ...
    VALOR TOTAL:                                   36,50
    FORMA DE PAGTO
    Cartao Debito                                  36,50

Estratégia (robusta a erros do OCR):
  * a COLUNA DE TOTAIS (à direita) é a âncora: cada item tem um total, e a soma
    deles bate com o "VALOR TOTAL". Casar nome↔total por ORDEM vertical (as duas
    colunas vêm completas e em ordem, mesmo quando o OCR embaralha as linhas).
  * a linha de quantidade ("0,775 KG 4,99") é casada ao item por ARITMÉTICA
    (qtd × unit == total do item), porque às vezes o OCR engole uma delas.
  * o OCR às vezes lê o zero inicial do código como a letra "O" (OOO6 -> 0006):
    normaliza O->0 no código.

Nada aqui grava: devolve o mesmo "cupom lido" que a tela de revisão já conhece
(ver cupons.py), para o João conferir/corrigir ANTES de salvar. OCR erra dígito
ou acento de vez em quando; a revisão na tela é a rede de segurança.

O motor de OCR (rapidocr-onnxruntime) é uma dependência OPCIONAL e pesada, à parte
do requirements.txt, para não inchar o app comum nem o .exe. A leitura do layout
(`montar_cupom`) é pura (só `re`) e não depende do motor — por isso dá para testá-la.
"""
from __future__ import annotations

import re

from .cupons import CupomInvalido

# Extensões que esta leitura aceita (foto do cupom ou PDF que é imagem).
EXTENSOES = (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".bmp")

_INSTALAR = ("A leitura de cupom por foto precisa do pacote de OCR (grátis, offline). "
             "Rode uma vez o script scripts\\ler_cupom_por_foto.bat e tente de novo.")


def suporta(nome: str) -> bool:
    return nome.lower().endswith(EXTENSOES)


# --------------------------------------------------------------------- números
def _centavos(texto: str) -> int:
    s = texto.strip().replace(" ", "")
    if "," in s and "." in s:            # 1.234,56
        s = s.replace(".", "").replace(",", ".")
    else:                                 # 36.50  ou  3,86
        s = s.replace(",", ".")
    return round(float(s) * 100)


def _milesimos(texto: str) -> int:
    s = texto.strip().replace(" ", "").replace(",", ".")
    if "." not in s and len(s) > 3:       # "1130" veio sem o ponto -> 1.130
        s = f"{s[:-3]}.{s[-3:]}"
    return round(float(s) * 1000)


def _codigo(texto: str) -> str:
    return re.sub(r"[Oo]", "0", texto)    # zero inicial lido como letra O


# Linhas do corpo do cupom.
_NOME = re.compile(r"^([O0o\d]{3,4})\s+([A-Za-zÀ-Ÿ].*)$")          # "0103 CENOURA"
_QTD = re.compile(r"(\d+[.,]?\d{0,3})\s*(KG|UN)\s*(\d+[.,]\d{1,2})", re.I)  # "0,775KG4,99"
_DINHEIRO = re.compile(r"^\d{1,3}[.,]\d{2}$")                       # "3,86"
_EMISSAO = re.compile(r"Emiss[aã]o:?\s*(\d{2})/(\d{2})/(\d{4})\s*(\d{2}:\d{2})?", re.I)
_NUMERO = re.compile(r"N[o0ºO]\.?\s*0*(\d+)")
_CIDADE_UF = re.compile(r"^(.+?)\s*[-–]\s*([A-Z]{2})$")


def montar_cupom(dets: list[dict]) -> dict:
    """Recebe as caixas do OCR [{t, x, y}] e devolve o "cupom lido".

    t = texto, x/y = centro da caixa (em pixels). Função pura: sem dependências
    pesadas, para poder ser testada com caixas sintéticas.
    """
    if not dets:
        raise CupomInvalido("Não consegui ler texto nenhum na imagem do cupom.")
    maxx = max(d["x"] for d in dets)
    col_dir = 0.55 * maxx                 # coluna da direita (totais)

    # Região dos itens: do cabeçalho ("Total"/"Unit") até o "VALOR TOTAL".
    y_ini = max([d["y"] for d in dets if d["t"].strip().lower() in ("total", "unit")] + [0.0])
    vt = [d for d in dets if "VALOR TOTAL" in d["t"].upper()]
    y_fim = min([d["y"] for d in vt] + [max(d["y"] for d in dets) + 1])
    reg = [d for d in dets if y_ini < d["y"] < y_fim]

    nomes = sorted((d for d in reg if _NOME.match(d["t"])
                    and not _QTD.search(d["t"].replace(" ", ""))),   # não é linha de quantidade
                   key=lambda d: d["y"])
    totais = sorted((d for d in reg if _DINHEIRO.match(d["t"]) and d["x"] > col_dir),
                    key=lambda d: d["y"])
    qtds = sorted((d for d in reg if _QTD.search(d["t"].replace(" ", "")) and d["x"] <= col_dir),
                  key=lambda d: d["y"])

    itens: list[dict] = []
    for seq, (nome, total) in enumerate(zip(nomes, totais), start=1):
        m = _NOME.match(nome["t"])
        itens.append({
            "seq": seq,
            "descricao": re.sub(r"\s+", " ", m.group(2)).strip(),
            "codigo": _codigo(m.group(1)),
            "valor_total_centavos": _centavos(total["t"]),
            "quantidade_milesimos": None,   # preenchido abaixo, se casar
            "unidade": None,
            "preco_unitario_centavos": None,
            "desconto_centavos": 0,
        })
    if not itens:
        raise CupomInvalido("Não reconheci os itens do cupom. Tire a foto reta, com boa "
                            "luz e o cupom inteiro no quadro, e tente de novo.")

    # Casa cada linha de quantidade ao item cujo total = qtd × preço unitário.
    usados: set[int] = set()
    for q in qtds:
        mq = _QTD.search(q["t"].replace(" ", ""))
        qtd_mil = _milesimos(mq.group(1))
        unid = mq.group(2).upper()
        unit = _centavos(mq.group(3))
        alvo = round(qtd_mil * unit / 1000)
        cand = [k for k, it in enumerate(itens)
                if k not in usados and abs(it["valor_total_centavos"] - alvo) <= 2]
        if cand:
            k = min(cand, key=lambda k: abs(itens[k]["valor_total_centavos"] - alvo))
            usados.add(k)
            itens[k].update(quantidade_milesimos=qtd_mil, unidade=unid,
                            preco_unitario_centavos=unit)

    # Item sem quantidade lida: trata como 1 unidade ao preço do total (o João ajusta).
    for it in itens:
        if it["quantidade_milesimos"] is None:
            it.update(quantidade_milesimos=1000, unidade="UN",
                      preco_unitario_centavos=it["valor_total_centavos"])

    bruto = sum(it["valor_total_centavos"] for it in itens)
    total_cupom = _centavos(_perto_de(dets, vt[0], col_dir)) if vt else None

    return {
        "origem": "foto",
        "tipo_documento": "pedido",
        "chave": None,
        "emitente": _emitente(dets),
        "numero": _numero(dets),
        "serie": None,
        "emissao": _emissao(dets),
        "itens": itens,
        "valor_total_centavos": bruto,
        "desconto_centavos": 0,
        "valor_pagar_centavos": total_cupom if total_cupom else bruto,
    }


def _perto_de(dets: list[dict], ref: dict, col_dir: float) -> str:
    """Token de dinheiro da coluna da direita mais próximo (em y) de `ref`."""
    cand = [d for d in dets if _DINHEIRO.match(d["t"]) and d["x"] > col_dir
            and abs(d["y"] - ref["y"]) < 70]
    return min(cand, key=lambda d: abs(d["y"] - ref["y"]))["t"] if cand else "0"


def _emitente(dets: list[dict]) -> dict:
    nome = next((d["t"] for d in dets if "FRESCOR" in d["t"].upper()), None)
    if not nome:
        nome = min(dets, key=lambda d: d["y"])["t"] if dets else ""
    cidade = uf = None
    for d in dets:
        m = _CIDADE_UF.match(d["t"].strip())
        if m:
            cidade, uf = m.group(1).strip(), m.group(2)
            break
    return {"nome": re.sub(r"\s+", " ", nome).strip(), "cnpj": None, "cidade": cidade, "uf": uf}


def _numero(dets: list[dict]) -> str | None:
    for d in dets:
        m = _NUMERO.search(d["t"])
        if m:
            return m.group(1)
    return None


def _emissao(dets: list[dict]) -> str | None:
    for d in dets:
        m = _EMISSAO.search(d["t"])
        if m:
            hora = m.group(4) or "00:00"
            return f"{m.group(3)}-{m.group(2)}-{m.group(1)}T{hora}"
    return None


# --------------------------------------------------------------------- imagem + OCR
def ler(nome: str, conteudo: bytes) -> dict:
    """Extrai a imagem (de um PDF-foto ou de um arquivo de imagem), roda o OCR e monta o cupom."""
    imagem = _imagem(nome, conteudo)
    return montar_cupom(_ocr(imagem))


def _imagem(nome: str, conteudo: bytes):
    """Devolve a imagem como ndarray RGB (o motor de OCR foi treinado em RGB)."""
    from io import BytesIO

    import numpy as np
    from PIL import Image

    if nome.lower().endswith(".pdf"):
        from pypdf import PdfReader
        try:
            leitor = PdfReader(BytesIO(conteudo))
            fotos = [img for pag in leitor.pages for img in getattr(pag, "images", [])]
        except Exception as e:                       # noqa: BLE001 - pypdf lança vários tipos
            raise CupomInvalido(f"Não consegui abrir o PDF: {e}") from e
        if not fotos:
            raise CupomInvalido("Este PDF não tem imagem de cupom. Se for a página da SEFAZ, "
                                "salve-a como .html; se for um pedido, mande a foto (.jpg/.png).")
        maior = max(fotos, key=lambda f: getattr(f.image, "width", 0) * getattr(f.image, "height", 0))
        return np.array(maior.image.convert("RGB"))

    try:
        return np.array(Image.open(BytesIO(conteudo)).convert("RGB"))
    except Exception as e:                           # noqa: BLE001 - Pillow lança vários tipos
        raise CupomInvalido("Não consegui abrir a imagem. Use um arquivo .jpg, .png ou .pdf.") from e


def _ocr(imagem) -> list[dict]:
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as e:
        raise CupomInvalido(_INSTALAR) from e
    resultado, _ = RapidOCR()(imagem)
    dets = []
    for caixa, texto, _score in (resultado or []):
        xs = [p[0] for p in caixa]
        ys = [p[1] for p in caixa]
        dets.append({"t": (texto or "").strip(), "x": sum(xs) / 4, "y": sum(ys) / 4})
    return dets
