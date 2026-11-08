"""Transações e Dashboard."""
from __future__ import annotations

import re
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from ..deps import con
from ..services import (agua, contas_casa, energia, fatura_cartao, indices, orcamento, painel,
                        plano, precos, relatorio_export, relatorios, transacoes)

router = APIRouter(prefix="/api", tags=["movimento"])
COMPETENCIA = r"^\d{4}-(0[1-9]|1[0-2])$"
DATA = r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$"


class TransacaoIn(BaseModel):
    tipo: Literal["receita", "despesa", "despesa_cartao", "credito_cartao", "transferencia",
                  "pagamento_fatura", "ajuste"]
    descricao: str = Field(min_length=1)
    valor_centavos: int = Field(gt=0)
    data: date
    pago: bool = True
    conta_id: int | None = None
    conta_destino_id: int | None = None
    cartao_id: int | None = None
    parcelas: int = Field(default=1, ge=1, le=72)
    repetir_meses: int = Field(default=1, ge=1, le=60)
    fatura_competencia: str | None = Field(default=None, pattern=COMPETENCIA)
    categoria_id: int | None = None
    estabelecimento_id: int | None = None
    ajuste_negativo: bool = False
    ignorar: bool = False
    observacao: str | None = None
    tags: list[int] = []


@router.get("/transacoes")
def listar(
    competencia: str | None = Query(default=None, pattern=COMPETENCIA),
    ini: str | None = Query(default=None, pattern=DATA),
    fim: str | None = Query(default=None, pattern=DATA),
    conta_id: int | None = None,
    tipo: str | None = None,
    categorias: list[int] = Query(default=[]),
    contas: list[int] = Query(default=[]),
    tags: list[int] = Query(default=[]),
    situacoes: list[Literal["pago", "pendente"]] = Query(default=[]),
    tipos: list[str] = Query(default=[]),
    c=Depends(con),
):
    """Transações filtradas. Sem nenhum filtro de data, usa o mês corrente (como o seletor de mês).

    - competencia: um mês ('AAAA-MM'); ini/fim: um intervalo de datas (têm prioridade sobre competencia).
    - categorias: inclui a categoria-mãe e suas subcategorias. contas/tags/tipos: listas. situacoes: pago/pendente.
    """
    sql = """
        SELECT t.*, c.nome AS categoria, co.nome AS conta, ca.nome AS cartao,
               COALESCE(c.fixa, 0) OR COALESCE(mae.fixa, 0) AS fixa,
               EXISTS (SELECT 1 FROM conta_ficha f WHERE f.transacao_id = t.id) AS tem_ficha,
               (SELECT group_concat(tg.nome, ', ') FROM transacao_tag tt
                  JOIN tag tg ON tg.id = tt.tag_id WHERE tt.transacao_id = t.id) AS tags,
               (SELECT COUNT(*) FROM item i WHERE i.transacao_id = t.id) AS itens
        FROM transacao t
        LEFT JOIN categoria c ON c.id = t.categoria_id
        LEFT JOIN categoria mae ON mae.id = c.pai_id
        LEFT JOIN conta co ON co.id = t.conta_id
        LEFT JOIN cartao ca ON ca.id = t.cartao_id
        WHERE 1 = 1
    """
    args: list = []
    if ini and fim:
        if fim < ini:
            raise HTTPException(422, "A data final não pode ser antes da inicial")
        sql += " AND t.data BETWEEN ? AND ?"
        args += [ini, fim]
    else:
        mes = competencia if competencia and not (ini or fim) else f"{date.today():%Y-%m}"
        sql += " AND strftime('%Y-%m', t.data) = ?"
        args.append(mes)
    if conta_id:
        sql += " AND t.conta_id = ?"
        args.append(conta_id)
    if tipo:
        sql += " AND t.tipo = ?"
        args.append(tipo)
    if categorias:
        marks = ", ".join("?" for _ in categorias)
        sql += f" AND (t.categoria_id IN ({marks}) OR c.pai_id IN ({marks}))"
        args += [*categorias, *categorias]
    if contas:
        sql += f" AND t.conta_id IN ({', '.join('?' for _ in contas)})"
        args += contas
    if tags:
        sql += (f" AND EXISTS (SELECT 1 FROM transacao_tag tt WHERE tt.transacao_id = t.id "
                f"AND tt.tag_id IN ({', '.join('?' for _ in tags)}))")
        args += tags
    if tipos:
        sql += f" AND t.tipo IN ({', '.join('?' for _ in tipos)})"
        args += tipos
    if situacoes and set(situacoes) != {"pago", "pendente"}:
        sql += " AND t.pago = ?"
        args.append(1 if situacoes[0] == "pago" else 0)
    sql += " ORDER BY t.data DESC, t.id DESC"
    return [dict(r) for r in c.execute(sql, args)]


