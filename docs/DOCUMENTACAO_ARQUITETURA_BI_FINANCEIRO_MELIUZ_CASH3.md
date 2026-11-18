# PROJETO: DATA WAREHOUSE & BUSINESS INTELLIGENCE FINANCEIRO (MÉLIUZ — CASH3)

## 1. Visão Geral e Declaração de Escopo

### 1.1 Objetivo do Projeto

Construir uma esteira completa de engenharia analítica (*Analytics Engineering*) ponta a ponta (*End-to-End*), modelando e disponibilizando os dados contábeis e operacionais da **Méliuz S.A. (B3: CASH3)** em um **Data Warehouse relacional** (*database-agnostic*: com suporte nativo a **PostgreSQL** e **SQL Server**), consumido por um modelo analítico e painel executivo no **Power BI**.

### 1.2 Fontes de Dados e Natureza Contábil

* **Planilha de Séries Históricas de RI:** `Dados historicos Meliuz_3T26.xlsx` disponibilizada pela diretoria de Relações com Investidores, contendo o histórico trimestral contínuo de $1\text{T}19$ a $3\text{T}26$.

* **Demonstrações Contábeis da CVM (ITRs):** Informações Trimestrais intermediárias consolidadas sujeitas a **revisão especial/limitada** pelos auditores independentes da PwC (conforme as normas NBC TR 2410 / ISRE 2410), utilizadas como balizador para batimento e reconciliação de métricas.

### 1.3 Delimitação de Escopo

* **Em Escopo:**

  * **Demonstrações Financeiras Consolidadas:** Aba `Finan. Cons. | Finan. Cons.` (DRE gerencial, Balanço Patrimonial Consolidado e DFC consolidada pelo Método Indireto).

  * **Métricas Operacionais de Shopping & Fintech:** Aba `Dados Oper. | Oper. Data` (GMV Shopping Brasil, Take Rate Bruto, Take Rate Líquido, Contas Totais, TPV e cartões da parceria com Banco BV).

  * **Estratégia de Tesouraria em Bitcoin:** Aba `Bitcoin Tesou. | Bitcoin Treas.` (saldo em custódia de reserva, custo de aquisição, preço médio e métricas por ação).

* **Fora de Escopo:**

  * Abas de operações segregadas ou descontinuadas (`Finan. Bankly.` e a visão individual não-consolidada `Finan. Contro. | Finan. Parent.`).

  * Colunas de consolidação anual estática (2019 a 2025), visto que a agregação anual é calculada dinamicamente pelo Data Warehouse e pelo Power BI a partir dos trimestres individuais.

## 2. Estrutura do Repositório

```
dw-bi-financeiro-meliuz/
│
├── data/
│   └── Dados historicos Meliuz_3T26.xlsx
│
├── database/
│   ├── postgresql/
│   │   ├── 01_ddl_schema.sql
│   │   └── 02_views_analiticas.sql
│   └── sqlserver/
│       ├── 01_ddl_schema.sql
│       └── 02_views_analiticas.sql
│
├── etl/
│   ├── config.py            # conexão (variáveis de ambiente / .env) e caminho dos dados
│   ├── extractors.py        # leitura da planilha, regras contábeis e desagregação temporal
│   ├── loaders.py           # carga idempotente (MERGE / UPSERT) por tabela
│   ├── main.py              # orquestrador e linha de comando
│   └── requirements.txt
│
├── tests/                   # suíte pytest (reconciliações contábeis, integridade, config/CLI)
├── .github/workflows/       # CI: pytest em push e pull request
├── powerbi/
│   └── dCalendario.m
│
├── docs/
│   └── DOCUMENTACAO_ARQUITETURA_BI_FINANCEIRO_MELIUZ_CASH3.md
│
├── .env.example             # modelo das variáveis de ambiente (copiar para .env)
├── pytest.ini
└── requirements-dev.txt
```

> O relatório do Power BI (`.pbix`) **não é versionado** neste repositório; apenas o script do calendário em Power Query (`dCalendario.m`) e as medidas DAX documentadas na seção 6.

## 3. Fundamentos de Negócio e Particularidades Contábeis

### 3.1 Modelo de Operação e Reconhecimento

