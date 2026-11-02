-- Rastreia de onde veio cada transação importada, para reimportar sem duplicar.
ALTER TABLE transacao ADD COLUMN origem TEXT;      -- 'mobills', 'cupom', ...
ALTER TABLE transacao ADD COLUMN origem_id TEXT;   -- identificador estável na origem
CREATE UNIQUE INDEX ux_transacao_origem ON transacao(origem, origem_id)
    WHERE origem IS NOT NULL;
