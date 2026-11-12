-- 1. Dimensão Plano de Contas
CREATE TABLE IF NOT EXISTS dim_plano_contas (
    id_conta VARCHAR(64) PRIMARY KEY,
    demonstrativo VARCHAR(10) NOT NULL,
    secao_contabil VARCHAR(50) NOT NULL,
    subgrupo VARCHAR(50) NOT NULL,
    descricao_conta VARCHAR(255) NOT NULL,
    tipo_conta VARCHAR(20) NOT NULL,
    nivel_hierarquia SMALLINT NOT NULL,
    ordem_exibicao INT NOT NULL,
    natureza_sinal SMALLINT NOT NULL DEFAULT 1
);

-- 2. Fato Movimentação Contábil
CREATE TABLE IF NOT EXISTS fato_movimento_contabil (
    id_conta VARCHAR(64) NOT NULL REFERENCES dim_plano_contas(id_conta),
    data_fechamento DATE NOT NULL,
    periodo_codigo VARCHAR(10) NOT NULL,
    valor_discreto NUMERIC(18, 2),
    valor_ytd NUMERIC(18, 2),
    data_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fato_movimento PRIMARY KEY (id_conta, data_fechamento)
);

CREATE INDEX IF NOT EXISTS idx_fato_mov_data ON fato_movimento_contabil(data_fechamento);

-- 3. Dimensão Métrica Operacional
CREATE TABLE IF NOT EXISTS dim_metrica_operacional (
    id_metrica VARCHAR(64) PRIMARY KEY,
    categoria VARCHAR(50) NOT NULL,
    subgrupo VARCHAR(50) NOT NULL,
    nome_metrica VARCHAR(255) NOT NULL,
    unidade_medida VARCHAR(20) NOT NULL
);

-- 4. Fato Indicadores Operacionais
CREATE TABLE IF NOT EXISTS fato_indicadores_operacionais (
    id_metrica VARCHAR(64) NOT NULL REFERENCES dim_metrica_operacional(id_metrica),
    data_fechamento DATE NOT NULL,
    periodo_codigo VARCHAR(10) NOT NULL,
    valor_metrica NUMERIC(18, 4) NOT NULL,
    data_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fato_indicadores PRIMARY KEY (id_metrica, data_fechamento)
);

CREATE INDEX IF NOT EXISTS idx_fato_ind_data ON fato_indicadores_operacionais(data_fechamento);