class FiltroIn(BaseModel):
    nome: str = Field(min_length=1, max_length=60)
    criterios: dict


@router.get("/filtros")
def listar_filtros(c=Depends(con)):
    """Filtros salvos da tela Transações, do mais recente ao mais antigo."""
    import json
    return [{**dict(r), "criterios": json.loads(r["criterios"])}
            for r in c.execute("SELECT * FROM filtro_salvo ORDER BY id DESC")]


@router.post("/filtros", status_code=201)
def salvar_filtro(dados: FiltroIn, c=Depends(con)):
    """Cria ou atualiza (pelo nome) um filtro salvo."""
    import json
    crit = json.dumps(dados.criterios, ensure_ascii=False)
    with c:
        c.execute("INSERT INTO filtro_salvo (nome, criterios) VALUES (?, ?) "
                  "ON CONFLICT(nome) DO UPDATE SET criterios = excluded.criterios",
                  (dados.nome, crit))
    r = c.execute("SELECT * FROM filtro_salvo WHERE nome = ?", (dados.nome,)).fetchone()
    return {**dict(r), "criterios": json.loads(r["criterios"])}


@router.delete("/filtros/{id_}", status_code=204)
def apagar_filtro(id_: int, c=Depends(con)):
    with c:
        if c.execute("DELETE FROM filtro_salvo WHERE id = ?", (id_,)).rowcount == 0:
            raise HTTPException(404, "Filtro não encontrado")


@router.post("/transacoes", status_code=201)
def criar(dados: TransacaoIn, c=Depends(con)):
    try:
        ids = transacoes.criar(c, transacoes.NovaTransacao(**dados.model_dump()))
    except transacoes.RegraViolada as e:
        raise HTTPException(422, str(e)) from e
    marcas = ", ".join("?" for _ in ids)
    return [dict(r) for r in c.execute(f"SELECT * FROM transacao WHERE id IN ({marcas})", ids)]


class ReajusteIn(BaseModel):
    saldo_centavos: int
    data: date = Field(default_factory=date.today)
    no_saldo_inicial: bool = False   # True: corrige o saldo de abertura em vez de lançar ajuste


@router.post("/contas/{id_}/reajuste", status_code=201)
def reajustar(id_: int, dados: ReajusteIn, c=Depends(con)):
    """Acerta o saldo da conta lançando um ajuste com a diferença."""
    try:
        return transacoes.reajustar_saldo(c, id_, dados.saldo_centavos, dados.data,
                                          dados.no_saldo_inicial)
    except transacoes.RegraViolada as e:
        raise HTTPException(404, str(e)) from e


class EdicaoIn(BaseModel):
    """Só os campos enviados mudam."""
    descricao: str | None = None
    valor_centavos: int | None = Field(default=None, gt=0)
    data: date | None = None
    conta_id: int | None = None
    cartao_id: int | None = None
    categoria_id: int | None = None
    observacao: str | None = None
    conferido: bool | None = None
    pago: bool | None = None
    ignorar: bool | None = None
    vencimento: date | None = None
    fatura_competencia: str | None = Field(default=None, pattern=COMPETENCIA)
    tags: list[int] | None = None
    parcelas_seguintes: bool = False     # ao trocar o cartão, levar as próximas parcelas junto
    aplicar_nas_proximas: bool = False   # conta que se repete: mudar também os meses não pagos


