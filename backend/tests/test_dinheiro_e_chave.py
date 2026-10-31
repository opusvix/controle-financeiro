import pytest

from app.money import formatar, para_centavos
from app.services import nfce

# Chaves reais dos cupons de outubro/2026 (QR Code lido das imagens em Notas/).
PERIM_0910 = "32261006955576000512651210003769891613257499"
PADARIA_2110 = "32261005932696000108650130003794301133794308"
URL_PADARIA = ("﻿http://app.sefaz.es.gov.br/ConsultaNFCe/qrcode.aspx?p="
               f"{PADARIA_2110}|2|1|1|C9E7549C4DE840FC241F7D2A7BF993924BD54B5C")


@pytest.mark.parametrize("entrada,esperado", [
    ("8,98", 898), ("1.234,56", 123456), ("R$ 375,06", 37506), (8.98, 898), (0.1 + 0.2, 30), (5, 500),
])
def test_para_centavos(entrada, esperado):
    assert para_centavos(entrada) == esperado


def test_formatar():
    assert formatar(37506) == "R$ 375,06"
    assert formatar(1962796) == "R$ 19.627,96"
    assert formatar(-1000) == "-R$ 10,00"


def test_chave_perim_bate_com_o_cupom_impresso():
    k = nfce.interpretar_chave(PERIM_0910)
    assert k.valida
    assert (k.uf, k.ano_mes, k.cnpj, k.modelo) == ("ES", "2026-10", "06955576000512", "65")
    assert (k.serie, k.numero) == (121, 376989)  # impresso: "N.:376989 Serie:121"


def test_chave_da_url_do_qr_com_bom():
    assert nfce.chave_da_url(URL_PADARIA) == PADARIA_2110
    assert nfce.interpretar_chave(PADARIA_2110).numero == 379430  # "NFC-e nº 000379430"


def test_chave_com_digito_errado_e_invalida():
    errada = PERIM_0910[:-1] + "0"
    assert not nfce.interpretar_chave(errada).valida


def test_chave_curta_e_recusada():
    with pytest.raises(ValueError):
        nfce.interpretar_chave("3226 1006")
