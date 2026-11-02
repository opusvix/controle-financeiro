-- Novo tipo 'credito_cartao': estorno, cashback ou crédito que DIMINUI a fatura.
-- O SQLite não altera CHECK, então a tabela é recriada (procedimento oficial:
-- nova tabela, copiar, apagar a antiga, renomear). Os ids não mudam.
PRAGMA foreign_keys = OFF;
BEGIN;
DROP VIEW IF EXISTS v_preco;
CREATE TABLE transacao_nova (
    id                    INTEGER PRIMARY KEY,
    tipo                  TEXT NOT NULL CHECK (tipo IN
                            ('receita', 'despesa', 'despesa_cartao', 'credito_cartao',
                             'transferencia', 'pagamento_fatura', 'ajuste')),
    descricao             TEXT NOT NULL,
    valor_centavos        INTEGER NOT NULL CHECK (valor_centavos > 0),
    data                  TEXT NOT NULL,
    pago                  INTEGER NOT NULL DEFAULT 1,
    conta_id              INTEGER REFERENCES conta(id),
    cartao_id             INTEGER REFERENCES cartao(id),
    fatura_id             INTEGER REFERENCES fatura(id),
    categoria_id          INTEGER REFERENCES categoria(id),
    estabelecimento_id    INTEGER REFERENCES estabelecimento(id),
    documento_id          INTEGER REFERENCES documento(id),
    transferencia_par_id  INTEGER REFERENCES transacao(id),
    entrada               INTEGER NOT NULL DEFAULT 0,
    ajuste_negativo       INTEGER NOT NULL DEFAULT 0,
    parcela               INTEGER,
    total_parcelas        INTEGER,
    grupo_parcelas        TEXT,
    ignorar               INTEGER NOT NULL DEFAULT 0,
    observacao            TEXT,
    criado_em             TEXT NOT NULL DEFAULT (datetime('now')),
    origem                TEXT,
    origem_id             TEXT,
    conferido             INTEGER NOT NULL DEFAULT 0,
    CHECK (
        (tipo IN ('despesa_cartao', 'credito_cartao') AND cartao_id IS NOT NULL AND conta_id IS NULL)
        OR (tipo NOT IN ('despesa_cartao', 'credito_cartao') AND conta_id IS NOT NULL)
    ),
    CHECK (tipo <> 'pagamento_fatura' OR cartao_id IS NOT NULL)
);
INSERT INTO transacao_nova (id, tipo, descricao, valor_centavos, data, pago, conta_id, cartao_id,
    fatura_id, categoria_id, estabelecimento_id, documento_id, transferencia_par_id, entrada,
    ajuste_negativo, parcela, total_parcelas, grupo_parcelas, ignorar, observacao, criado_em,
    origem, origem_id, conferido)
SELECT id, tipo, descricao, valor_centavos, data, pago, conta_id, cartao_id,
    fatura_id, categoria_id, estabelecimento_id, documento_id, transferencia_par_id, entrada,
    ajuste_negativo, parcela, total_parcelas, grupo_parcelas, ignorar, observacao, criado_em,
    origem, origem_id, conferido
FROM transacao;
DROP TABLE transacao;
ALTER TABLE transacao_nova RENAME TO transacao;
CREATE INDEX ix_transacao_data ON transacao(data);
CREATE INDEX ix_transacao_conta ON transacao(conta_id);
CREATE INDEX ix_transacao_fatura ON transacao(fatura_id);
CREATE UNIQUE INDEX ux_transacao_origem ON transacao(origem, origem_id) WHERE origem IS NOT NULL;
CREATE VIEW v_preco AS
SELECT
    i.id                AS item_id,
    i.produto_id,
    p.nome              AS produto,
    p.grupo_id,
    t.data,
    t.estabelecimento_id,
    i.quantidade_milesimos,
    i.unidade,
    (i.valor_total_centavos - i.desconto_centavos) AS liquido_centavos,
    CAST(ROUND((i.valor_total_centavos - i.desconto_centavos) * 1000.0
               / i.quantidade_milesimos) AS INTEGER) AS preco_liquido_unitario_centavos
FROM item i
JOIN transacao t ON t.id = i.transacao_id
LEFT JOIN produto p ON p.id = i.produto_id
WHERE t.ignorar = 0;
PRAGMA foreign_key_check;
COMMIT;
PRAGMA foreign_keys = ON;