@router.patch("/transacoes/{id_}")
def editar(id_: int, dados: EdicaoIn, c=Depends(con)):
    mudancas = dados.model_dump(exclude_unset=True)
    for k in ("conferido", "pago", "ignorar"):
        if k in mudancas and mudancas[k] is not None:
            mudancas[k] = int(mudancas[k])
    try:
        return transacoes.editar(c, id_, mudancas)
    except transacoes.RegraViolada as e:
        raise HTTPException(422, str(e)) from e


@router.get("/cartoes/{id_}/fatura")
def fatura(id_: int, competencia: str = Query(pattern=COMPETENCIA), c=Depends(con)):
    try:
        return fatura_cartao.detalhe(c, id_, competencia)
    except transacoes.RegraViolada as e:
        raise HTTPException(404, str(e)) from e


class ValorBancoIn(BaseModel):
    valor_centavos: int | None = Field(default=None, ge=0)


@router.put("/cartoes/{id_}/fatura/{competencia}/valor-banco")
def valor_banco(id_: int, competencia: str, dados: ValorBancoIn, c=Depends(con)):
    if not re.match(COMPETENCIA, competencia):
        raise HTTPException(422, "Competência inválida")
    try:
        fatura_cartao.informar_valor_banco(c, id_, competencia, dados.valor_centavos)
    except transacoes.RegraViolada as e:
        raise HTTPException(422, str(e)) from e
    return fatura_cartao.detalhe(c, id_, competencia)


@router.delete("/transacoes/{id_}", status_code=204)
def apagar(id_: int, proximas: bool = False, c=Depends(con)):
    try:
        transacoes.apagar(c, id_, proximas)
    except transacoes.RegraViolada as e:
        raise HTTPException(404, str(e)) from e


@router.get("/a-pagar")
def a_pagar(dias: int = Query(default=30, ge=0, le=366), c=Depends(con)):
    """Contas a pagar e a receber até daqui a 'dias' (inclui as atrasadas)."""
    from datetime import timedelta
    return transacoes.a_pagar(c, date.today() + timedelta(days=dias))


@router.get("/dashboard")
def dashboard(competencia: str | None = Query(default=None, pattern=COMPETENCIA), c=Depends(con)):
    competencia = competencia or f"{date.today():%Y-%m}"
    if not re.match(COMPETENCIA, competencia):
        raise HTTPException(422, "Competência inválida")
    return painel.resumo(c, competencia)


class OrcamentoIn(BaseModel):
    categoria_id: int
    competencia: str = Field(pattern=COMPETENCIA)
    valor_centavos: int = Field(ge=0)   # 0 remove o teto


@router.get("/orcamento")
def ver_orcamento(competencia: str | None = Query(default=None, pattern=COMPETENCIA), c=Depends(con)):
    """Orçado × realizado por categoria de despesa na competência."""
    competencia = competencia or f"{date.today():%Y-%m}"
    return orcamento.ver(c, competencia)


@router.put("/orcamento")
def definir_orcamento(dados: OrcamentoIn, c=Depends(con)):
    """Define (ou remove, com valor 0) o teto de uma categoria na competência."""
    with c:
        orcamento.definir(c, dados.categoria_id, dados.competencia, dados.valor_centavos)
    return {"ok": True}


@router.post("/orcamento/copiar")
def copiar_orcamento(competencia: str = Query(pattern=COMPETENCIA), c=Depends(con)):
    """Copia os tetos do mês anterior para esta competência (os que ainda faltam)."""
    with c:
        copiados = orcamento.copiar_do_mes_anterior(c, competencia)
    return {"copiados": copiados}


@router.get("/painel/energia")
def painel_energia(meses: int = Query(default=12, ge=1, le=36), c=Depends(con)):
    """Luz da casa mês a mês: Escelsa + Solar, preço real do kWh, consumo × ano anterior, economia da Solar."""
    return energia.painel(c, meses)


