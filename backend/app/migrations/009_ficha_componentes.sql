-- Ficha da conta: componentes que não dependem do consumo, lidos do PDF da fatura.
ALTER TABLE conta_ficha ADD COLUMN cip_centavos INTEGER;          -- iluminação pública
ALTER TABLE conta_ficha ADD COLUMN terceiros_centavos INTEGER;    -- serviços de terceiros (ex.: seguro)
ALTER TABLE conta_ficha ADD COLUMN arquivo TEXT;                  -- PDF de onde a ficha foi lida

-- Série de consumo que a própria fatura traz (13 meses): dá o "mesmo mês do ano anterior"
-- mesmo para meses que não estão no app (2025 ficou no Excel).
CREATE TABLE conta_historico (
    tipo            TEXT NOT NULL,           -- 'energia', 'agua'...
    referencia      TEXT NOT NULL,           -- AAAA-MM
    consumo         REAL NOT NULL,
    valor_centavos  INTEGER,
    PRIMARY KEY (tipo, referencia)
);
