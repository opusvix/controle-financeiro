"""Leitura de cupom por foto (OCR local): o PARSER do layout, sem o motor de OCR.

As "caixas" ({t, x, y}) imitam o que o rapidocr devolve na foto de um pedido da
Frescor. Assim dá para testar a lógica (casar item↔total, quantidade por aritmética,
normalizar código) sem depender do pacote pesado de OCR nem de uma imagem real.
"""
import sys

import pytest

from app.services import cupom_ocr
from app.services.cupons import CupomInvalido


def _d(t, x, y):
    return {"t": t, "x": x, "y": y}


# Cabeçalho (Total) marca o começo; VALOR TOTAL marca o fim. Totais à direita (x grande).
CABECALHO = _d("Total", 1500, 100)


def test_parser_casa_itens_normaliza_codigo_e_confere_total():
    dets = [
        CABECALHO,
        _d("0103 CENOURA", 300, 200), _d("0,775KG4,99", 320, 230), _d("3,87", 1500, 215),
        _d("OOO6 LARANJA PERA", 300, 300), _d("2,565KG3,49", 320, 330), _d("8,95", 1500, 315),
        _d("VALOR TOTAL:", 300, 400), _d("12,82", 1500, 400),
    ]
    cupom = cupom_ocr.montar_cupom(dets)
    assert cupom["origem"] == "foto" and cupom["tipo_documento"] == "pedido"
    assert [i["descricao"] for i in cupom["itens"]] == ["CENOURA", "LARANJA PERA"]
    assert [i["codigo"] for i in cupom["itens"]] == ["0103", "0006"]   # OOO6 -> 0006
    cen = cupom["itens"][0]
    assert (cen["quantidade_milesimos"], cen["unidade"], cen["preco_unitario_centavos"]) == (775, "KG", 499)
    assert cen["valor_total_centavos"] == 387
    assert cupom["valor_pagar_centavos"] == 1282
    assert sum(i["valor_total_centavos"] for i in cupom["itens"]) == cupom["valor_pagar_centavos"]


def test_item_sem_quantidade_lida_vira_uma_unidade_ao_preco_do_total():
    # O OCR engoliu a linha de quantidade da CENOURA (acontece): o total ainda vem.
    dets = [
        CABECALHO,
        _d("0103 CENOURA", 300, 200), _d("3,87", 1500, 215),
        _d("OOO6 LARANJA PERA", 300, 300), _d("2,565KG3,49", 320, 330), _d("8,95", 1500, 315),
        _d("VALOR TOTAL:", 300, 400), _d("12,82", 1500, 400),
    ]
    cupom = cupom_ocr.montar_cupom(dets)
    cen = cupom["itens"][0]
    assert cen["quantidade_milesimos"] == 1000 and cen["unidade"] == "UN"
    assert cen["preco_unitario_centavos"] == cen["valor_total_centavos"] == 387   # editável na tela
    assert sum(i["valor_total_centavos"] for i in cupom["itens"]) == 1282


def test_linha_de_quantidade_nao_vira_nome_de_item():
    # OCR às vezes perde o ponto: "0,530KG3,99" -> "0530 KG3.99", que parece "código nome".
    dets = [
        CABECALHO,
        _d("0098 ABOBORA", 300, 200), _d("0,530KG3,99", 320, 230), _d("2,11", 1500, 215),
        _d("0530 KG3.99", 320, 232),   # lixo do OCR: NÃO pode virar item
        _d("VALOR TOTAL:", 300, 400), _d("2,11", 1500, 400),
    ]
    cupom = cupom_ocr.montar_cupom(dets)
    assert len(cupom["itens"]) == 1
    assert cupom["itens"][0]["descricao"] == "ABOBORA"


def test_emitente_numero_e_emissao_saem_do_cabecalho():
    dets = [
        _d("FRESCOR REAL HORTIFRUTI", 800, 20), _d("VILA VELHA - ES", 350, 40),
        _d("No.000148923", 1400, 60), _d("Emissao:09/11/2026 10:22", 550, 80),
        CABECALHO,
        _d("0103 CENOURA", 300, 200), _d("0,775KG4,99", 320, 230), _d("3,87", 1500, 215),
        _d("VALOR TOTAL:", 300, 400), _d("3,87", 1500, 400),
    ]
    cupom = cupom_ocr.montar_cupom(dets)
    assert "FRESCOR" in cupom["emitente"]["nome"]
    assert (cupom["emitente"]["cidade"], cupom["emitente"]["uf"]) == ("VILA VELHA", "ES")
    assert cupom["numero"] == "148923"
    assert cupom["emissao"] == "2026-11-09T10:22"


def test_imagem_vazia_recusada():
    with pytest.raises(CupomInvalido):
        cupom_ocr.montar_cupom([])


def test_suporta_reconhece_foto_e_pdf_mas_nao_html():
    assert cupom_ocr.suporta("pedido.JPG") and cupom_ocr.suporta("nota.pdf")
    assert cupom_ocr.suporta("foto.png") and cupom_ocr.suporta("x.webp")
    assert not cupom_ocr.suporta("pagina.html") and not cupom_ocr.suporta("dados.json")


def test_ler_arquivo_manda_foto_para_o_ocr(monkeypatch):
    from app.services import cupons
    monkeypatch.setattr(cupom_ocr, "ler", lambda nome, conteudo: {"origem": "foto", "itens": []})
    assert cupons.ler_arquivo("pedido.png", b"\x89PNG...")["origem"] == "foto"


def test_sem_pacote_de_ocr_a_mensagem_ensina_a_instalar(monkeypatch):
    # Simula o pacote de OCR ausente: a mensagem precisa apontar o script de instalação.
    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", None)
    with pytest.raises(CupomInvalido) as e:
        cupom_ocr._ocr(object())
    assert "ler_cupom_por_foto.bat" in str(e.value)
