-- Cupom antigo pode entrar só para o histórico de preços, sem criar despesa
-- (a despesa já veio do Mobills). O preço passa a valer pelo documento quando
-- não há transação: data de emissão e loja do cupom.
DROP VIEW IF EXISTS v_preco;
CREATE VIEW v_preco AS
SELECT
    i.id                AS item_id,
    i.produto_id,
    p.nome              AS produto,
    p.grupo_id,
    COALESCE(t.data, substr(d.data_emissao, 1, 10))      AS data,
    COALESCE(t.estabelecimento_id, d.estabelecimento_id) AS estabelecimento_id,
    i.quantidade_milesimos,
    i.unidade,
    (i.valor_total_centavos - i.desconto_centavos) AS liquido_centavos,
    CAST(ROUND((i.valor_total_centavos - i.desconto_centavos) * 1000.0
               / i.quantidade_milesimos) AS INTEGER) AS preco_liquido_unitario_centavos
FROM item i
LEFT JOIN transacao t ON t.id = i.transacao_id
LEFT JOIN documento d ON d.id = i.documento_id
LEFT JOIN produto p ON p.id = i.produto_id
WHERE (t.id IS NOT NULL AND t.ignorar = 0) OR (i.transacao_id IS NULL AND d.id IS NOT NULL);
