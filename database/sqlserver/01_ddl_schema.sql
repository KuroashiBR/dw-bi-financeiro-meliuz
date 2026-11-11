-- 1. Dimensão Plano de Contas
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='dim_plano_contas' AND xtype='U')
CREATE TABLE dim_plano_contas (
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
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='fato_movimento_contabil' AND xtype='U')
CREATE TABLE fato_movimento_contabil (
    id_conta VARCHAR(64) NOT NULL FOREIGN KEY REFERENCES dim_plano_contas(id_conta),
    data_fechamento DATE NOT NULL,
    periodo_codigo VARCHAR(10) NOT NULL,
    valor_discreto DECIMAL(18, 2),
    valor_ytd DECIMAL(18, 2),
    data_carga DATETIME DEFAULT GETDATE(),
    CONSTRAINT pk_fato_movimento PRIMARY KEY CLUSTERED (id_conta, data_fechamento)
);

CREATE NONCLUSTERED INDEX idx_fato_mov_data ON fato_movimento_contabil(data_fechamento);

-- 3. Dimensão Métrica Operacional
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='dim_metrica_operacional' AND xtype='U')
CREATE TABLE dim_metrica_operacional (
    id_metrica VARCHAR(64) PRIMARY KEY,
    categoria VARCHAR(50) NOT NULL,
    subgrupo VARCHAR(50) NOT NULL,
    nome_metrica VARCHAR(255) NOT NULL,
    unidade_medida VARCHAR(20) NOT NULL
);

-- 4. Fato Indicadores Operacionais
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='fato_indicadores_operacionais' AND xtype='U')
CREATE TABLE fato_indicadores_operacionais (
    id_metrica VARCHAR(64) NOT NULL FOREIGN KEY REFERENCES dim_metrica_operacional(id_metrica),
    data_fechamento DATE NOT NULL,
    periodo_codigo VARCHAR(10) NOT NULL,
    valor_metrica DECIMAL(18, 4) NOT NULL,
    data_carga DATETIME DEFAULT GETDATE(),
    CONSTRAINT pk_fato_indicadores PRIMARY KEY CLUSTERED (id_metrica, data_fechamento)
);

CREATE NONCLUSTERED INDEX idx_fato_ind_data ON fato_indicadores_operacionais(data_fechamento);
