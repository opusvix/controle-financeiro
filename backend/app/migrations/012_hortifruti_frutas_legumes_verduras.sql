-- Fase 3 (controle de preços): separar o hortifruti em Frutas, Legumes e Verduras.
-- O modelo de categorias tem 2 níveis (mãe > subcategoria), então estas entram
-- como subcategorias IRMÃS de "Hortifruti", todas sob "Alimentação".
-- "Hortifruti" continua existindo (serve de geral / mistos já lançados).
--
-- Bancos NOVOS: aqui ainda não há categorias (o seed roda depois da migração),
-- então o SELECT não acha "Alimentação" e nada é inserido; o seed.py cria as três.
-- Bancos EXISTENTES (como o do João): o seed não roda, e esta migração as cria.
-- INSERT OR IGNORE + UNIQUE(nome, tipo, pai_id) deixa tudo idempotente.
INSERT OR IGNORE INTO categoria (nome, tipo, cor, pai_id)
SELECT novo.nome, 'despesa', mae.cor, mae.id
FROM categoria mae
JOIN (SELECT 'Frutas' AS nome UNION ALL SELECT 'Legumes' UNION ALL SELECT 'Verduras') novo
WHERE mae.nome = 'Alimentação' AND mae.tipo = 'despesa' AND mae.pai_id IS NULL;