@router.get("/painel/agua")
def painel_agua(meses: int = Query(default=12, ge=1, le=36), c=Depends(con)):
    """Água da casa (CESAN): parte fixa × variável, preço médio do m³, consumo × ano anterior."""
    return agua.painel(c, meses)


@router.get("/painel/plano")
def painel_plano(c=Depends(con)):
    """Plano de saúde: mensalidades, reajustes (anual × faixa etária) e comparação com ANS e índices."""
    return plano.painel(c)


@router.post("/indices/atualizar")
def atualizar_indices(c=Depends(con)):
    """Baixa IPCA, INPC, IGP-M, IGP-DI e IPC-Fipe do Banco Central (precisa de internet)."""
    return indices.atualizar(c)


@router.get("/painel/precos")
def painel_precos(meses: int = Query(default=24, ge=1, le=60), c=Depends(con)):
    """Comparação de preços: cada produto dos cupons ao longo do tempo e entre lojas, sem marca."""
    return precos.painel(c, meses)




@router.get("/relatorios")
def relatorio_periodo(
    ini: str | None = Query(default=None, pattern=DATA),
    fim: str | None = Query(default=None, pattern=DATA),
    meses: int = Query(default=12, ge=1, le=60),
    c=Depends(con),
):
    """Relatório de um período: evolução mensal, despesas por categoria e por projeto (tag).

    Passe ini e fim (AAAA-MM-DD) para um intervalo exato, ou só `meses` para os últimos N meses.
    """
    return _relatorio(c, ini, fim, meses)


def _relatorio(c, ini: str | None, fim: str | None, meses: int) -> dict:
    if ini and fim:
        if fim < ini:
            raise HTTPException(422, "A data final não pode ser antes da inicial")
        return relatorios.periodo(c, ini, fim)
    return relatorios.atalho(c, meses)


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.get("/relatorios/export.xlsx")
def relatorio_xlsx(
    ini: str | None = Query(default=None, pattern=DATA),
    fim: str | None = Query(default=None, pattern=DATA),
    meses: int = Query(default=12, ge=1, le=60),
    c=Depends(con),
):
    """Mesmo relatório do período, como planilha Excel para baixar."""
    dados = _relatorio(c, ini, fim, meses)
    conteudo = relatorio_export.montar_xlsx(dados)
    nome = f"relatorio_{dados['ini']}_a_{dados['fim']}.xlsx"
    return Response(conteudo, media_type=XLSX,
                    headers={"Content-Disposition": f'attachment; filename="{nome}"'})


class FichaIn(BaseModel):
    """O que a fatura da conta diz além do valor. Campos que não valem para o tipo ficam vazios."""
    tipo: Literal[contas_casa.TIPOS]
    referencia: str | None = Field(default=None, pattern=COMPETENCIA)
    consumo: float | None = Field(default=None, ge=0)
    kwh_compensado: float | None = Field(default=None, ge=0)
    bandeira: Literal["verde", "amarela", "vermelha1", "vermelha2", "escassez"] | None = None
    bandeira_centavos: int | None = Field(default=None, ge=0)
    multa_juros_centavos: int | None = Field(default=None, ge=0)
    vidas: int | None = Field(default=None, ge=1)
    observacao: str | None = None


@router.get("/transacoes/{id_}/ficha")
def ficha(id_: int, c=Depends(con)):
    """A ficha gravada ou, se ainda não houver, uma sugestão a partir do mês anterior da mesma conta."""
    return contas_casa.obter(c, id_)


@router.put("/transacoes/{id_}/ficha")
def gravar_ficha(id_: int, dados: FichaIn, c=Depends(con)):
    try:
        return contas_casa.gravar(c, id_, dados.model_dump())
    except transacoes.RegraViolada as e:
        raise HTTPException(422, str(e)) from e


@router.delete("/transacoes/{id_}/ficha", status_code=204)
def apagar_ficha(id_: int, c=Depends(con)):
    with c:
        c.execute("DELETE FROM conta_ficha WHERE transacao_id = ?", (id_,))
