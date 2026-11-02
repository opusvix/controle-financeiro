from datetime import date

from openpyxl import Workbook

from app.importacao import mobills_cartoes as m
from app.services import painel
from app.services.transacoes import NovaTransacao, criar

MAPA = {"tag_ignorar": "ignorar transação"}


def _xlsx(tmp_path, linhas):
    wb = Workbook()
    ws = wb.active
    ws.title = "Despesas"
    ws.append(["Data", "Descrição", "Valor", "Conta", "Situação", "Categoria", "Subcategoria", "Tags"])
    for ln in linhas:
        ws.append(ln)
    ws.append([None] * 8)
    ws.append(["Total (despesas)", None, -1, None, None, None, None, None])
    arq = tmp_path / "cartoes.xlsx"
    wb.save(arq)
    return arq


def _cenario(con):
    with con:
        conta = con.execute("INSERT INTO conta (nome, tipo, saldo_inicial_centavos, data_saldo_inicial) "
                            "VALUES ('1 - C6 Bank 1118', 'corrente', 100000, '2026-01-01')").lastrowid
        cartao = con.execute("INSERT INTO cartao (nome, bandeira, final, dia_fechamento, dia_vencimento, "
                             "conta_pagamento_id) VALUES ('C6 MAU 1118', 'Mastercard', '1118', 28, 10, ?)",
                             (conta,)).lastrowid
    # Como veio do relatório de transações: itens da fatura como despesa da conta no dia 10.
    for desc, valor in [("DL GOOGLE", 999), ("PERIM ", 12975)]:
        criar(con, NovaTransacao("despesa", desc, valor, date(2026, 10, 10), conta_id=conta))
    criar(con, NovaTransacao("despesa_cartao", "PADARIA IDEAL LTDA", 2917, date(2026, 10, 21),
                             cartao_id=cartao))  # lançado pelo app (cupom)
    return conta, cartao


def test_converte_sem_mudar_saldo_e_importa_futuras(con, tmp_path):
    conta, cartao = _cenario(con)
    arq = _xlsx(tmp_path, [
        ["10/10/2026", "DL GOOGLE", -9.99, "1 - C6 Bank 1118", "Paga", "Serviços", None, ""],
        ["10/10/2026", "PERIM", -129.75, "1 - C6 Bank 1118", "Paga", "Mercado", None, ""],
        ["10/11/2026", "PADARIA NOVA DELLI", -29.17, "1 - C6 Bank 1118", "Pendente", "Casa", None, ""],
        ["10/12/2026", "MELI - POWER BANK - 12x (3/12)", -6.87, "1 - C6 Bank 1118", "Pendente", None, None,
         "ignorar transação"],
        ["10/12/2026", "MELI - POWER BANK - 12x (4/12)", -6.87, "1 - C6 Bank 1118", "Pendente", None, None, ""],
        ["10/10/2026", "OPUS", -50, "C6 - OpusVix", "Paga", None, None, ""],
    ])
    saldo = painel.saldos_contas(con)[0]["saldo_atual"]
    rel, texto = m.executar(con, arq, MAPA)
    assert sum(rel.convertidos.values()) == 2 and sum(rel.novos.values()) == 2
    assert rel.sem_cartao == {"C6 - OpusVix": 1} and len(rel.duplicatas) == 1
    assert painel.saldos_contas(con)[0]["saldo_atual"] == saldo
    assert "Todos os saldos ficaram iguais." in texto
    out = con.execute("SELECT valor_centavos FROM transacao WHERE tipo = 'pagamento_fatura'").fetchall()
    assert [r[0] for r in out] == [999 + 12975]
    dez = con.execute("""SELECT t.ignorar, t.parcela FROM transacao t JOIN fatura f ON f.id = t.fatura_id
                         WHERE f.competencia = '2026-12' ORDER BY t.parcela""").fetchall()
    assert [tuple(r) for r in dez] == [(1, 3), (0, 4)]
    # Rodar de novo não muda nada.
    rel2, _ = m.executar(con, arq, MAPA)
    assert sum(rel2.convertidos.values()) == 0 and sum(rel2.novos.values()) == 0
    assert rel2.ja_estavam == 4
    assert con.execute("SELECT COUNT(*) FROM transacao WHERE tipo = 'pagamento_fatura'").fetchone()[0] == 1


def test_simulacao_nao_grava(con, tmp_path):
    _cenario(con)
    arq = _xlsx(tmp_path, [["10/10/2026", "DL GOOGLE", -9.99, "1 - C6 Bank 1118", "Paga", None, None, ""]])
    m.executar(con, arq, MAPA, simular=True)
    assert con.execute("SELECT COUNT(*) FROM transacao WHERE tipo = 'despesa'").fetchone()[0] == 2


def test_conta_sem_cartao_no_mapa_fica_como_esta(con, tmp_path):
    _cenario(con)
    arq = _xlsx(tmp_path, [["10/10/2026", "DL GOOGLE", -9.99, "1 - C6 Bank 1118", "Paga", None, None, ""]])
    rel, _ = m.executar(con, arq, {**MAPA, "contas_sem_cartao": ["1 - c6 bank 1118"]})
    assert rel.sem_cartao == {"1 - C6 Bank 1118": 1} and not rel.convertidos
