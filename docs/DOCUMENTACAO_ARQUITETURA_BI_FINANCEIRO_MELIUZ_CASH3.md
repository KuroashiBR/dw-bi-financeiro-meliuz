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
│   ├── etl_meliuz_dw.py
│   └── requirements.txt
│
├── powerbi/
│   ├── dCalendario.m
│   └── relatorio_financeiro_meliuz.pbix
│
└── docs/
    └── PROJETO_DW_BI_FINANCEIRO_MELIUZ.md

```

## 3. Fundamentos de Negócio e Particularidades Contábeis

### 3.1 Modelo de Operação e Reconhecimento

1. **Receita via Take Rate:** A Méliuz remunera-se percentualmente sobre o volume transacionado no e-commerce parceiro (GMV).

2. **Ciclo de Vida do Cashback:**

   * Na DRE (regime de competência), o custo de cashback é provisionado no momento em que a compra é confirmada.

   * Na DFC (regime de caixa), o desembolso efetivo só é registrado no momento em que o usuário resgata o saldo financeiro para sua conta bancária.

3. **Mapeamento do Bitcoin no Balanço e DFC:**

   * A Méliuz adotou formalmente a estratégia de *Bitcoin Treasury Company* em 2025.

   * As aquisições de Bitcoin para reserva de valor são classificadas contabilmente como **Ativo Intangível (CPC 04 / IAS 38)** pelo critério de custo deduzido de perdas por redução ao valor recuperável (*impairment*).

   * Na DFC, as compras de Bitcoin entram na linha de **"Adições ao intangível"** das Atividades de Investimento ($-\text{R\$} 360.136$ mil em 2025, dos quais $\text{R\$} 350.169$ mil referem-se a aquisições de Bitcoin, conforme discriminado na Nota Explicativa nº 9 do ITR). As alienações parciais entram em **"Recebimento pela venda de Bitcoin"** ($\text{R\$} 29.350$ mil no $3\text{T}26$).

4. **Segregação do Impairment Histórico e Impacto Setorial:**

   * O impairment de $-\text{R\$} 82.995$ mil registrado no $2\text{T}24$ decorreu do teste de recuperabilidade realizado em 30/06/2024 sobre a controlada **Picodi** (abrangendo ágio/*goodwill* de $\text{R\$} 78.797$ mil e marca de $\text{R\$} 955$ mil, totalizando $\text{R\$} 79.752$ mil), somado à baixa contábil de $\text{R\$} 3.243$ mil de ativos intangíveis da plataforma de desenvolvimento interno.

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

* **Sanitização de Séries Incompletas:** Os dados da DFC em 2019 e no $1\text{T}20$/$2\text{T}20$ possuem zeros artificiais na planilha. O pipeline define esses períodos como `NULL`. No $3\text{T}20$, o valor reportado reflete o acumulado de 9 meses sem base de comparação anterior; logo, o pipeline armazena o valor em `valor_ytd` e define `valor_discreto = NULL`.

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
    valor_discreto NUMERIC(18, 2),
    valor_ytd NUMERIC(18, 2),
    data_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fato_movimento PRIMARY KEY (id_conta, data_fechamento)
);

CREATE INDEX idx_fato_mov_data ON fato_movimento_contabil(data_fechamento);

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
    valor_metrica NUMERIC(18, 4) NOT NULL,
    data_carga TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_fato_indicadores PRIMARY KEY (id_metrica, data_fechamento)
);

CREATE INDEX idx_fato_ind_data ON fato_indicadores_operacionais(data_fechamento);

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

```

## 5. Pipeline de Ingestão e Carga Automatizada (`etl_meliuz_dw.py`)

