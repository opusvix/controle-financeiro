-- Solar Digital EDP: o desconto sobre os créditos é a economia que a própria fatura declara.
ALTER TABLE conta_ficha ADD COLUMN desconto_centavos INTEGER;
