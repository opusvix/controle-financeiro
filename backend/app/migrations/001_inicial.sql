-- Esquema inicial do Controle Financeiro.
-- Convenções:
--   * Dinheiro em CENTAVOS inteiros (R$ 8,98 = 898). Nunca REAL para dinheiro.
--   * Quantidades em MILÉSIMOS (0,458 kg = 458; 1 un = 1000).
--   * Datas em texto ISO: 'AAAA-MM-DD'. Competência de fatura: 'AAAA-MM'.
--   * Transação: valor_centavos sempre POSITIVO; o sinal vem do tipo.

PRAGMA foreign_keys = ON;

CREATE TABLE instituicao (
    id      INTEGER PRIMARY KEY,
    nome    TEXT NOT NULL UNIQUE,
    codigo  TEXT              -- código do banco (ex.: 001, 336)
);

CREATE TABLE conta (
    id                    INTEGER PRIMARY KEY,
    nome                  TEXT NOT NULL UNIQUE,
    instituicao_id        INTEGER REFERENCES instituicao(id),
    tipo                  TEXT NOT NULL CHECK (tipo IN
                            ('corrente', 'poupanca', 'investimento', 'carteira', 'outro')),
    saldo_inicial_centavos INTEGER NOT NULL DEFAULT 0,
    data_saldo_inicial    TEXT NOT NULL DEFAULT (date('now')),
    cor                   TEXT NOT NULL DEFAULT '#6b7280',
    -- Saldo disponível = contas com esta marca; Patrimônio = todas as ativas.
    compoe_saldo_disponivel INTEGER NOT NULL DEFAULT 1,
    ativa                 INTEGER NOT NULL DEFAULT 1,
    criado_em             TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE cartao (
    id                  INTEGER PRIMARY KEY,
    nome                TEXT NOT NULL UNIQUE,
    instituicao_id      INTEGER REFERENCES instituicao(id),
    bandeira            TEXT NOT NULL,
    final               TEXT NOT NULL CHECK (length(final) = 4 AND final GLOB '[0-9][0-9][0-9][0-9]'),
    limite_centavos     INTEGER NOT NULL DEFAULT 0,
    dia_fechamento      INTEGER NOT NULL CHECK (dia_fechamento BETWEEN 1 AND 31),
    dia_vencimento      INTEGER NOT NULL CHECK (dia_vencimento BETWEEN 1 AND 31),
    conta_pagamento_id  INTEGER REFERENCES conta(id),
    cor                 TEXT NOT NULL DEFAULT '#6b7280',
    ativo               INTEGER NOT NULL DEFAULT 1
);

-- Fatura: uma por cartão e competência (mês do vencimento).
CREATE TABLE fatura (
    id              INTEGER PRIMARY KEY,
    cartao_id       INTEGER NOT NULL REFERENCES cartao(id),
    competencia     TEXT NOT NULL,              -- 'AAAA-MM' do vencimento
    data_fechamento TEXT NOT NULL,
    data_vencimento TEXT NOT NULL,
    UNIQUE (cartao_id, competencia)
);

-- Categoria = "conta contábil" (o QUE foi gasto). Hierarquia com pai_id.
CREATE TABLE categoria (
    id      INTEGER PRIMARY KEY,
    nome    TEXT NOT NULL,
    tipo    TEXT NOT NULL CHECK (tipo IN ('receita', 'despesa')),
    pai_id  INTEGER REFERENCES categoria(id),
    icone   TEXT,
    cor     TEXT NOT NULL DEFAULT '#6b7280',
    ativa   INTEGER NOT NULL DEFAULT 1,
    UNIQUE (nome, tipo, pai_id)
);

-- Tag = "centro de custo" (PARA QUÊ / qual projeto). Ex.: CERCO FELINO.
CREATE TABLE tag (
    id    INTEGER PRIMARY KEY,
    nome  TEXT NOT NULL UNIQUE,
    cor   TEXT NOT NULL DEFAULT '#6b7280'
);

CREATE TABLE estabelecimento (
    id            INTEGER PRIMARY KEY,
    cnpj          TEXT UNIQUE,                 -- só dígitos
    nome          TEXT NOT NULL,
    cidade        TEXT,
    uf            TEXT
);

-- Documento: imagem/PDF de cupom, pedido ou comprovante de maquininha.
CREATE TABLE documento (
    id                  INTEGER PRIMARY KEY,
    tipo                TEXT NOT NULL CHECK (tipo IN ('nfce', 'pedido', 'comprovante', 'outro')),
    arquivo             TEXT NOT NULL,          -- caminho relativo da imagem
    hash_arquivo        TEXT,
    chave_nfce          TEXT UNIQUE,            -- 44 dígitos; evita lançar a mesma nota duas vezes
    estabelecimento_id  INTEGER REFERENCES estabelecimento(id),
    data_emissao        TEXT,
    valor_total_centavos INTEGER,
    status              TEXT NOT NULL DEFAULT 'novo'
                          CHECK (status IN ('novo', 'lido', 'revisado', 'lancado', 'descartado')),
    leitura_json        TEXT,                   -- resposta bruta da leitura, para auditoria
    criado_em           TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Transação (o "cabeçalho"). Tipos e efeito:
--   receita           +conta
--   despesa           -conta
--   despesa_cartao    entra na fatura do cartão (não mexe em conta)
--   transferencia     -conta origem; o par (transferencia_par_id) é +conta destino
--   pagamento_fatura  -conta; quita fatura (NÃO é despesa: evita contar em dobro)
--   ajuste            +/- conta (sinal em ajuste_negativo)
CREATE TABLE transacao (
    id                    INTEGER PRIMARY KEY,
    tipo                  TEXT NOT NULL CHECK (tipo IN
                            ('receita', 'despesa', 'despesa_cartao', 'transferencia',
                             'pagamento_fatura', 'ajuste')),
    descricao             TEXT NOT NULL,
    valor_centavos        INTEGER NOT NULL CHECK (valor_centavos > 0),
    data                  TEXT NOT NULL,
    pago                  INTEGER NOT NULL DEFAULT 1,     -- 0 = pendente / a pagar
    conta_id              INTEGER REFERENCES conta(id),
    cartao_id             INTEGER REFERENCES cartao(id),
    fatura_id             INTEGER REFERENCES fatura(id),
    categoria_id          INTEGER REFERENCES categoria(id), -- nulo quando dividida por itens
    estabelecimento_id    INTEGER REFERENCES estabelecimento(id),
    documento_id          INTEGER REFERENCES documento(id),
    transferencia_par_id  INTEGER REFERENCES transacao(id),
    entrada               INTEGER NOT NULL DEFAULT 0,     -- 1 = perna de entrada de transferência
    ajuste_negativo       INTEGER NOT NULL DEFAULT 0,
    parcela               INTEGER,
    total_parcelas        INTEGER,
    grupo_parcelas        TEXT,
    ignorar               INTEGER NOT NULL DEFAULT 0,     -- fora de relatórios
    observacao            TEXT,
    criado_em             TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (
        (tipo = 'despesa_cartao' AND cartao_id IS NOT NULL AND conta_id IS NULL)
        OR (tipo <> 'despesa_cartao' AND conta_id IS NOT NULL)
    ),
    CHECK (tipo <> 'pagamento_fatura' OR cartao_id IS NOT NULL)
);
CREATE INDEX ix_transacao_data ON transacao(data);
CREATE INDEX ix_transacao_conta ON transacao(conta_id);
CREATE INDEX ix_transacao_fatura ON transacao(fatura_id);

CREATE TABLE transacao_tag (
    transacao_id INTEGER NOT NULL REFERENCES transacao(id) ON DELETE CASCADE,
    tag_id       INTEGER NOT NULL REFERENCES tag(id),
    PRIMARY KEY (transacao_id, tag_id)
);

-- Produtos: grupo ("Mortadela") > produto ("Mortadela Sadia defumada").
CREATE TABLE grupo_produto (
    id    INTEGER PRIMARY KEY,
    nome  TEXT NOT NULL UNIQUE
);

CREATE TABLE produto (
    id                INTEGER PRIMARY KEY,
    nome              TEXT NOT NULL UNIQUE,      -- nome padronizado
    ean               TEXT UNIQUE,
    grupo_id          INTEGER REFERENCES grupo_produto(id),
    unidade_base      TEXT NOT NULL DEFAULT 'un' CHECK (unidade_base IN ('un', 'kg', 'l')),
    conteudo_milesimos INTEGER,                  -- 200 g = 200 (em kg: 0,200); 600 ml = 600
    categoria_padrao_id INTEGER REFERENCES categoria(id)
);

-- Aprendizado: este texto, nesta loja, é este produto.
CREATE TABLE produto_alias (
    id                  INTEGER PRIMARY KEY,
    texto               TEXT NOT NULL,
    estabelecimento_id  INTEGER REFERENCES estabelecimento(id),
    produto_id          INTEGER NOT NULL REFERENCES produto(id),
    UNIQUE (texto, estabelecimento_id)
);

-- Item (a "linha" da nota).
CREATE TABLE item (
    id                      INTEGER PRIMARY KEY,
    transacao_id            INTEGER REFERENCES transacao(id) ON DELETE CASCADE,
    documento_id            INTEGER REFERENCES documento(id),
    seq                     INTEGER NOT NULL,
    codigo                  TEXT,               -- código interno da loja ou EAN
    descricao_lida          TEXT NOT NULL,      -- texto exatamente como impresso
    produto_id              INTEGER REFERENCES produto(id),
    quantidade_milesimos    INTEGER NOT NULL CHECK (quantidade_milesimos > 0),
    unidade                 TEXT NOT NULL DEFAULT 'un',
    preco_unitario_centavos INTEGER NOT NULL,
    desconto_centavos       INTEGER NOT NULL DEFAULT 0,
    valor_total_centavos    INTEGER NOT NULL,   -- bruto, antes do desconto
    categoria_id            INTEGER REFERENCES categoria(id)
);
CREATE INDEX ix_item_produto ON item(produto_id);

-- Histórico de preços: preço líquido por unidade de compra e por unidade base.
CREATE VIEW v_preco AS
SELECT
    i.id                AS item_id,
    i.produto_id,
    p.nome              AS produto,
    p.grupo_id,
    t.data,
    t.estabelecimento_id,
    i.quantidade_milesimos,
    i.unidade,
    (i.valor_total_centavos - i.desconto_centavos) AS liquido_centavos,
    -- centavos por unidade comprada (1 un ou 1 kg)
    CAST(ROUND((i.valor_total_centavos - i.desconto_centavos) * 1000.0
               / i.quantidade_milesimos) AS INTEGER) AS preco_liquido_unitario_centavos
FROM item i
JOIN transacao t ON t.id = i.transacao_id
LEFT JOIN produto p ON p.id = i.produto_id
WHERE t.ignorar = 0;

CREATE TABLE orcamento (
    id            INTEGER PRIMARY KEY,
    categoria_id  INTEGER NOT NULL REFERENCES categoria(id),
    competencia   TEXT NOT NULL,               -- 'AAAA-MM'
    valor_centavos INTEGER NOT NULL,
    UNIQUE (categoria_id, competencia)
);

CREATE TABLE configuracao (
    chave  TEXT PRIMARY KEY,
    valor  TEXT NOT NULL                       -- JSON
);

CREATE TABLE backup_log (
    id         INTEGER PRIMARY KEY,
    arquivo    TEXT NOT NULL,
    bytes      INTEGER NOT NULL,
    copiado_drive INTEGER NOT NULL DEFAULT 0,
    criado_em  TEXT NOT NULL DEFAULT (datetime('now'))
);
