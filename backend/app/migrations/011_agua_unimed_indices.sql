-- Água (CESAN) e reajuste do plano de saúde (Unimed) comparado com índices.

-- 1) Parte fixa da tarifa: a CESAN cobra um valor fixo (água + esgoto) mesmo sem consumo.
ALTER TABLE conta_ficha ADD COLUMN fixo_centavos INTEGER;

-- 2) Itens da fatura do plano de saúde, por beneficiário (mensalidade, remoção...).
--    Separa o reajuste anual (todos sobem juntos) da mudança de faixa etária (só uma pessoa sobe).
CREATE TABLE plano_item (
    transacao_id    INTEGER NOT NULL REFERENCES transacao(id) ON DELETE CASCADE,
    beneficiario    TEXT NOT NULL,
    item            TEXT NOT NULL,
    valor_centavos  INTEGER NOT NULL,
    PRIMARY KEY (transacao_id, beneficiario, item)
);

-- 3) Índices de preço mês a mês (% no mês), baixados do Banco Central (SGS).
CREATE TABLE indice_mensal (
    indice  TEXT NOT NULL,        -- 'IPCA', 'INPC', 'IGP-M', 'IGP-DI', 'IPC-Fipe'
    mes     TEXT NOT NULL,        -- AAAA-MM
    valor   REAL NOT NULL,        -- variação no mês, em %
    PRIMARY KEY (indice, mes)
);

-- 4) Teto da ANS para planos individuais/familiares: vale de maio a abril do ano seguinte.
CREATE TABLE teto_ans (
    ciclo_inicio  TEXT PRIMARY KEY,   -- AAAA-05
    percentual    REAL NOT NULL,
    fonte         TEXT
);
INSERT INTO teto_ans (ciclo_inicio, percentual, fonte) VALUES
    ('2026-05', 5.11, 'ANS, 29/05/2026 (ciclo mai/2026-abr/2027)'),
    ('2025-05', 6.06, 'ANS (ciclo mai/2025-abr/2026)'),
    ('2024-05', 6.91, 'ANS (ciclo mai/2024-abr/2025)'),
    ('2023-05', 9.63, 'ANS (ciclo mai/2023-abr/2024)'),
    ('2022-05', 15.50, 'ANS (ciclo mai/2022-abr/2023)'),
    ('2021-05', -8.19, 'ANS (ciclo mai/2021-abr/2022)');
