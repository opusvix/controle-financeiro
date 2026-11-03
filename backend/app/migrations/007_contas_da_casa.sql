-- Contas da casa (etapa 1 do painel de contas de consumo).

-- 1) Vencimento separado da data do pagamento: ao dar baixa, a data vira o dia em que pagou
--    e o vencimento fica guardado aqui (para medir atraso, multa e juros).
ALTER TABLE transacao ADD COLUMN vencimento TEXT;

-- 2) Despesa fixa (contas da casa) x variável: marca na categoria; a subcategoria herda da mãe.
ALTER TABLE categoria ADD COLUMN fixa INTEGER NOT NULL DEFAULT 0;
UPDATE categoria SET fixa = 1
 WHERE tipo = 'despesa' AND nome IN ('Energia, água e gás', 'Internet e telefone', 'Plano de saúde');

-- 3) Ficha da conta: o que a fatura diz além do valor (consumo, bandeira, multa...).
--    tipo 'energia' (EDP Escelsa) e 'energia_solar' (créditos da EDP Solar) somam o "custo de energia".
CREATE TABLE conta_ficha (
    transacao_id          INTEGER PRIMARY KEY REFERENCES transacao(id) ON DELETE CASCADE,
    tipo                  TEXT NOT NULL CHECK (tipo IN
                            ('energia', 'energia_solar', 'agua', 'internet', 'telefone', 'saude', 'outra')),
    referencia            TEXT,      -- mês de consumo da fatura (AAAA-MM)
    consumo               REAL,      -- kWh (energia) ou m³ (água)
    kwh_compensado        REAL,      -- energia: créditos da Solar abatidos na conta da Escelsa
    bandeira              TEXT CHECK (bandeira IN ('verde', 'amarela', 'vermelha1', 'vermelha2', 'escassez')),
    bandeira_centavos     INTEGER,   -- quanto da conta foi adicional de bandeira
    multa_juros_centavos  INTEGER,   -- pago a mais por atraso
    vidas                 INTEGER,   -- plano de saúde
    observacao            TEXT
);

-- 4) Plano de saúde: a UNIMED veio do Mobills na categoria-mãe "Saúde", junto com farmácia.
--    Passa para "Saúde > Plano de saúde" (fixa), a pedido do João em 03/11/2026.
UPDATE transacao
   SET categoria_id = (SELECT f.id FROM categoria f JOIN categoria m ON m.id = f.pai_id
                        WHERE f.nome = 'Plano de saúde' AND m.nome = 'Saúde' AND f.tipo = 'despesa')
 WHERE upper(trim(descricao)) LIKE 'UNIMED%'
   AND categoria_id = (SELECT id FROM categoria WHERE nome = 'Saúde' AND pai_id IS NULL AND tipo = 'despesa')
   AND EXISTS (SELECT 1 FROM categoria f JOIN categoria m ON m.id = f.pai_id
                WHERE f.nome = 'Plano de saúde' AND m.nome = 'Saúde' AND f.tipo = 'despesa');
