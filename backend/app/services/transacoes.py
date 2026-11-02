"""Criação de transações com as regras de cada tipo."""
from __future__ import annotations

import re
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import date

from . import faturas

TIPOS = ("receita", "despesa", "despesa_cartao", "credito_cartao", "transferencia",
         "pagamento_fatura", "ajuste")
NO_CARTAO = ("despesa_cartao", "credito_cartao")   # entram na fatura, não mexem em conta

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
    if n.tipo == "credito_cartao":
        if not n.cartao_id:
            raise RegraViolada("Crédito na fatura precisa do cartão")
        if n.parcelas != 1:
            raise RegraViolada("Crédito na fatura não tem parcelas")
    elif n.tipo == "despesa_cartao":
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
                if n.fatura_competencia and i == 0:
                    # Lançado direto numa fatura (ex.: tarifa ou compra esquecida na conferência).
                    from .fatura_cartao import fatura_por_competencia
                    fatura_id = fatura_por_competencia(con, n.cartao_id, n.fatura_competencia)
                else:
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
        elif n.tipo == "credito_cartao":
            from .fatura_cartao import fatura_por_competencia
            fatura_id = (fatura_por_competencia(con, n.cartao_id, n.fatura_competencia)
                         if n.fatura_competencia
                         else faturas.obter_ou_criar_fatura(con, n.cartao_id, n.data))
            ids.append(_inserir(con, tipo="credito_cartao", valor_centavos=n.valor_centavos,
                                data=n.data.isoformat(), cartao_id=n.cartao_id,
                                fatura_id=fatura_id, **base))
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
                    data: date, no_saldo_inicial: bool = False) -> dict:
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
    if diferenca and no_saldo_inicial:
        # Corrige o saldo de ABERTURA: o histórico mês a mês fica certo desde o início.
        with con:
            con.execute("UPDATE conta SET saldo_inicial_centavos = saldo_inicial_centavos + ? "
                        "WHERE id = ?", (diferenca, conta_id))
    elif diferenca:
        ids = criar(con, NovaTransacao(
            tipo="ajuste", descricao="Reajuste de saldo", valor_centavos=abs(diferenca),
            data=data, conta_id=conta_id, ajuste_negativo=diferenca < 0))
    return {"conta_id": conta_id, "saldo_anterior": atual, "saldo_novo": saldo_desejado,
            "diferenca": diferenca, "transacao_id": ids[0] if ids else None}


EDITAVEIS = ("descricao", "valor_centavos", "data", "conta_id", "cartao_id", "categoria_id",
             "observacao", "conferido", "pago", "ignorar")


