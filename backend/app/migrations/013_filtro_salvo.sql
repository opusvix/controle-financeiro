-- Filtros personalizados da tela Transações (como no Mobills: "Filtros salvos").
-- São conveniência do usuário, não dado financeiro; guardamos o critério como JSON.
CREATE TABLE filtro_salvo (
    id            INTEGER PRIMARY KEY,
    nome          TEXT NOT NULL UNIQUE,
    criterios     TEXT NOT NULL,              -- JSON do filtro (datas, categorias, contas, tags, situações, tipos)
    criado_em     TEXT NOT NULL DEFAULT (datetime('now'))
);
