-- Conferência da fatura do cartão com o extrato do banco.
ALTER TABLE transacao ADD COLUMN conferido INTEGER NOT NULL DEFAULT 0;   -- 1 = bateu com o extrato
ALTER TABLE fatura ADD COLUMN valor_banco_centavos INTEGER;               -- total que o banco cobrou
