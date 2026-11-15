# Data Warehouse & Financial Business Intelligence — Méliuz S.A. (B3: CASH3)

[🇺🇸 English](#english) | [🇧🇷 Português](#portugues)

---

<a name="english"></a>
## 🇺🇸 Overview

End-to-end **Analytics Engineering** and **Financial Business Intelligence** pipeline modeling the consolidated financial statements (Income Statement, Balance Sheet, Indirect Cash Flow), operational e-commerce/fintech metrics, and Bitcoin Treasury strategy of **Méliuz S.A. (B3: CASH3)** from **1Q19 to 3Q26**.

### 📚 Full Technical & Accounting Architecture
For an in-depth breakdown of the dimensional Star Schema modeling, accounting rules (CPC 04 / IAS 38), Cash Flow Statement temporal disaggregation (YTD-to-discrete deltas vs. cash stock balances), and sector impairment segregation, read the complete specification:
👉 **[Full Project Architecture & Accounting Modeling (PT-BR)](docs/DOCUMENTACAO_ARQUITETURA_BI_FINANCEIRO_MELIUZ_CASH3.md)**

### 🛠️ Tech Stack
* **Extraction & ETL:** Python (`pandas`, `openpyxl`, `SQLAlchemy`, `pyodbc`) with deterministic MD5 surrogate keys and atomic `MERGE` / `UPSERT` idempotency.
* **Data Warehouse:** Database-agnostic Star Schema DDL designed for **Microsoft SQL Server** and **PostgreSQL**.
* **Semantic Layer & BI:** Power BI, Power Query (`M`), and DAX measures (semi-additive Balance Sheet evaluations, YTD anchors, and pure leaf-account aggregations).

---

<a name="portugues"></a>
## 🇧🇷 Visão Geral

Pipeline completo de **Analytics Engineering** e **Business Intelligence Financeiro** modelando as demonstrações contábeis consolidadas (DRE, Balanço Patrimonial e DFC pelo Método Indireto), métricas operacionais de shopping/fintech e a estratégia de Tesouraria em Bitcoin da **Méliuz S.A. (B3: CASH3)** de **1T19 a 3T26**.

### 📚 Documentação Técnica e Arquitetura Contábil Completa
Para uma visão aprofundada da modelagem dimensional (*Star Schema*), fundamentos contábeis (CPC 04 / IAS 38), regras matemáticas de desagregação temporal da DFC (deltas trimestrais vs. saldos de estoque) e segregação setorial de *impairment*, acesse a documentação detalhada na pasta `docs/`:
👉 **[Especificação Completa de Arquitetura e Modelagem Contábil](docs/DOCUMENTACAO_ARQUITETURA_BI_FINANCEIRO_MELIUZ_CASH3.md)**

### 🛠️ Stack Tecnológica
* **Extração e ETL:** Python (`pandas`, `openpyxl`, `SQLAlchemy`, `pyodbc`) com chaves determinísticas MD5 e carga idempotente via `MERGE` / `UPSERT`.
* **Data Warehouse:** Modelagem dimensional *Star Schema* agnóstica de banco com scripts DDL para **Microsoft SQL Server** e **PostgreSQL**.
* **Camada Semântica e BI:** Power BI, Power Query (`M`) e DAX (avaliação semiaditiva de Balanço, ancoragem YTD e agregações estritas de contas analíticas).

---

## 📂 Repository Structure / Estrutura do Repositório

```text
dw-bi-financeiro-meliuz/
├── data/             # Historical IR spreadsheets (1Q19 - 3Q26)
├── database/         # Star Schema DDLs and analytical views (SQL Server & PostgreSQL)
├── docs/             # Full technical and accounting specification
├── etl/              # Python extraction, temporal disaggregation & upsert pipeline (config, extractors, loaders, main)
├── powerbi/          # Power Query (M) calendar (the .pbix report is not versioned here)
├── tests/            # pytest suite: accounting reconciliations, integrity, config/CLI
├── .github/workflows # CI: runs pytest on push and pull requests
├── .env.example      # Environment variables template (copy to .env)
├── pytest.ini
├── requirements-dev.txt
└── README.md         # Project overview
```

---

## 🚀 How to Run / Como Rodar

**Requirements / Requisitos:** Python 3.10+ and a SQL Server or PostgreSQL database. SQL Server also needs the *ODBC Driver 17 for SQL Server*.

**1. Install / Instalar**
```bash
pip install -r etl/requirements.txt
```

**2. Create the schema / Criar o esquema** — run, in this order, the scripts of your database (`database/sqlserver/` or `database/postgresql/`): `01_ddl_schema.sql`, then `02_views_analiticas.sql`.

> ⚠️ `CREATE TABLE IF NOT EXISTS` does not alter existing tables. If you loaded data with an older version of the DDL, recreate the tables (or `ALTER COLUMN`) to get the current numeric precision (`valor_discreto`/`valor_ytd` as 5 decimals, `valor_metrica` as 10).
> ⚠️ `CREATE TABLE IF NOT EXISTS` não altera tabelas existentes. Se você já carregou dados com uma versão antiga do DDL, recrie as tabelas (ou use `ALTER COLUMN`) para obter a precisão numérica atual.

**3. Configure the connection / Configurar a conexão** — copy `.env.example` to `.env` (ignored by git) and edit it, or set the same variables in your shell:

| Variable | Meaning |
|---|---|
| `DW_DB_TYPE` | `sqlserver` (default) or `postgresql` |
| `DW_DB_SERVER`, `DW_DB_NAME`, `DW_DB_PORT` | Host, database and (optional) port |
| `DW_DB_USER`, `DW_DB_PASSWORD` | SQL Server: leave `DW_DB_USER` empty to use Windows integrated authentication. PostgreSQL: `DW_DB_PASSWORD` is required |
| `DW_ODBC_DRIVER` | Defaults to `ODBC Driver 17 for SQL Server` |

**4. Load / Carregar**
```bash
python etl/main.py                                   # uses .env / defaults and the latest spreadsheet in data/
python etl/main.py --db postgresql --server localhost --database dwmeliuz
python etl/main.py --file "data/Dados historicos Meliuz_3T26.xlsx"
```
The latest spreadsheet is chosen by the quarter in the file name (e.g. `_3T26`). / A planilha mais recente é escolhida pelo trimestre no nome do arquivo.

**5. Test / Testar**
```bash
pip install -r requirements-dev.txt
pytest
```
The suite runs the extractor against the spreadsheet in `data/` (no database required) and checks accounting identities (assets = liabilities + equity, income statement chain, cash flow sums, DFC vs. balance sheet cash) and structural integrity. To test a new spreadsheet before copying it to `data/`: `DW_XLSX=<path> pytest`. / A suíte roda o extrator sobre a planilha em `data/` (sem banco) e confere identidades contábeis e a integridade estrutural.

> The SQL (`MERGE` / `UPSERT`, views, DDL) is not covered by automated tests: validate it against your database after the first load. / O SQL (`MERGE`/`UPSERT`, views, DDL) não é coberto por testes automatizados: valide no seu banco após a primeira carga.
