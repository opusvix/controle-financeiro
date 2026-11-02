-- Contas que se repetem todo mês (luz, água, internet, plano de saúde).
-- Cada mês é uma transação própria; as do mesmo compromisso dividem o recorrencia_id.
ALTER TABLE transacao ADD COLUMN recorrencia_id TEXT;
CREATE INDEX IF NOT EXISTS ix_transacao_recorrencia ON transacao (recorrencia_id, data);
