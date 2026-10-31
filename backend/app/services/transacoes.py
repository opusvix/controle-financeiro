"""Criação de transações com as regras de cada tipo."""
from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import date

from . import faturas

TIPOS = ("receita", "despesa", "despesa_cartao", "transferencia", "pagamento_fatura", "ajuste")

# Efeito no saldo da conta, em SQL. Usado por saldos e relatórios.
EFEITO_SQL = """
CASE t.tipo
    WHEN 'receita' THEN t.valor_centavos
    WHEN 'despesa' THEN -t.valor_centavos
    WHEN 'pagamento_fatura' THEN -t.valor_centavos
    WHEN 'transferencia' THEN CASE WHEN t.entrada = 1 THEN t.valor_centavos ELSE -t.valor_centavos END
    WHEN 'ajuste' THEN CASE WHEN t.ajuste_negativo = 1 THEN -t.valor_centavos ELSE t.valor_centavos END
    ELSE 0
END
"""


@dataclass
class NovaTransacao:
    tipo: str
    descricao: str
    valor_centavos: int
    data: date
    pago: bool = True
    conta_id: int | None = None
    conta_destino_id: int | None = None      # transferência
    cartao_id: int | None = None
    parcelas: int = 1                         # despesa_cartao parcelada
    fatura_competencia: str | None = None     # pagamento_fatura: 'AAAA-MM'
    categoria_id: int | None = None
    estabelecimento_id: int | None = None
    documento_id: int | None = None
    ajuste_negativo: bool = False
    ignorar: bool = False
    observacao: str | None = None
    tags: list[int] = field(default_factory=list)


class RegraViolada(ValueError):
    """Dados que quebram uma regra de negócio (vira HTTP 422)."""


def _validar(n: NovaTransacao) -> None:
    if n.tipo not in TIPOS:
        raise RegraViolada(f"Tipo inválido: {n.tipo}")
    if n.valor_centavos <= 0:
        raise RegraViolada("O valor deve ser maior que zero")
    if n.tipo == "despesa_cartao":
        if not n.cartao_id:
            raise RegraViolada("Despesa de cartão precisa do cartão")
        if n.parcelas < 1:
            raise RegraViolada("Parcelas deve ser 1 ou mais")
    elif not n.conta_id:
        raise RegraViolada("Informe a conta")
    if n.tipo == "transferencia":
        if not n.conta_destino_id or n.conta_destino_id == n.conta_id:
            raise RegraViolada("Transferência precisa de uma conta de destino diferente")
    if n.tipo == "pagamento_fatura" and not n.cartao_id:
        raise RegraViolada("Pagamento de fatura precisa do cartão")


def _inserir(con: sqlite3.Connection, **campos) -> int:
    colunas = ", ".join(campos)
    marcas = ", ".join("?" for _ in campos)
    return con.execute(
        f"INSERT INTO transacao ({colunas}) VALUES ({marcas})", tuple(campos.values())
    ).lastrowid


def _fatura_a_pagar(con: sqlite3.Connection, n: NovaTransacao) -> int:
    """Fatura informada, ou a última já fechada até a data do pagamento."""
    if n.fatura_competencia:
        linha = con.execute(
            "SELECT id FROM fatura WHERE cartao_id = ? AND competencia = ?",
            (n.cartao_id, n.fatura_competencia),
        ).fetchone()
    else:
        linha = con.execute(
            "SELECT id FROM fatura WHERE cartao_id = ? AND data_fechamento <= ? "
            "ORDER BY data_fechamento DESC LIMIT 1",
            (n.cartao_id, n.data.isoformat()),
        ).fetchone()
    if linha is None:
        raise RegraViolada("Não há fatura fechada para pagar neste cartão")
    return linha["id"]


