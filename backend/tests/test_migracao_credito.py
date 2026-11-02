import sqlite3

from app import db, seed


def test_migracao_004_preserva_dados_e_faz_copia(tmp_path):
    arquivo = tmp_path / "financeiro.db"
    con = db.conectar(str(arquivo))
    # Aplica só até a 003, como está no PC hoje.
    todas = sorted(db.PASTA_MIGRACOES.glob("*.sql"))
    con.execute("CREATE TABLE _migracao (nome TEXT PRIMARY KEY, aplicada_em TEXT NOT NULL DEFAULT (datetime('now')))")
    for a in todas:
        if a.name.startswith("004"):
            break
        con.executescript(a.read_text(encoding="utf-8"))
        con.execute("INSERT INTO _migracao (nome) VALUES (?)", (a.name,))
    con.commit()
    seed.popular(con)
    with con:
        conta = con.execute("INSERT INTO conta (nome, tipo, saldo_inicial_centavos, data_saldo_inicial) "
                            "VALUES ('C6', 'corrente', 0, '2026-01-01')").lastrowid
        t = con.execute("INSERT INTO transacao (tipo, descricao, valor_centavos, data, conta_id) "
                        "VALUES ('despesa', 'Pão', 500, '2026-10-01', ?)", (conta,)).lastrowid
        tag = con.execute("INSERT INTO tag (nome) VALUES ('CERCO FELINO')").lastrowid
        con.execute("INSERT INTO transacao_tag VALUES (?, ?)", (t, tag))
    assert db.migrar(con)[0] == "004_credito_cartao.sql"
    assert (tmp_path / "financeiro.antes-004_credito_cartao.db").exists()
    assert con.execute("SELECT descricao FROM transacao WHERE id = ?", (t,)).fetchone()[0] == "Pão"
    assert con.execute("SELECT COUNT(*) FROM transacao_tag").fetchone()[0] == 1
    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    con.execute("SELECT * FROM v_preco").fetchall()
    # Apagar a transação ainda apaga as tags (FK com cascade continua valendo).
    with con:
        con.execute("DELETE FROM transacao WHERE id = ?", (t,))
    assert con.execute("SELECT COUNT(*) FROM transacao_tag").fetchone()[0] == 0
    con.close()
    assert sqlite3.connect(arquivo).execute("SELECT COUNT(*) FROM _migracao").fetchone()[0] == len(todas)
