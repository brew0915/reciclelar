from sqlalchemy import create_engine, text

DATABASE_URL = "DATABASE_URL"

engine = create_engine(DATABASE_URL)

sql = """

-- =========================
-- USUÁRIOS
-- =========================

CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100),
    email VARCHAR(200),
    senha_hash VARCHAR(255),
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- FORNECEDORES
-- =========================

CREATE TABLE IF NOT EXISTS fornecedores (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    tipo VARCHAR(50),
    documento VARCHAR(30),
    telefone VARCHAR(30),
    email VARCHAR(200),
    endereco TEXT,
    observacoes TEXT
);

-- =========================
-- INDÚSTRIAS
-- =========================

CREATE TABLE IF NOT EXISTS industrias (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(200) NOT NULL,
    cnpj VARCHAR(30),
    contato VARCHAR(100),
    telefone VARCHAR(30),
    email VARCHAR(200),
    endereco TEXT
);

-- =========================
-- MATERIAIS
-- =========================

CREATE TABLE IF NOT EXISTS materiais (
    id SERIAL PRIMARY KEY,
    descricao VARCHAR(100) NOT NULL,
    categoria VARCHAR(50),
    unidade VARCHAR(20)
);

-- =========================
-- COMPRAS (CABEÇALHO)
-- =========================

CREATE TABLE IF NOT EXISTS compras (
    id SERIAL PRIMARY KEY,

    fornecedor_id INTEGER,

    fornecedor_avulso VARCHAR(200),

    valor_total NUMERIC(12,2) DEFAULT 0,

    observacao TEXT,

    data_compra TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- ITENS COMPRA
-- =========================

CREATE TABLE IF NOT EXISTS itens_compra (
    id SERIAL PRIMARY KEY,

    compra_id INTEGER NOT NULL
        REFERENCES compras(id),

    material_id INTEGER NOT NULL
        REFERENCES materiais(id),

    quantidade NUMERIC(12,3) NOT NULL,

    valor_kg NUMERIC(12,2) NOT NULL,

    valor_total NUMERIC(12,2) NOT NULL
);

-- =========================
-- VENDAS
-- =========================

CREATE TABLE IF NOT EXISTS vendas (
    id SERIAL PRIMARY KEY,

    industria_id INTEGER NOT NULL
        REFERENCES industrias(id),

    valor_total NUMERIC(12,2),

    observacao TEXT,

    data_venda TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- ESTOQUE
-- =========================

CREATE TABLE IF NOT EXISTS estoque_movimentacao (
    id SERIAL PRIMARY KEY,

    material_id INTEGER NOT NULL
        REFERENCES materiais(id),

    tipo VARCHAR(20) NOT NULL,

    quantidade NUMERIC(12,3) NOT NULL,

    origem VARCHAR(50),

    referencia_id INTEGER,

    data_movimentacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

"""

with engine.begin() as conn:
    conn.execute(text(sql))

print("Banco criado com sucesso!")