1. **Receita via Take Rate:** A Méliuz remunera-se percentualmente sobre o volume transacionado no e-commerce parceiro (GMV).

2. **Ciclo de Vida do Cashback:**

   * Na DRE (regime de competência), o custo de cashback é provisionado no momento em que a compra é confirmada.

   * Na DFC (regime de caixa), o desembolso efetivo só é registrado no momento em que o usuário resgata o saldo financeiro para sua conta bancária.

3. **Mapeamento do Bitcoin no Balanço e DFC:**

   * A Méliuz adotou formalmente a estratégia de *Bitcoin Treasury Company* em 2025.

   * As aquisições de Bitcoin para reserva de valor são classificadas contabilmente como **Ativo Intangível (CPC 04 / IAS 38)** pelo critério de custo deduzido de perdas por redução ao valor recuperável (*impairment*).

   * Na DFC, as compras de Bitcoin entram na linha de **"Adições ao intangível"** das Atividades de Investimento (-R$ 360.136 mil em 2025, dos quais R$ 350.169 mil referem-se a aquisições de Bitcoin, conforme discriminado na Nota Explicativa nº 9 do ITR). As alienações parciais entram em **"Recebimento pela venda de Bitcoin"** (R$ 29.350 mil no $3\text{T}26$).

4. **Segregação do Impairment Histórico e Impacto Setorial:**

   * O impairment de -R$ 82.995 mil registrado no $2\text{T}24$ decorreu do teste de recuperabilidade realizado em 30/06/2024 sobre a controlada **Picodi** (abrangendo ágio/*goodwill* de R$ 78.797 mil e marca de R$ 955 mil, totalizando R$ 79.752 mil), somado à baixa contábil de R$ 3.243 mil de ativos intangíveis da plataforma de desenvolvimento interno.

   * **Impacto na Análise por Segmentos:** Na análise setorial e nas conciliações de EBITDA Ajustado, essa perda deve ser atribuída exclusivamente ao segmento **B2C Internacional (Picodi)**, evitando distorções na rentabilidade operacional apurada pelo B2C Nacional.

   * Em contrapartida, os impairments registrados a partir de 2025 decorrem prioritariamente do ajuste a valor justo na cotação do Bitcoin e devem ser atribuídos ao segmento **Tesouraria Bitcoin**.

### 3.2 Tratamento de Sinal Contábil

Na planilha gerencial da Méliuz, custos e despesas já são grafados como valores negativos (ex.: Cashback em 2025 é grafado como `-209.256`).

* Os dados são persistidos no banco mantendo rigorosamente o valor numérico original extraído.

* A coluna `natureza_sinal` é um **metadado puramente informativo** derivado do histórico. Em contas de sinal misto (ex.: variações de capital de giro na DFC, que oscilam entre positivo e negativo dependendo do trimestre), os relatórios e medidas em DAX utilizam diretamente o valor numérico armazenado (`valor_discreto` e `valor_ytd`), sem aplicação de multiplicadores cegos.

### 3.3 Dinâmica Temporal: Desagregação da DFC, Saldos de Estoque e YTD da DRE

* **DRE (Fluxo):** O valor nativo é o discreto trimestral. O YTD é gerado pelo pipeline via soma acumulada intra-anual:

  $$
  \text{DRE}_{ytd, nT} = \sum_{i=1}^{n} \text{DRE}_{discreto, iT}
  $$

* **DFC (Atividades de Fluxo — Operacional, Investimento, Financiamento e Efeito Cambial):** O valor nativo é o YTD. O valor discreto é calculado pelo delta trimestral:

  $$
  \text{DFC}_{discreto, 1T} = \text{DFC}_{ytd, 1T}
  $$

  $$
  \text{DFC}_{discreto, nT} = \text{DFC}_{ytd, nT} - \text{DFC}_{ytd, (n-1)T} \quad (n \in \{2, 3, 4\})
  $$

* **DFC (Saldos de Caixa — Estoque):** As linhas de saldo inicial e saldo final de caixa representam posições estáticas de balanço (estoque financeiro). Nelas, o valor discreto é idêntico ao saldo real reportado:

  $$
  \text{Saldo}_{discreto} = \text{Saldo}_{ytd} = \text{Saldo em Caixa}
  $$

* **Sanitização de Séries Incompletas:** Os dados da DFC em 2019 e no $1\text{T}20$/$2\text{T}20$ possuem zeros artificiais na planilha. O pipeline define esses períodos como `NULL`, **inclusive os saldos de caixa** (linhas "No início/No final do exercício"): como não há DFC nesses trimestres, o zero da fonte representa ausência de dado. No $3\text{T}20$, o valor reportado reflete o acumulado de 9 meses sem base de comparação anterior; logo, o pipeline armazena o valor em `valor_ytd` e define `valor_discreto = NULL`.

* **Zeros anteriores à primeira medição (métricas operacionais):** o *take rate* bruto só é medido a partir do $3\text{T}20$ e o líquido a partir do $1\text{T}21$; os zeros que a planilha traz antes disso são tratados como `NULL`. Um zero **depois** da primeira medição real é preservado.

* **Precisão numérica:** a planilha traz valores em R\$ mil com até 5 casas decimais (ex.: `-62500.91196`) e o *take rate* como fração com até 10 casas. O pipeline arredonda a 5 casas (valores contábeis) e a 10 (métricas), eliminando ruído de ponto flutuante, e os DDLs usam `NUMERIC(18,5)` / `DECIMAL(18,5)` e `NUMERIC(18,10)` / `DECIMAL(18,10)` para não perder precisão na carga.

* **Notas de rodapé coladas ao rótulo:** alguns rótulos chegam da planilha com o dígito da nota de rodapé (ex.: `Outros5`, `Publicidade e propaganda4`). O pipeline remove esse dígito final antes de gerar o `id_conta`. Em consequência, `Outros` aparece duas vezes no mesmo subgrupo da DRE (o filho de *Cashback* e a linha operacional); o contador de ocorrência as distingue e a coluna `conta_exibicao` (seção 6.3) as separa nos relatórios.

## 4. Modelo de Dados Relacional (Star Schema)

A modelagem física separa as movimentações financeiras das métricas operacionais heterogêneas:

```
       ┌────────────────────────┐         ┌────────────────────────┐
       │    dim_plano_contas    │         │ dim_metrica_operacional│
       ├────────────────────────┤         ├────────────────────────┤
       │ PK  id_conta           │         │ PK  id_metrica         │
       │     demonstrativo      │         │     categoria          │
       │     secao_contabil     │         │     subgrupo           │
       │     subgrupo           │         │     nome_metrica       │
       │     descricao_conta    │         │     unidade_medida     │
       │     tipo_conta         │         └───────────┬────────────┘
       │     nivel_hierarquia   │                     │ 1
       │     ordem_exibicao     │                     │
       │     natureza_sinal     │                     │ N
       └───────────┬────────────┘         ┌───────────┴────────────────┐
                   │ 1                    │fato_indicadores_operacionais│
                   │                      ├────────────────────────────┤
                   │ N                    │ PK,FK id_metrica           │
       ┌───────────┴────────────────┐     │ PK    data_fechamento      │
       │  fato_movimento_contabil   │     │       periodo_codigo       │
       ├────────────────────────────┤     │       valor_metrica        │
       │ PK,FK id_conta             │     │       data_carga           │
       │ PK    data_fechamento      │     └────────────────────────────┘
       │       periodo_codigo       │
       │       valor_discreto       │     (O relacionamento com o tempo
       │       valor_ytd            │      no Power BI é realizado via
       │       data_carga           │      campo data_fechamento)
       └────────────────────────────┘

```

### 4.1 DDL — PostgreSQL

```
-- 1. Dimensão Plano de Contas
CREATE TABLE IF NOT EXISTS dim_plano_contas (
    id_conta VARCHAR(64) PRIMARY KEY,
    demonstrativo VARCHAR(10) NOT NULL,            -- 'DRE', 'BP', 'DFC'
    secao_contabil VARCHAR(50) NOT NULL,           -- 'DRE', 'BP', 'DFC'
    subgrupo VARCHAR(50) NOT NULL,                 -- 'FLUXO_OPERACIONAL', 'EFEITO_CAMBIAL', etc.
    descricao_conta VARCHAR(255) NOT NULL,
    tipo_conta VARCHAR(20) NOT NULL,               -- 'Analítica', 'Sintética', 'Gerencial'
    nivel_hierarquia SMALLINT NOT NULL,            -- 1 (Pai), 2 (Filho)
    ordem_exibicao INT NOT NULL,
    natureza_sinal SMALLINT NOT NULL DEFAULT 1     -- Metadado de apresentação (1: Positivo, -1: Negativo)
);

-- 2. Fato Movimentação Contábil
CREATE TABLE IF NOT EXISTS fato_movimento_contabil (
    id_conta VARCHAR(64) NOT NULL REFERENCES dim_plano_contas(id_conta),
    data_fechamento DATE NOT NULL,
    periodo_codigo VARCHAR(10) NOT NULL,
    valor_discreto NUMERIC(18, 5),
    valor_ytd NUMERIC(18, 5),
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
    unidade_medida VARCHAR(20) NOT NULL            -- 'R$ MIL', '%', 'UNIDADES', 'BTC', 'USD', 'SATS'
);

-- 4. Fato Indicadores Operacionais
CREATE TABLE IF NOT EXISTS fato_indicadores_operacionais (
    id_metrica VARCHAR(64) NOT NULL REFERENCES dim_metrica_operacional(id_metrica),
    data_fechamento DATE NOT NULL,
    periodo_codigo VARCHAR(10) NOT NULL,
    valor_metrica NUMERIC(18, 10) NOT NULL,
    data_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fato_indicadores PRIMARY KEY (id_metrica, data_fechamento)
);

CREATE INDEX IF NOT EXISTS idx_fato_ind_data ON fato_indicadores_operacionais(data_fechamento);

```

### 4.2 DDL — Microsoft SQL Server

```
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
    valor_discreto DECIMAL(18, 5),
    valor_ytd DECIMAL(18, 5),
    data_carga DATETIME DEFAULT GETDATE(),
    CONSTRAINT pk_fato_movimento PRIMARY KEY CLUSTERED (id_conta, data_fechamento)
);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_fato_mov_data' AND object_id = OBJECT_ID('fato_movimento_contabil'))
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
    valor_metrica DECIMAL(18, 10) NOT NULL,
    data_carga DATETIME DEFAULT GETDATE(),
    CONSTRAINT pk_fato_indicadores PRIMARY KEY CLUSTERED (id_metrica, data_fechamento)
);

IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_fato_ind_data' AND object_id = OBJECT_ID('fato_indicadores_operacionais'))
    CREATE NONCLUSTERED INDEX idx_fato_ind_data ON fato_indicadores_operacionais(data_fechamento);

```

## 5. Pipeline de Ingestão e Carga Automatizada (`etl/`)

> **Nota de revisão.** Esta seção continha uma cópia integral de uma versão anterior do pipeline (um único arquivo, `etl_meliuz_dw.py`, com a classe `MeliuzETLPipeline`). Essa versão foi substituída pela implementação modular descrita abaixo; a cópia foi removida para que a documentação não diverja do código. O código vigente é o da pasta `etl/`; a versão antiga permanece no histórico do git.

### 5.1 Módulos e fluxo

| Módulo | Responsabilidade |
|---|---|
| `config.py` | Resolve o destino e as credenciais por variáveis de ambiente (ou `.env`) e monta a conexão SQLAlchemy. Define `DATA_FOLDER` como caminho absoluto, independente do diretório de execução |
| `extractors.py` | Escolhe a planilha, localiza as seções, classifica as contas, desagrega no tempo e devolve DataFrames de dimensão e fato |
| `loaders.py` | Carga idempotente por tabela: staging, `MERGE` (SQL Server) ou `INSERT ... ON CONFLICT` (PostgreSQL) |
| `main.py` | Orquestra extração e carga dos dois domínios e expõe a linha de comando |

Fluxo de `main.py`:

1. Resolve a planilha: `--file` ou, por padrão, a mais recente em `data/`. O critério é o **trimestre no nome do arquivo** (ex.: `_3T26`); a data de modificação só vale se nenhum nome trouxer trimestre, e arquivos temporários do Office (`~$`) são ignorados.
2. Cria a engine a partir de `config.py`.
3. **Domínio 1 — Demonstrações financeiras:** `extract_financial_statements` → `load_dim_plano_contas` → `load_fato_movimento_contabil`.
4. **Domínio 2 — Indicadores operacionais e Bitcoin:** `extract_operational_indicators` → `load_dim_metrica_operacional` → `load_fato_indicadores_operacionais`.

### 5.2 Configuração e execução

Variáveis de ambiente (modelo em `.env.example`):

| Variável | Significado |
|---|---|
| `DW_DB_TYPE` | `sqlserver` (padrão) ou `postgresql` |
| `DW_DB_SERVER`, `DW_DB_NAME`, `DW_DB_PORT` | Servidor, banco e porta (opcional) |
| `DW_DB_USER`, `DW_DB_PASSWORD` | SQL Server: sem `DW_DB_USER`, usa autenticação integrada do Windows. PostgreSQL: `DW_DB_PASSWORD` é obrigatória |
| `DW_ODBC_DRIVER` | Padrão `ODBC Driver 17 for SQL Server` |

```bash
python etl/main.py
python etl/main.py --db postgresql --server localhost --database dwmeliuz
python etl/main.py --file "data/Dados historicos Meliuz_3T26.xlsx"
```

Nenhuma credencial é versionada. O arquivo `.env` é ignorado pelo git.

### 5.3 Regras de extração (`extractors.py`)

* **Localização das seções (`find_section_bounds`):** por âncoras de texto na coluna de rótulos (DRE, EBITDA, Balanço, Fluxo de Caixa). Se uma âncora não é encontrada, o pipeline **falha com `AssertionError`** em vez de carregar dado incorreto.
* **Trimestres (`detect_quarter_columns`):** lê o código `nTaa` do cabeçalho (`1T19 | 1Q19` → `1T19`), derivando a data de fechamento do último dia do trimestre e parando na coluna vazia que antecede os totais anuais. Os totais anuais da planilha não são carregados; a agregação anual é recalculada no banco e no Power BI.
* **Rótulos:** remove sobrescritos (¹²³) e dígitos de nota de rodapé colados ao final do texto, normaliza espaços e usa o resultado como `descricao_conta`.
* **`subgrupo`:** inferido pelos rótulos de cabeçalho de cada bloco (ex.: `ATIVO_CIRCULANTE`, `FLUXO_OPERACIONAL`, `SALDOS_CAIXA`, `VARIACAO_CAIXA_PERIODO`).
* **`tipo_conta`:** `Gerencial` (conciliação do EBITDA), `Sintética` (subtotais e totais) ou `Analítica` (demais). No balanço, a soma das analíticas de cada grupo (ativo circulante, passivo circulante e passivo não circulante) reproduz o subtotal informado pela RI, o que é verificado nos testes; uma conta mal classificada faz a soma deixar de fechar.
* **`id_conta`:** MD5 (16 primeiros caracteres hexadecimais) de `seção + subgrupo + rótulo`. Rótulos repetidos no mesmo subgrupo recebem um contador de ocorrência na ordem em que aparecem na planilha. **Consequência:** renomear um rótulo na fonte ou inserir uma linha repetida acima de outra altera ids; o pipeline não mantém tabela de equivalência.
* **Valor discreto e YTD:** DRE (fluxo, valor nativo é o discreto, YTD é a soma acumulada intra-anual), DFC (valor nativo é o YTD, o discreto é o delta trimestral, conforme seção 3.3), BP e saldos de caixa (estoque: discreto = YTD). Regras de `NULL` para séries incompletas na seção 3.3.
* **Precisão:** valores contábeis arredondados a 5 casas e métricas a 10, como descrito na seção 3.3.
* **Métricas operacionais (`extract_operational_indicators`):** o extrator identifica cada métrica pelo rótulo da fonte. Para o TPV, usa também o bloco da parceria BV ou da operação legada. Rótulos ausentes ou ambíguos interrompem a extração.

### 5.4 Carga (`loaders.py`)

Cada loader, em uma **única transação**:

1. grava o DataFrame em uma tabela de staging (`stg_*`);
2. aplica `MERGE` (SQL Server) ou `INSERT ... ON CONFLICT DO UPDATE` (PostgreSQL) com projeção explícita de colunas;
3. descarta a staging.

Como a staging é criada dentro da mesma transação, uma falha na carga desfaz também a staging, sem deixar tabelas `stg_*` órfãs. As cargas são idempotentes: reexecutar com a mesma planilha não duplica linhas. O upsert da dimensão de contas atualiza todas as colunas não-chave; os das fatos atualizam `valor_*` e `data_carga`.

> **Limitação conhecida:** uma reapresentação de números pela RI (por exemplo, a reclassificação decorrente da venda da Bankly, nota 3 da planilha) sobrescreve os valores anteriores sem manter histórico de versões.

---

## 6. Modelagem Tabular e DAX (Power BI)

### 6.1 Calendário em Power Query (M) (`dCalendario.m`)

Código em Power Query para geração dinâmica da dimensão de calendário contínua a partir de 2019:

```
let
    DataInicial = #date(2019, 1, 1),
    DataFinal = Date.EndOfYear(DateTime.Date(DateTime.LocalNow())),
    TotalDias = Duration.Days(DataFinal - DataInicial) + 1,
    ListaDatas = List.Dates(DataInicial, TotalDias, #duration(1, 0, 0, 0)),
    Tabela = Table.FromList(ListaDatas, Splitter.SplitByNothing(), {"Data"}, null, ExtraValues.Error),
    AlteraTipo = Table.TransformColumnTypes(Tabela, {{"Data", type date}}),
    AdicionaAno = Table.AddColumn(AlteraTipo, "Ano", each Date.Year([Data]), Int64.Type),
    AdicionaTrimestre = Table.AddColumn(AdicionaAno, "Trimestre", each Date.QuarterOfYear([Data]), Int64.Type),
    AdicionaPeriodo = Table.AddColumn(AdicionaTrimestre, "Periodo", each Text.From([Trimestre]) & "T" & Text.End(Text.From([Ano]), 2), type text),
    AdicionaMesAno = Table.AddColumn(AdicionaPeriodo, "MesAno", each Date.ToText([Data], "MMM/yy"), type text),
    AdicionaFimTrimestre = Table.AddColumn(AdicionaMesAno, "DataFimTrimestre", each Date.EndOfQuarter([Data]), type date)
in
    AdicionaFimTrimestre

```

*Relacionamentos no Modelo:*

* `dCalendario[Data]` $\xrightarrow{1:N}$ `fato_movimento_contabil[data_fechamento]`

* `dCalendario[Data]` $\xrightarrow{1:N}$ `fato_indicadores_operacionais[data_fechamento]`

### 6.2 Medidas em DAX

```
// =========================================================================
// 1. MEDIDAS DE EXIBIÇÃO TABULAR (MATRIZ POR CONTA)
// =========================================================================

// Exibe o valor do trimestre para cada conta (Analítica, Sintética ou Gerencial)
Valor Linha Relatório = 
SUM(fato_movimento_contabil[valor_discreto])

// Exibe o acumulado YTD por linha da matriz, ancorado na maior data fechada do período
// Impede a quadruplicação de valores quando o filtro abrange um ano civil inteiro
Valor Linha Relatório YTD = 
VAR DataMaxComMovimento = 
    CALCULATE(
        MAX(fato_movimento_contabil[data_fechamento]),
        KEEPFILTERS(fato_movimento_contabil[valor_ytd] <> BLANK())
    )
RETURN
    CALCULATE(
        SUM(fato_movimento_contabil[valor_ytd]),
        fato_movimento_contabil[data_fechamento] = DataMaxComMovimento
    )

// Exibe a linha homóloga do ano anterior na matriz (YoY por conta)
Valor Linha Relatório Ano Anterior = 
CALCULATE(
    [Valor Linha Relatório],
    DATEADD(dCalendario[Data], -1, YEAR)
)

// Variação percentual homóloga por conta na matriz
Valor Linha Relatório YoY % = 
VAR Atual = [Valor Linha Relatório]
VAR Anterior = [Valor Linha Relatório Ano Anterior]
RETURN
    IF(
        NOT ISBLANK(Atual) && NOT ISBLANK(Anterior) && Anterior <> 0,
        DIVIDE(Atual - Anterior, ABS(Anterior))
    )

// =========================================================================
// 2. MEDIDAS DE AGREGAÇÃO ANALÍTICA PURA (CARDS, TOTAIS E WATERFALL)
// =========================================================================

// Soma estrita de contas folha para gráficos de cascata e cartões sem duplicidade de subtotais
Total Analítico Discreto = 
CALCULATE(
    SUM(fato_movimento_contabil[valor_discreto]),
    dim_plano_contas[tipo_conta] = "Analítica"
)

// Acumulado do ano (YTD) apenas de contas folha analíticas
Total Analítico YTD = 
VAR DataMaxComMovimento = 
    CALCULATE(
        MAX(fato_movimento_contabil[data_fechamento]),
        KEEPFILTERS(fato_movimento_contabil[valor_ytd] <> BLANK())
    )
RETURN
    CALCULATE(
        SUM(fato_movimento_contabil[valor_ytd]),
        fato_movimento_contabil[data_fechamento] = DataMaxComMovimento,
        dim_plano_contas[tipo_conta] = "Analítica"
    )

// =========================================================================
// 3. BALANÇO PATRIMONIAL (SALDO SEMIADIATIVO)
// =========================================================================

// Avalia a fotografia na última data real reportada dentro do contexto filtrado
Saldo Balanço Patrimonial = 
VAR DataMaxComMovimento = 
    CALCULATE(
        MAX(fato_movimento_contabil[data_fechamento]),
        KEEPFILTERS(fato_movimento_contabil[valor_discreto] <> BLANK())
    )
RETURN
    CALCULATE(
        SUM(fato_movimento_contabil[valor_discreto]),
        fato_movimento_contabil[data_fechamento] = DataMaxComMovimento,
        dim_plano_contas[demonstrativo] = "BP"
    )

// =========================================================================
// 4. MEDIDAS DIRETAS DE MÉTRICAS OFICIAIS REPORTADAS
// =========================================================================

Receita Líquida Publicada = 
CALCULATE(
    SUM(fato_movimento_contabil[valor_discreto]),
    dim_plano_contas[descricao_conta] = "Receita operacional líquida"
)

EBITDA Publicado = 
CALCULATE(
    SUM(fato_movimento_contabil[valor_discreto]),
    dim_plano_contas[descricao_conta] = "EBITDA"
)

EBITDA Ajustado Publicado = 
CALCULATE(
    SUM(fato_movimento_contabil[valor_discreto]),
    dim_plano_contas[descricao_conta] = "EBITDA Ajustado"
)

Lucro Líquido Publicado = 
CALCULATE(
    SUM(fato_movimento_contabil[valor_discreto]),
    dim_plano_contas[descricao_conta] = "Lucro líquido (prejuízo) do exercício"
)

```

### 6.3 Desambiguação de Contas Homônimas e Ordenação Contábil (`conta_exibicao`)

Como o plano de contas consolidado apresenta descrições idênticas em grupos distintos (por exemplo, `"Outros"` no Ativo Circulante e Passivo Circulante; `"Depreciação e amortização"` na DRE e DFC; `"Caixa e equivalentes de caixa"` no BP e na DFC), a ordenação direta da coluna `descricao_conta` por `ordem_exibicao` viola a restrição de cardinalidade `1:1` exigida pelo motor tabular do Power BI.

Para preservar a hierarquia contábil oficial nas matrizes sem exibir códigos técnicos artificiais nos rótulos, implementou-se a coluna calculada `conta_exibicao` na dimensão `dim_plano_contas`, concatenando caracteres invisíveis de largura zero (`UNICHAR(8203)`) de acordo com a ordem de ocorrência de cada descrição:

```dax
conta_exibicao = 
VAR Ocorrencia = 
    RANKX(
        FILTER(
            dim_plano_contas,
            dim_plano_contas[descricao_conta] = EARLIER(dim_plano_contas[descricao_conta])
        ),
        dim_plano_contas[ordem_exibicao],
        ,
        ASC,
        DENSE
    )
RETURN
dim_plano_contas[descricao_conta] & REPT(UNICHAR(8203), Ocorrencia - 1)
```

Com essa abordagem, cada linha assume uma assinatura única (permitindo classificar `conta_exibicao` por `ordem_exibicao` e impedindo a agregação indevida de contas homônimas de grupos distintos), mantendo a renderização visual limpa nos relatórios.

---

## 7. Rastreabilidade e Auditoria Contábil

* **Natureza da Opinião:** Os demonstrativos trimestrais (ITRs) possuem **relatório de revisão especial/limitada** emitido pela PwC nos termos da NBC TR 2410 / ISRE 2410. A auditoria completa com opinião formal aplica-se exclusivamente às demonstrações financeiras anuais (DFPs).

* **Parâmetros de Auditoria (Metas para Homologação do 3T26):**

  * Receita Operacional Líquida (3T26): **R\$ 96.084 mil**.

  * Lucro Líquido Consolidado (3T26): **R\$ 113.698 mil**.

  * Caixa Líquido das Atividades Operacionais (YTD 9M26): **R\$ 35.047 mil** (conciliado exatamente pela soma das contas analíticas com o ponto de partida do lucro contábil).

  * Caixa Líquido das Atividades de Financiamento (YTD 9M26): **-R\$ 41.417 mil** (excluindo os **-R\$ 631 mil** isolados no subgrupo `EFEITO_CAMBIAL`).

  * Recebimento pela Venda de Bitcoin (DFC Investimento YTD 9M26): **R\$ 29.350 mil**.

  * Posição em Bitcoin em Tesouraria (3T26): **526,69 BTC**.

### 7.1 Reconciliações automatizadas

A pasta `tests/` valida a saída do extrator contra identidades contábeis, a cada execução de `pytest` (e pelo workflow de CI em `.github/workflows`). Principais verificações:

* **Balanço:** ativo = passivo + patrimônio líquido; ativo = circulante + não circulante; subtotais = soma das contas analíticas.
* **DRE:** receita + custos = resultado bruto; cadeia até o lucro líquido; custos = soma dos componentes; EBITDA e EBITDA ajustado; YTD do 4T = soma dos quatro trimestres = coluna anual da própria planilha.
* **DFC:** caixa operacional + investimento + financiamento + câmbio = variação líquida de caixa; saldo inicial + variação = saldo final; saldo inicial do ano = saldo final do 4T anterior; fluxos anuais = YTD do 4T.
* **Cruzadas:** o resultado antes dos tributos da DRE é igual ao da DFC **das operações em continuidade** (a linha consolidada da DFC inclui operações descontinuadas); o caixa final da DFC é igual ao caixa do balanço, ajustado pelo caixa de operações descontinuadas (a seguir).
* **Bitcoin:** a queda da posição em BTC coincide com o recebimento pela venda de Bitcoin na DFC, e o preço médio de compra não muda na venda.
* **Integridade:** 31 trimestres contíguos (1T19 a 3T26), sem chaves duplicadas, sem fato órfão, valores dentro da precisão do DDL, rótulos sem dígito de nota.

A tolerância é de 1,5 (R\$ mil) e cobre apenas o arredondamento da própria fonte.

#### Caixa da DFC versus caixa do balanço em 2T23 e 3T23

Nesses dois trimestres o caixa final da DFC consolidada excede o "Caixa e equivalentes de caixa" do balanço. A causa, conferida nos ITRs (nota 3.a e nota 8), é a reclassificação, por força do CPC 31 / IFRS 5, do caixa da Bankly e da Acessopar para "ativo mantido para venda" após o acordo de venda ao Banco BV (1º de junho de 2023): o balanço o exclui do caixa, mas a DFC o mantém no saldo final.

| Trimestre | Caixa no balanço (R\$ mil) | Caixa de operações descontinuadas (R\$ mil) | Saldo final da DFC (R\$ mil) |
|---|---|---|---|
| 2T23 | 59.704 | 11.854 (Bankly 11.669 + Acessopar 185) | 71.558 |
| 3T23 | 165.689 | 92.949 (Bankly 92.767 + Acessopar 182) | 258.638 |

Não se trata de erro da planilha nem do pipeline. Os testes incorporam esse ajuste de forma explícita e falham se ele deixar de ser necessário.

#### Conferência dos parâmetros do 3T26

Os valores da lista de parâmetros acima (receita, lucro líquido, caixa operacional, caixa de financiamento, recebimento pela venda de Bitcoin e posição em Bitcoin) foram conferidos no ITR consolidado do 3T26.
