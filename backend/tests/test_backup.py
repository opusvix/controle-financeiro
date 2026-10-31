from datetime import datetime, timedelta

from app.services import backup


def test_rotacao_guarda_7_dias_4_semanas_12_meses():
    agora = datetime(2026, 10, 31, 2, 0)
    # um backup por dia durante 2 anos
    momentos = [agora - timedelta(days=d) for d in range(730)]
    mantidos = backup.escolher_mantidos(momentos)
    assert all(agora - timedelta(days=d) in mantidos for d in range(7))
    assert len({d.date() for d in mantidos}) <= 7 + 4 + 12
    assert min(mantidos) >= datetime(2025, 11, 1)  # nada além de ~12 meses


def test_backup_real_copia_banco_e_vai_para_o_drive(con, tmp_path):
    local, drive = tmp_path / "BackUp", tmp_path / "Drive"
    r = backup.executar(con, local, drive, agora=datetime(2026, 10, 31, 2, 0))
    assert r["copiado_drive"] and r["bytes"] > 0
    assert (local / "financeiro_20261031_020000.db").exists()
    assert (drive / "financeiro_20261031_020000.db").exists()
    assert backup.ultimo(con)["arquivo"] == "financeiro_20261031_020000.db"


def test_drive_indisponivel_nao_impede_backup_local(con, tmp_path):
    arquivo_no_lugar_da_pasta = tmp_path / "G"
    arquivo_no_lugar_da_pasta.write_text("x")
    r = backup.executar(con, tmp_path / "BackUp", arquivo_no_lugar_da_pasta / "sub")
    assert not r["copiado_drive"]
    assert (tmp_path / "BackUp").glob("financeiro_*.db")
