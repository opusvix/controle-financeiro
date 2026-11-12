"""Primeira vez no .exe: lógica de onde guardar os dados (sem janela/GUI)."""
from pathlib import Path

import pytest

from app import config as config_mod
from app import pasta_dados


@pytest.fixture
def ao_lado(tmp_path, monkeypatch):
    """Finge que o .exe mora em tmp_path (onde fica o bilhete) e limpa o ambiente."""
    monkeypatch.setattr(config_mod, "_PASTA_PADRAO", tmp_path)
    monkeypatch.delenv("CF_PASTA_DADOS", raising=False)
    monkeypatch.delenv("CF_PASTA_BACKUP", raising=False)
    return tmp_path


def test_sem_bilhete_nao_ha_pasta_salva(ao_lado):
    assert pasta_dados.pasta_salva() is None


def test_salvar_e_ler_a_escolha(ao_lado):
    escolhida = Path("D:/Dados/ControleFinanceiro")
    pasta_dados.salvar_escolha(escolhida)
    assert pasta_dados.pasta_salva() == escolhida
    assert (ao_lado / pasta_dados.BILHETE).read_text(encoding="utf-8").strip() == str(escolhida)


def test_pergunta_na_primeira_vez_do_exe_normal(ao_lado):
    assert pasta_dados.precisa_perguntar(empacotado=True, modo_demo=False) is True


def test_nao_pergunta_fora_do_exe(ao_lado):
    # Modo desenvolvimento (rodando do código): usa a pasta do repo, sem perguntar.
    assert pasta_dados.precisa_perguntar(empacotado=False, modo_demo=False) is False


def test_nao_pergunta_na_demonstracao(ao_lado):
    assert pasta_dados.precisa_perguntar(empacotado=True, modo_demo=True) is False


def test_nao_pergunta_se_ja_escolheu_antes(ao_lado):
    pasta_dados.salvar_escolha(ao_lado / "ControleFinanceiro")
    assert pasta_dados.precisa_perguntar(empacotado=True, modo_demo=False) is False


def test_nao_pergunta_se_o_ambiente_ja_define_a_pasta(ao_lado, monkeypatch):
    monkeypatch.setenv("CF_PASTA_DADOS", str(ao_lado / "qualquer"))
    assert pasta_dados.precisa_perguntar(empacotado=True, modo_demo=False) is False


def test_aplicar_define_dados_e_backup_sem_sobrescrever(ao_lado, monkeypatch):
    pasta = Path("D:/Dados/CF")
    pasta_dados.aplicar(pasta)
    import os
    assert os.environ["CF_PASTA_DADOS"] == str(pasta)
    assert os.environ["CF_PASTA_BACKUP"] == str(pasta / "BackUp")
    # Não sobrescreve uma escolha anterior do usuário.
    monkeypatch.setenv("CF_PASTA_DADOS", "D:/OutroLugar")
    pasta_dados.aplicar(pasta)
    assert os.environ["CF_PASTA_DADOS"] == "D:/OutroLugar"


def test_pasta_sugerida_usa_documentos_quando_existe(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    (tmp_path / "Documents").mkdir()
    assert pasta_dados.pasta_sugerida() == tmp_path / "Documents" / "ControleFinanceiro"


def test_pasta_sugerida_cai_na_casa_quando_nao_ha_documentos(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    assert pasta_dados.pasta_sugerida() == tmp_path / "ControleFinanceiro"