def editar(con: sqlite3.Connection, transacao_id: int, mudancas: dict) -> dict:
    """Altera uma transação já lançada.

    - Compra no cartão: mudar a data ou o cartão recalcula a fatura; 'fatura_competencia'
      move o lançamento para outra fatura (quando o banco lançou num mês diferente).
    - Transferência: data, valor e descrição mudam nas duas pernas.
    - Lançamento com itens de cupom: o valor e a categoria vêm dos itens e não mudam aqui.
    """
    t = con.execute("SELECT * FROM transacao WHERE id = ?", (transacao_id,)).fetchone()
    if t is None:
        raise RegraViolada("Transação não encontrada")
    campos = {k: v for k, v in mudancas.items() if k in EDITAVEIS}
    if "data" in campos and isinstance(campos["data"], date):
        campos["data"] = campos["data"].isoformat()
    # A tela reenvia o formulário inteiro: o que veio igual não é mudança e não pode
    # recalcular a fatura (trocar só o cartão mantém o mês de vencimento).
    for k in ("data", "cartao_id", "conta_id"):
        if k in campos and campos[k] == t[k]:
            del campos[k]
    if "descricao" in campos:
        campos["descricao"] = campos["descricao"].strip()
        if not campos["descricao"]:
            raise RegraViolada("A descrição não pode ficar vazia")
    if campos.get("valor_centavos") is not None and campos["valor_centavos"] <= 0:
        raise RegraViolada("O valor deve ser maior que zero")
    tem_itens = con.execute("SELECT COUNT(*) FROM item WHERE transacao_id = ?",
                            (transacao_id,)).fetchone()[0]
    if tem_itens:
        if "valor_centavos" in campos and campos["valor_centavos"] != t["valor_centavos"]:
            raise RegraViolada("O valor deste lançamento vem dos itens do cupom")
        if campos.get("categoria_id"):
            raise RegraViolada("A categoria deste lançamento está nos itens do cupom")
    # Trocar a forma de pagamento de uma despesa à vista: conta <-> cartão.
    if t["tipo"] == "despesa" and campos.get("cartao_id") and t["grupo_parcelas"] is None:
        campos.update(tipo="despesa_cartao", conta_id=None, pago=1)
    elif t["tipo"] == "despesa_cartao" and campos.get("conta_id") and t["grupo_parcelas"] is None:
        campos.update(tipo="despesa", cartao_id=None, fatura_id=None, conferido=0)
    tipo = campos.get("tipo", t["tipo"])

    if tipo in NO_CARTAO:
        if "tipo" not in campos:
            campos.pop("conta_id", None)
        if campos.get("cartao_id") is None:
            campos.pop("cartao_id", None)
        cartao = campos.get("cartao_id", t["cartao_id"])
        from .fatura_cartao import fatura_por_competencia
        if mudancas.get("fatura_competencia"):
            campos["fatura_id"] = fatura_por_competencia(con, cartao, mudancas["fatura_competencia"])
        elif "cartao_id" in campos and "data" not in campos and "tipo" not in campos and t["fatura_id"]:
            # Só trocou o cartão: a compra continua no mesmo mês de vencimento.
            campos["fatura_id"] = fatura_por_competencia(con, cartao, _competencia_da_fatura(con, t["fatura_id"]))
        elif {"data", "cartao_id", "tipo"} & campos.keys():
            campos["fatura_id"] = faturas.obter_ou_criar_fatura(
                con, cartao, date.fromisoformat(campos.get("data", t["data"])))
    else:
        if "tipo" not in campos:
            campos.pop("cartao_id", None)
        if "conta_id" in campos and not campos["conta_id"]:
            raise RegraViolada("Informe a conta")
    if t["tipo"] in ("pagamento_fatura", "transferencia", "ajuste"):
        campos.pop("categoria_id", None)

    with con:
        if campos:
            sets = ", ".join(f"{k} = ?" for k in campos)
            con.execute(f"UPDATE transacao SET {sets} WHERE id = ?", (*campos.values(), transacao_id))
            par = t["transferencia_par_id"]
            comuns = {k: v for k, v in campos.items() if k in ("descricao", "valor_centavos", "data",
                                                                "observacao", "ignorar")}
            if par and comuns:
                sets = ", ".join(f"{k} = ?" for k in comuns)
                con.execute(f"UPDATE transacao SET {sets} WHERE id = ?", (*comuns.values(), par))
        if mudancas.get("parcelas_seguintes") and campos.get("cartao_id") \
                and campos["cartao_id"] != t["cartao_id"] and t["parcela"]:
            from .fatura_cartao import fatura_por_competencia
            for irma in parcelas_seguintes(con, t):
                comp = _competencia_da_fatura(con, irma["fatura_id"])
                con.execute("UPDATE transacao SET cartao_id = ?, fatura_id = ? WHERE id = ?",
                            (campos["cartao_id"], fatura_por_competencia(con, campos["cartao_id"], comp),
                             irma["id"]))
        if mudancas.get("tags") is not None:
            con.execute("DELETE FROM transacao_tag WHERE transacao_id = ?", (transacao_id,))
            con.executemany("INSERT INTO transacao_tag (transacao_id, tag_id) VALUES (?, ?)",
                            [(transacao_id, tag) for tag in mudancas["tags"]])
    return dict(con.execute("SELECT * FROM transacao WHERE id = ?", (transacao_id,)).fetchone())


def _competencia_da_fatura(con: sqlite3.Connection, fatura_id: int) -> str:
    return con.execute("SELECT competencia FROM fatura WHERE id = ?", (fatura_id,)).fetchone()[0]


_RE_PARCELA = re.compile(r"\s*\(\s*\d{1,3}\s*/\s*\d{1,3}\s*\)\s*$")


def parcelas_seguintes(con: sqlite3.Connection, t) -> list:
    """Parcelas posteriores da mesma compra, no mesmo cartão.

    Pelo grupo (parcelado pelo app) ou, para parcelas importadas uma a uma, pela
    descrição sem o "(n/m)" e pelo total de parcelas."""
    if t["grupo_parcelas"]:
        return con.execute("SELECT * FROM transacao WHERE grupo_parcelas = ? AND parcela > ?",
                           (t["grupo_parcelas"], t["parcela"])).fetchall()
    base = _RE_PARCELA.sub("", t["descricao"]).strip().lower()
    candidatas = con.execute(
        """SELECT * FROM transacao WHERE tipo = 'despesa_cartao' AND cartao_id = ? AND id <> ?
           AND total_parcelas = ? AND parcela > ? AND data > ?""",
        (t["cartao_id"], t["id"], t["total_parcelas"], t["parcela"], t["data"])).fetchall()
    return [c for c in candidatas if _RE_PARCELA.sub("", c["descricao"]).strip().lower() == base]
