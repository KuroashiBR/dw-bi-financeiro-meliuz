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
├── data/          # Historical IR spreadsheets (1Q19 - 3Q26)
├── database/      # Star Schema DDLs (SQL Server & PostgreSQL)
├── docs/          # Full technical and accounting specification
├── etl/           # Python ingestion, temporal disaggregation & upsert pipeline
├── powerbi/       # Power Query (M) calendar & Power BI semantic model
└── README.md      # Project overview
