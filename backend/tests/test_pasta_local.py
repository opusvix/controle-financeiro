"""Campos "pasta que lembra o último local": listar arquivos de uma pasta do PC e
ler UM arquivo de dentro dela (Conciliação, Conciliação de Fatura e Cupom)."""
import pytest

from app.services import cupons, pasta_local
from tests.test_conciliacao_fatura import FATURA, _cartao, _compra


# --------------------------------------------------------------- unidade (pasta_local)
def test_listar_filtra_por_extensao(tmp_path):
    (tmp_path / "jan.ofx").write_bytes(b"x")
    (tmp_path / "fev.OFX").write_bytes(b"x")   # extensão em maiúsculas conta
    (tmp_path / "leia.txt").write_bytes(b"x")  # fora do filtro
    pasta, nomes = pasta_local.listar(str(tmp_path), [".ofx"])
    assert nomes == ["fev.OFX", "jan.ofx"]


def test_listar_pasta_inexistente_avisa(tmp_path):
    with pytest.raises(Exception) as e:
        pasta_local.listar(str(tmp_path / "nao-existe"), [".ofx"])
    assert e.value.status_code == 422


def test_ler_arquivo_recusa_escapar_da_pasta(tmp_path):
    (tmp_path / "ok.csv").write_bytes(b"conteudo")
    for nome in ["../segredo.csv", "sub/ok.csv", "..\\x.csv", "..", "."]:
        with pytest.raises(Exception) as e:
            pasta_local.ler_arquivo(str(tmp_path), nome, [".csv"])
        assert e.value.status_code == 422


def test_ler_arquivo_recusa_extensao_fora_da_lista(tmp_path):
    (tmp_path / "foto.exe").write_bytes(b"x")
    with pytest.raises(Exception) as e:
        pasta_local.ler_arquivo(str(tmp_path), "foto.exe", [".png", ".pdf"])
    assert e.value.status_code == 422


def test_ler_arquivo_devolve_nome_e_bytes(tmp_path):
    (tmp_path / "nota.pdf").write_bytes(b"%PDF-1.4 ...")
    nome, conteudo = pasta_local.ler_arquivo(str(tmp_path), "nota.pdf", [".pdf"])
    assert nome == "nota.pdf" and conteudo == b"%PDF-1.4 ..."


# ----------------------------------------------------------------- endpoint genérico
def test_endpoint_listar_arquivos(cliente, tmp_path):
    (tmp_path / "a.csv").write_bytes(b"x")
    (tmp_path / "b.pdf").write_bytes(b"x")
    (tmp_path / "c.zip").write_bytes(b"x")
    r = cliente.post("/api/arquivos/listar",
                     json={"pasta": str(tmp_path), "extensoes": [".csv", ".pdf"]})
    assert r.status_code == 200
    assert r.json()["arquivos"] == ["a.csv", "b.pdf"]


# ------------------------------------------------------- endpoint da fatura (por pasta)
def test_endpoint_fatura_analisar_da_pasta(cliente, tmp_path):
    cartao = _cartao(cliente)
    _compra(cliente, cartao, "Pneus Mauri 6x (5/6)", 36766)   # casa com a fatura
    (tmp_path / "C6-Fatura_2026-11-10.csv").write_bytes(FATURA)
    r = cliente.post("/api/conciliacao/fatura/analisar-pasta",
                     json={"pasta": str(tmp_path), "arquivo": "C6-Fatura_2026-11-10.csv",
                           "cartao_id": cartao, "competencia": "2026-11"})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["arquivo"] == "C6-Fatura_2026-11-10.csv"
    assert "casados" in corpo


# ------------------------------------------------------- endpoint do cupom (por pasta)
def test_endpoint_cupom_ler_da_pasta(cliente, tmp_path, monkeypatch):
    # Evita o motor de OCR nos testes: troca o leitor por um dublê e confere a "fiação"
    # (ler o arquivo certo da pasta → passar ao leitor → devolver com o nome do arquivo).
    (tmp_path / "cupom.png").write_bytes(b"\x89PNG finge-foto")
    visto = {}

    def fake_ler(nome, conteudo):
        visto["nome"], visto["bytes"] = nome, conteudo
        return {"itens": [], "valor_pagar_centavos": 0}

    monkeypatch.setattr(cupons, "ler_arquivo", fake_ler)
    monkeypatch.setattr(cupons, "preparar", lambda c, cupom: {"cupom": cupom})

    r = cliente.post("/api/cupons/ler-da-pasta",
                     json={"pasta": str(tmp_path), "arquivo": "cupom.png"})
    assert r.status_code == 200, r.text
    assert r.json()["arquivo"] == "cupom.png"
    assert visto["nome"] == "cupom.png" and visto["bytes"] == b"\x89PNG finge-foto"


def test_endpoint_cupom_recusa_arquivo_de_outro_tipo(cliente, tmp_path):
    (tmp_path / "planilha.xlsx").write_bytes(b"x")
    r = cliente.post("/api/cupons/ler-da-pasta",
                     json={"pasta": str(tmp_path), "arquivo": "planilha.xlsx"})
    assert r.status_code == 422