def criar(con: sqlite3.Connection, n: NovaTransacao) -> list[int]:
    """Grava a transação e devolve os ids criados (2 na transferência, N nas parcelas)."""
    _validar(n)
    base = dict(
        descricao=n.descricao.strip(),
        pago=int(n.pago),
        categoria_id=n.categoria_id,
        estabelecimento_id=n.estabelecimento_id,
        documento_id=n.documento_id,
        ignorar=int(n.ignorar),
        observacao=n.observacao,
    )
    ids: list[int] = []
    with con:
        if n.tipo == "transferencia":
            saida = _inserir(con, tipo="transferencia", valor_centavos=n.valor_centavos,
                             data=n.data.isoformat(), conta_id=n.conta_id, entrada=0, **base)
            entrada = _inserir(con, tipo="transferencia", valor_centavos=n.valor_centavos,
                               data=n.data.isoformat(), conta_id=n.conta_destino_id,
                               entrada=1, transferencia_par_id=saida, **base)
            con.execute("UPDATE transacao SET transferencia_par_id = ? WHERE id = ?",
                        (entrada, saida))
            ids = [saida, entrada]
        elif n.tipo == "despesa_cartao":
            grupo = uuid.uuid4().hex if n.parcelas > 1 else None
            parcela_base, resto = divmod(n.valor_centavos, n.parcelas)
            for i in range(n.parcelas):
                # Centavos que sobram da divisão vão na 1ª parcela, como fazem os bancos.
                valor = parcela_base + (resto if i == 0 else 0)
                data_parcela = faturas.somar_meses(n.data, i)
                fatura_id = faturas.obter_ou_criar_fatura(con, n.cartao_id, data_parcela)
                descricao = base["descricao"] + (f" ({i + 1}/{n.parcelas})" if grupo else "")
                # Cada parcela é datada no seu mês (como no extrato do cartão): a despesa
                # de uma compra parcelada se distribui pelos meses das parcelas.
                ids.append(_inserir(
                    con, tipo="despesa_cartao", valor_centavos=valor,
                    data=data_parcela.isoformat(), cartao_id=n.cartao_id, fatura_id=fatura_id,
                    parcela=i + 1 if grupo else None, total_parcelas=n.parcelas if grupo else None,
                    grupo_parcelas=grupo, **{**base, "descricao": descricao},
                ))
        elif n.tipo == "pagamento_fatura":
            fatura_id = _fatura_a_pagar(con, n)
            ids.append(_inserir(con, tipo="pagamento_fatura", valor_centavos=n.valor_centavos,
                                data=n.data.isoformat(), conta_id=n.conta_id,
                                cartao_id=n.cartao_id, fatura_id=fatura_id,
                                **{**base, "categoria_id": None}))
        else:
            ids.append(_inserir(con, tipo=n.tipo, valor_centavos=n.valor_centavos,
                                data=n.data.isoformat(), conta_id=n.conta_id,
                                ajuste_negativo=int(n.ajuste_negativo), **base))
        for tid in ids:
            con.executemany("INSERT INTO transacao_tag (transacao_id, tag_id) VALUES (?, ?)",
                            [(tid, tag) for tag in n.tags])
    return ids


def reajustar_saldo(con: sqlite3.Connection, conta_id: int, saldo_desejado: int,
                    data: date) -> dict:
    """Lança um ajuste para que o saldo da conta na data fique igual ao informado.

    Como o "Reajuste de saldo" do Mobills: útil depois de importar um histórico
    que não traz saldo inicial, ou para acertar diferenças com o extrato.
    """
    conta = con.execute("SELECT id, nome, saldo_inicial_centavos, data_saldo_inicial "
                        "FROM conta WHERE id = ?", (conta_id,)).fetchone()
    if conta is None:
        raise RegraViolada("Conta não encontrada")
    atual = conta["saldo_inicial_centavos"] + con.execute(
        f"SELECT COALESCE(SUM({EFEITO_SQL}), 0) FROM transacao t "
        "WHERE t.conta_id = ? AND t.pago = 1 AND t.data >= ? AND t.data <= ?",
        (conta_id, conta["data_saldo_inicial"], data.isoformat())).fetchone()[0]
    diferenca = saldo_desejado - atual
    ids: list[int] = []
    if diferenca:
        ids = criar(con, NovaTransacao(
            tipo="ajuste", descricao="Reajuste de saldo", valor_centavos=abs(diferenca),
            data=data, conta_id=conta_id, ajuste_negativo=diferenca < 0))
    return {"conta_id": conta_id, "saldo_anterior": atual, "saldo_novo": saldo_desejado,
            "diferenca": diferenca, "transacao_id": ids[0] if ids else None}