```
"""
Pipeline de Ingestão e Modelagem Dimensional - Méliuz (CASH3)
Executa extração, sanitização, desagregação temporal e upsert idempotente
para PostgreSQL e SQL Server com subgrupos rigorosos e reconciliação da DFC.
"""

import os
import re
import glob
import hashlib
import logging
import pandas as pd
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class MeliuzETLPipeline:
    def __init__(self, data_folder="./", db_type="postgresql", conn_string=None):
        self.data_folder = data_folder
        self.db_type = db_type.lower()
        self.conn_string = conn_string
        self.engine = create_engine(conn_string) if conn_string else None

    def get_latest_file(self):
        """Identifica a planilha mais recente, ignorando arquivos temporários (~$)."""
        pattern = os.path.join(self.data_folder, "*Meliuz*.xlsx")
        files = [f for f in glob.glob(pattern) if not os.path.basename(f).startswith("~$")]
        if not files:
            raise FileNotFoundError(f"Nenhum arquivo válido encontrado em {self.data_folder}")
        return max(files, key=os.path.getmtime)

    @staticmethod
    def generate_hash_id(parts):
        """Gera hash determinístico MD5 baseado nas partes constitutivas da chave natural."""
        clean_parts = [re.sub(r'[^a-zA-Z0-9_]', '', str(p).upper().replace(' ', '_')) for p in parts]
        raw_key = "_".join(clean_parts).encode('utf-8')
        return hashlib.md5(raw_key).hexdigest()[:16]

    def detect_quarter_columns(self, header_row):
        """Varre os trimestres parando na coluna vazia que antecede os anos cheios."""
        quarters = []
        for c_idx, val in header_row.items():
            if pd.isna(val):
                if len(quarters) > 0:
                    break
                continue
            val_str = str(val).split('|')[0].strip()
            match = re.search(r'([1-4]T\d{2})', val_str, re.IGNORECASE)
            if match:
                q_code = match.group(1).upper()
                q_num = int(q_code[0])
                yy = int(q_code[2:])
                full_year = 2000 + yy if yy < 50 else 1900 + yy
                m_end = q_num * 3
                d_end = 31 if q_num in (1, 4) else 30
                quarters.append({
                    "col_idx": c_idx,
                    "periodo_codigo": q_code,
                    "ano": full_year,
                    "trimestre": q_num,
                    "data_fechamento": f"{full_year}-{m_end:02d}-{d_end:02d}"
                })
        return quarters

    def find_section_bounds(self, df_fin):
        """Localiza os limites das seções por âncoras de texto com asserção estrita."""
        bounds = {}
        for idx, val in df_fin['Unnamed: 2'].items():
            if pd.isna(val):
                continue
            s = str(val).strip().lower()
            if 'dre (r$ mil)' in s:
                bounds['dre_start'] = idx + 1
            elif s == 'ebitda':
                bounds['ebitda_start'] = idx
            elif 'balanço patrimonial (r$ mil)' in s:
                bounds['dre_end'] = idx - 1
                bounds['bp_start'] = idx + 1
            elif 'fluxo de caixa (r$ mil)' in s:
                bounds['bp_end'] = idx - 1
                bounds['dfc_start'] = idx + 1
            elif 'variação líquida de caixa e equivalentes de caixa' in s and 'dfc_start' in bounds and idx > 250:
                bounds['dfc_end'] = idx

        required_bounds = ['dre_start', 'ebitda_start', 'dre_end', 'bp_start', 'bp_end', 'dfc_start', 'dfc_end']
        for rb in required_bounds:
            assert rb in bounds, f"Falha de integridade: âncora textual para '{rb}' não foi localizada."
        return bounds

    def parse_financial_statements(self, file_path):
        """Extrai DRE, Balanço e DFC tratando colisões, subtotais e desagregação."""
        df = pd.read_excel(file_path, sheet_name='Finan. Cons. | Finan. Cons.')
        quarters = self.detect_quarter_columns(df.iloc[2])
        bounds = self.find_section_bounds(df)

        dim_contas = {}
        fato_contabil = []
        seen_keys = {}

        current_sec = "HEADER"
        current_sub = "GERAL"

        ignore_exact_headers = {
            'balanço patrimonial (r$ mil)', 'fluxo de caixa (r$ mil)', 'dre (r$ mil)',
            'período acumulado', 'atividades operacionais', 'atividades de investimento',
            'atividades de financiamento'
        }

        for r in range(bounds['dre_start'], bounds['dfc_end'] + 1):
            raw_pt = df.iloc[r]['Unnamed: 2']
            if pd.isna(raw_pt) or str(raw_pt).strip().startswith('¹') or str(raw_pt).strip().lower() == 'notas:':
                continue

            pt_str = str(raw_pt)
            indent = len(pt_str) - len(pt_str.lstrip(' '))

            # Limpeza: remove notas sobrescritas (¹²³⁴⁵⁶⁷⁸⁹⁰) e normaliza espaços
            clean_pt = re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]', '', pt_str).strip()
            clean_pt = re.sub(r'\s+', ' ', clean_pt)
            clean_lower = clean_pt.lower()

            # -------------------------------------------------------------
            # ETAPA 1: ATUALIZAÇÃO SEMÂNTICA DE ESTADO (SEÇÃO E SUBGRUPO)
            # Processado ANTES de qualquer descarte para que os cabeçalhos
            # definam corretamente o contexto dos próximos lançamentos.
            # -------------------------------------------------------------
            if r < bounds['ebitda_start']:
                current_sec = "DRE"
                current_sub = "RESULTADO_OPERACIONAL"
            elif r <= bounds['dre_end']:
                current_sec = "DRE"
                current_sub = "CONCILIACAO_EBITDA"
            elif r < bounds['dfc_start']:
                current_sec = "BP"
                if 'ativo circulante' in clean_lower and 'total' not in clean_lower:
                    current_sub = "ATIVO_CIRCULANTE"
                elif 'ativo não circulante' in clean_lower and 'total' not in clean_lower:
                    current_sub = "ATIVO_NAO_CIRCULANTE"
                elif 'realizável a longo prazo' in clean_lower and 'total' not in clean_lower:
                    current_sub = "ATIVO_RLP"
                elif clean_lower == 'investimentos':
                    current_sub = "ATIVO_INVESTIMENTOS"
                elif clean_lower == 'imobilizado':
                    current_sub = "ATIVO_IMOBILIZADO"
                elif clean_lower == 'intangível':
                    current_sub = "ATIVO_INTANGIVEL"
                elif 'passivo circulante' in clean_lower and 'total' not in clean_lower:
                    current_sub = "PASSIVO_CIRCULANTE"
                elif 'passivo não circulante' in clean_lower and 'total' not in clean_lower:
                    current_sub = "PASSIVO_NAO_CIRCULANTE"
                elif 'patrimônio líquido' in clean_lower and 'total' not in clean_lower and 'controladores' not in clean_lower:
                    current_sub = "PATRIMONIO_LIQUIDO"
            else:
                current_sec = "DFC"
                if 'atividades operacionais' in clean_lower and 'caixa' not in clean_lower:
                    current_sub = "FLUXO_OPERACIONAL"
                elif 'atividades de investimento' in clean_lower and 'caixa' not in clean_lower:
                    current_sub = "FLUXO_INVESTIMENTO"
                elif 'atividades de financiamento' in clean_lower and 'caixa' not in clean_lower:
                    current_sub = "FLUXO_FINANCIAMENTO"
                elif any(k in clean_lower for k in ['efeito de variação de câmbio', 'efeito de variacao de cambio', 'variação cambial s/ caixa']):
                    current_sub = "EFEITO_CAMBIAL"
                elif any(k in clean_lower for k in ['saldo inicial', 'no início do período', 'no início do exercício', 'saldo final', 'no final do período', 'no final do exercício']):
                    current_sub = "SALDOS_CAIXA"
                elif 'variação líquida de caixa' in clean_lower:
                    if current_sub in ["FLUXO_FINANCIAMENTO", "FLUXO_INVESTIMENTO", "FLUXO_OPERACIONAL", "EFEITO_CAMBIAL"]:
                        current_sub = "VARIACAO_CAIXA_PERIODO"
                    else:
                        current_sub = "VARIACAO_CAIXA_TOTAL"

            # -------------------------------------------------------------
            # ETAPA 2: DESCARTE DE CABEÇALHOS TEXTUAIS
            # -------------------------------------------------------------
            if clean_lower in ignore_exact_headers:
                continue

            # -------------------------------------------------------------
            # ETAPA 3: RESOLUÇÃO DE IDENTIFICADOR ÚNICO E DETERMINÍSTICO
            # -------------------------------------------------------------
            base_key = f"{current_sec}_{current_sub}_{clean_pt.upper()}"
            seen_keys[base_key] = seen_keys.get(base_key, 0) + 1
            occ = seen_keys[base_key]
            unique_key_parts = [current_sec, current_sub, clean_pt] if occ == 1 else [current_sec, current_sub, clean_pt, str(occ)]
            id_conta = self.generate_hash_id(unique_key_parts)

            # Classificação do Tipo de Conta
            if current_sub == "CONCILIACAO_EBITDA":
                tipo_conta = "Gerencial"
            elif any(k in clean_lower for k in [
                'resultado bruto', 'total do ativo', 'total do passivo', 'total do patrimônio',
                'lucro líquido', 'caixa líquido', 'variação líquida',
                'resultado ajustado', 'no final do exercício', 'no início do exercício',
                'no final do período', 'no início do período', 'custos e despesas operacionais',
                'patrimônio líquido atribuído a controladores'
            ]):
                tipo_conta = "Sintética"
            elif current_sec == "DRE" and any(k in clean_lower for k in ['lucro (prejuízo) antes', 'resultado do período antes dos tributos', 'resultado antes dos tributos']):
                tipo_conta = "Sintética"
            elif current_sec == "DFC" and clean_lower == 'resultado do período antes dos tributos sobre o lucro':
                # Subtotal (continuidade + descontinuadas): evita contar o ponto de partida duas vezes na ponte do caixa operacional
                tipo_conta = "Sintética"
            elif clean_pt == "Cashback" and current_sec == "DRE":
                tipo_conta = "Sintética"
            else:
                # As linhas filhas do ponto de partida da DFC (continuidade e descontinuadas) permanecem como Analítica para compor a ponte do fluxo operacional
                tipo_conta = "Analítica"

            # Coleta temporal dos dados numéricos
            series_vals = {}
            numeric_samples = []
            for q in quarters:
                val = df.iloc[r][q["col_idx"]]
                try:
                    num_val = float(val) if pd.notna(val) else None
                except (ValueError, TypeError):
                    num_val = None
                series_vals[q["periodo_codigo"]] = num_val
                if num_val is not None:
                    numeric_samples.append(num_val)

            mean_val = (sum(numeric_samples) / len(numeric_samples)) if numeric_samples else 0.0
            natureza_sinal = -1 if mean_val < 0 else 1

            nivel = 2 if indent > 0 else 1
            dim_contas[id_conta] = {
                "id_conta": id_conta,
                "demonstrativo": current_sec,
                "secao_contabil": current_sec,
                "subgrupo": current_sub,
                "descricao_conta": clean_pt,
                "tipo_conta": tipo_conta,
                "nivel_hierarquia": nivel,
                "ordem_exibicao": r * 10,
                "natureza_sinal": natureza_sinal
            }

            # Desagregação da DFC, Tratamento de Estoque e Acumulação da DRE
            running_dre_ytd = 0.0
            current_dre_year = None

            for idx, q in enumerate(quarters):
                p_code = q["periodo_codigo"]
                cur_val = series_vals[p_code]
                v_discreto = cur_val
                v_ytd = cur_val

                if current_sec == "DRE":
                    if q["ano"] != current_dre_year:
                        current_dre_year = q["ano"]
                        running_dre_ytd = 0.0

                    if cur_val is not None:
                        running_dre_ytd += cur_val
                        v_discreto = cur_val
                        v_ytd = running_dre_ytd
                    else:
                        v_discreto = None
                        v_ytd = None

                elif current_sec == "DFC":
                    if current_sub == "SALDOS_CAIXA":
                        # Saldos de caixa representam estoque financeiro (análogo ao Balanço Patrimonial)
                        v_discreto = cur_val
                        v_ytd = cur_val
                    else:
                        # 2019 e primeiros trimestres de 2020 não possuem apuração na série
                        if q["ano"] < 2020 or (q["ano"] == 2020 and q["trimestre"] in [1, 2]):
                            v_discreto = None
                            v_ytd = None
                        elif q["ano"] == 2020 and q["trimestre"] == 3:
                            # 3T20 reflete acumulado de 9M sem base discreta anterior
                            v_discreto = None
                            v_ytd = cur_val
                        elif cur_val is not None:
                            v_ytd = cur_val
                            if q["trimestre"] == 1:
                                v_discreto = cur_val
                            else:
                                prev_code = quarters[idx - 1]["periodo_codigo"]
                                prev_val = series_vals.get(prev_code)
                                v_discreto = (cur_val - prev_val) if prev_val is not None else None

                elif current_sec == "BP":
                    v_discreto = cur_val
                    v_ytd = cur_val

                fato_contabil.append({
                    "id_conta": id_conta,
                    "data_fechamento": q["data_fechamento"],
                    "periodo_codigo": p_code,
                    "valor_discreto": v_discreto,
                    "valor_ytd": v_ytd
                })

        return pd.DataFrame(list(dim_contas.values())), pd.DataFrame(fato_contabil)

    def parse_operational_indicators(self, file_path):
        """Extrai métricas operacionais e da tesouraria de Bitcoin com sanitização de zeros."""
        xls = pd.ExcelFile(file_path)
        df_op = pd.read_excel(xls, sheet_name='Dados Oper. | Oper. Data')
        df_btc = pd.read_excel(xls, sheet_name='Bitcoin Tesou. | Bitcoin Treas.')
        quarters = self.detect_quarter_columns(df_op.iloc[2])

        dim_metricas = [
            {"id_metrica": "GMV_SHOPPING_BRASIL", "categoria": "SHOPPING", "subgrupo": "ECOMMERCE", "nome_metrica": "GMV Shopping Brasil", "unidade_medida": "R$ MIL", "row": 5, "source": "OP"},
            {"id_metrica": "TAKE_RATE_BRUTO", "categoria": "SHOPPING", "subgrupo": "MONETIZACAO", "nome_metrica": "Take Rate Méliuz", "unidade_medida": "%", "row": 7, "source": "OP"},
            {"id_metrica": "TAKE_RATE_LIQUIDO", "categoria": "SHOPPING", "subgrupo": "MONETIZACAO", "nome_metrica": "Net Take Rate Méliuz", "unidade_medida": "%", "row": 9, "source": "OP"},
            {"id_metrica": "CONTAS_TOTAIS", "categoria": "USUARIOS", "subgrupo": "BASE", "nome_metrica": "Contas Totais Méliuz", "unidade_medida": "MILHARES", "row": 11, "source": "OP"},
            {"id_metrica": "CONTAS_DIGITAIS_BV", "categoria": "SERVICOS_FINANCEIROS", "subgrupo": "PARCERIA_BV", "nome_metrica": "Contas Digitais Abertas BV", "unidade_medida": "UNIDADES", "row": 15, "source": "OP"},
            {"id_metrica": "CARTOES_EMITIDOS_BV", "categoria": "SERVICOS_FINANCEIROS", "subgrupo": "PARCERIA_BV", "nome_metrica": "Cartões Emitidos BV", "unidade_medida": "UNIDADES", "row": 16, "source": "OP"},
            {"id_metrica": "TPV_BANCO_BV", "categoria": "SERVICOS_FINANCEIROS", "subgrupo": "PARCERIA_BV", "nome_metrica": "TPV Parceria BV", "unidade_medida": "R$ MIL", "row": 17, "source": "OP"},
            {"id_metrica": "TPV_LEGADO", "categoria": "SERVICOS_FINANCEIROS", "subgrupo": "LEGADO", "nome_metrica": "TPV Operação Legada", "unidade_medida": "R$ MIL", "row": 20, "source": "OP"},
            {"id_metrica": "BTC_POSICAO_ACUMULADA", "categoria": "BITCOIN", "subgrupo": "TESOURARIA", "nome_metrica": "Posição Bitcoin em Tesouraria", "unidade_medida": "BTC", "row": 4, "source": "BTC"},
            {"id_metrica": "BTC_PRECO_MEDIO_USD", "categoria": "BITCOIN", "subgrupo": "TESOURARIA", "nome_metrica": "Preço Médio de Compra Bitcoin", "unidade_medida": "USD", "row": 6, "source": "BTC"},
            {"id_metrica": "BTC_SATS_POR_ACAO", "categoria": "BITCOIN", "subgrupo": "TESOURARIA", "nome_metrica": "Sats por Ação", "unidade_medida": "SATS", "row": 10, "source": "BTC"},
            {"id_metrica": "BTC_GAIN_BRL_MI", "categoria": "BITCOIN", "subgrupo": "TESOURARIA", "nome_metrica": "Bitcoin Gain", "unidade_medida": "R$ MILHOES", "row": 16, "source": "BTC"}
        ]

        fato_metricas = []
        for m in dim_metricas:
            target_df = df_op if m["source"] == "OP" else df_btc
            for q in quarters:
                col_match = None
                for c_col, c_val in target_df.iloc[2].items():
                    if pd.notna(c_val) and q["periodo_codigo"] in str(c_val):
                        col_match = c_col
                        break

                if col_match is not None:
                    val = target_df.iloc[m["row"]][col_match]
                    try:
                        num_val = float(val) if pd.notna(val) else None
                    except (ValueError, TypeError):
                        num_val = None

                    # Sanitização de zeros em períodos sem apuração
                    if m["id_metrica"] in ["TAKE_RATE_BRUTO", "TAKE_RATE_LIQUIDO"] and q["ano"] == 2019 and num_val == 0.0:
                        num_val = None

                    if num_val is not None:
                        fato_metricas.append({
                            "id_metrica": m["id_metrica"],
                            "data_fechamento": q["data_fechamento"],
                            "periodo_codigo": q["periodo_codigo"],
                            "valor_metrica": num_val
                        })

        df_dim_m = pd.DataFrame(dim_metricas).drop(columns=["row", "source"])
        return df_dim_m, pd.DataFrame(fato_metricas)

    def execute_upsert(self, df_dim_c, df_fato_c, df_dim_m, df_fato_m):
        """Executa carga em lote com declaração explícita de colunas no SQL."""
        if not self.engine:
            logging.info("Engine não conectada. Modo dry-run concluído.")
            return

        df_dim_c.to_sql("stg_dim_plano_contas", self.engine, if_exists="replace", index=False)
        df_fato_c.to_sql("stg_fato_movimento_contabil", self.engine, if_exists="replace", index=False)
        df_dim_m.to_sql("stg_dim_metrica_operacional", self.engine, if_exists="replace", index=False)
        df_fato_m.to_sql("stg_fato_indicadores_operacionais", self.engine, if_exists="replace", index=False)

        with self.engine.begin() as conn:
            if self.db_type == "postgresql":
                conn.execute(text("""
                    INSERT INTO dim_plano_contas (
                        id_conta, demonstrativo, secao_contabil, subgrupo, descricao_conta, 
                        tipo_conta, nivel_hierarquia, ordem_exibicao, natureza_sinal
                    )
                    SELECT 
                        id_conta, demonstrativo, secao_contabil, subgrupo, descricao_conta, 
                        tipo_conta, nivel_hierarquia, ordem_exibicao, natureza_sinal 
                    FROM stg_dim_plano_contas
                    ON CONFLICT (id_conta) DO UPDATE SET 
                        descricao_conta = EXCLUDED.descricao_conta,
                        tipo_conta = EXCLUDED.tipo_conta,
                        subgrupo = EXCLUDED.subgrupo,
                        ordem_exibicao = EXCLUDED.ordem_exibicao,
                        natureza_sinal = EXCLUDED.natureza_sinal;

                    INSERT INTO fato_movimento_contabil (
                        id_conta, data_fechamento, periodo_codigo, valor_discreto, valor_ytd
                    )
                    SELECT 
                        id_conta, CAST(data_fechamento AS DATE), periodo_codigo, valor_discreto, valor_ytd 
                    FROM stg_fato_movimento_contabil
                    ON CONFLICT (id_conta, data_fechamento) DO UPDATE SET 
                        valor_discreto = EXCLUDED.valor_discreto,
                        valor_ytd = EXCLUDED.valor_ytd,
                        data_carga = NOW();

                    INSERT INTO dim_metrica_operacional (id_metrica, categoria, subgrupo, nome_metrica, unidade_medida)
                    SELECT id_metrica, categoria, subgrupo, nome_metrica, unidade_medida FROM stg_dim_metrica_operacional
                    ON CONFLICT (id_metrica) DO NOTHING;

                    INSERT INTO fato_indicadores_operacionais (id_metrica, data_fechamento, periodo_codigo, valor_metrica)
                    SELECT id_metrica, CAST(data_fechamento AS DATE), periodo_codigo, valor_metrica 
                    FROM stg_fato_indicadores_operacionais
                    WHERE valor_metrica IS NOT NULL
                    ON CONFLICT (id_metrica, data_fechamento) DO UPDATE SET 
                        valor_metrica = EXCLUDED.valor_metrica,
                        data_carga = NOW();
                """))
            elif self.db_type == "sqlserver":
                conn.execute(text("""
                    MERGE INTO dim_plano_contas AS t 
                    USING stg_dim_plano_contas AS s ON t.id_conta = s.id_conta
                    WHEN MATCHED THEN 
                        UPDATE SET 
                            t.descricao_conta = s.descricao_conta, 
                            t.tipo_conta = s.tipo_conta, 
                            t.subgrupo = s.subgrupo,
                            t.ordem_exibicao = s.ordem_exibicao,
                            t.natureza_sinal = s.natureza_sinal
                    WHEN NOT MATCHED THEN 
                        INSERT (id_conta, demonstrativo, secao_contabil, subgrupo, descricao_conta, tipo_conta, nivel_hierarquia, ordem_exibicao, natureza_sinal)
                        VALUES (s.id_conta, s.demonstrativo, s.secao_contabil, s.subgrupo, s.descricao_conta, s.tipo_conta, s.nivel_hierarquia, s.ordem_exibicao, s.natureza_sinal);

                    MERGE INTO fato_movimento_contabil AS t 
                    USING stg_fato_movimento_contabil AS s 
                    ON t.id_conta = s.id_conta AND t.data_fechamento = s.data_fechamento
                    WHEN MATCHED THEN 
                        UPDATE SET 
                            t.valor_discreto = s.valor_discreto, 
                            t.valor_ytd = s.valor_ytd, 
                            t.data_carga = GETDATE()
                    WHEN NOT MATCHED THEN 
                        INSERT (id_conta, data_fechamento, periodo_codigo, valor_discreto, valor_ytd, data_carga)
                        VALUES (s.id_conta, s.data_fechamento, s.periodo_codigo, s.valor_discreto, s.valor_ytd, GETDATE());

                    MERGE INTO dim_metrica_operacional AS t 
                    USING stg_dim_metrica_operacional AS s ON t.id_metrica = s.id_metrica
                    WHEN NOT MATCHED THEN 
                        INSERT (id_metrica, categoria, subgrupo, nome_metrica, unidade_medida)
                        VALUES (s.id_metrica, s.categoria, s.subgrupo, s.nome_metrica, s.unidade_medida);

                    MERGE INTO fato_indicadores_operacionais AS t 
                    USING (SELECT * FROM stg_fato_indicadores_operacionais WHERE valor_metrica IS NOT NULL) AS s
                    ON t.id_metrica = s.id_metrica AND t.data_fechamento = s.data_fechamento
                    WHEN MATCHED THEN 
                        UPDATE SET 
                            t.valor_metrica = s.valor_metrica, 
                            t.data_carga = GETDATE()
                    WHEN NOT MATCHED THEN 
                        INSERT (id_metrica, data_fechamento, periodo_codigo, valor_metrica, data_carga)
                        VALUES (s.id_metrica, s.data_fechamento, s.periodo_codigo, s.valor_metrica, GETDATE());
                """))
        logging.info("Upsert atômico concluído com sucesso.")

if __name__ == "__main__":
    pipeline = MeliuzETLPipeline(data_folder="./")
    arquivo = pipeline.get_latest_file()
    dim_c, fato_c = pipeline.parse_financial_statements(arquivo)
    dim_m, fato_m = pipeline.parse_operational_indicators(arquivo)
    pipeline.execute_upsert(dim_c, fato_c, dim_m, fato_m)

```

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

## 7. Rastreabilidade e Auditoria Contábil

* **Natureza da Opinião:** Os demonstrativos trimestrais (ITRs) possuem **relatório de revisão especial/limitada** emitido pela PwC nos termos da NBC TR 2410 / ISRE 2410. A auditoria completa com opinião formal aplica-se exclusivamente às demonstrações financeiras anuais (DFPs).

* **Parâmetros de Auditoria (Metas para Homologação do 3T26):**

  * Receita Operacional Líquida (3T26): **R\$ 96.084 mil**.

  * Lucro Líquido Consolidado (3T26): **R\$ 113.698 mil**.

  * Caixa Líquido das Atividades Operacionais (YTD 9M26): **R\$ 35.047 mil** (conciliado exatamente pela soma das contas analíticas com o ponto de partida do lucro contábil).

  * Caixa Líquido das Atividades de Financiamento (YTD 9M26): **-R\$ 41.417 mil** (excluindo os **-R\$ 631 mil** isolados no subgrupo `EFEITO_CAMBIAL`).

  * Recebimento pela Venda de Bitcoin (DFC Investimento YTD 9M26): **R\$ 29.350 mil**.

  * Posição em Bitcoin em Tesouraria (3T26): **526,69 BTC**.