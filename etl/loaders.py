"""Loaders idempotentes isolados por tabela com projeção explícita de colunas."""

import logging
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine


def load_dim_plano_contas(engine: Engine, db_type: str, df: pd.DataFrame) -> None:
    """Executa MERGE/UPSERT da dimensão dim_plano_contas e limpa staging."""
    stg_table = "stg_dim_plano_contas"
    df.to_sql(stg_table, engine, if_exists="replace", index=False)

    with engine.begin() as conn:
        if db_type == "sqlserver":
            conn.execute(text("""
                MERGE INTO dim_plano_contas AS t
                USING (
                    SELECT id_conta, demonstrativo, secao_contabil, subgrupo, descricao_conta,
                           tipo_conta, nivel_hierarquia, ordem_exibicao, natureza_sinal
                    FROM stg_dim_plano_contas
                ) AS s ON t.id_conta = s.id_conta
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

                DROP TABLE IF EXISTS stg_dim_plano_contas;
            """))
        elif db_type == "postgresql":
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

                DROP TABLE IF EXISTS stg_dim_plano_contas;
            """))
    logging.info(f"[dim_plano_contas] Carga concluída ({len(df)} registros processados).")


def load_fato_movimento_contabil(engine: Engine, db_type: str, df: pd.DataFrame) -> None:
    """Executa MERGE/UPSERT da fato fato_movimento_contabil e limpa staging."""
    stg_table = "stg_fato_movimento_contabil"
    df.to_sql(stg_table, engine, if_exists="replace", index=False)

    with engine.begin() as conn:
        if db_type == "sqlserver":
            conn.execute(text("""
                MERGE INTO fato_movimento_contabil AS t
                USING (
                    SELECT id_conta, data_fechamento, periodo_codigo, valor_discreto, valor_ytd
                    FROM stg_fato_movimento_contabil
                ) AS s ON t.id_conta = s.id_conta AND t.data_fechamento = s.data_fechamento
                WHEN MATCHED THEN
                    UPDATE SET
                        t.valor_discreto = s.valor_discreto,
                        t.valor_ytd = s.valor_ytd,
                        t.data_carga = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (id_conta, data_fechamento, periodo_codigo, valor_discreto, valor_ytd, data_carga)
                    VALUES (s.id_conta, s.data_fechamento, s.periodo_codigo, s.valor_discreto, s.valor_ytd, GETDATE());

                DROP TABLE IF EXISTS stg_fato_movimento_contabil;
            """))
        elif db_type == "postgresql":
            conn.execute(text("""
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

                DROP TABLE IF EXISTS stg_fato_movimento_contabil;
            """))
    logging.info(f"[fato_movimento_contabil] Carga concluída ({len(df)} registros processados).")


def load_dim_metrica_operacional(engine: Engine, db_type: str, df: pd.DataFrame) -> None:
    """Executa MERGE/UPSERT da dimensão dim_metrica_operacional e limpa staging."""
    stg_table = "stg_dim_metrica_operacional"
    df.to_sql(stg_table, engine, if_exists="replace", index=False)

    with engine.begin() as conn:
        if db_type == "sqlserver":
            conn.execute(text("""
                MERGE INTO dim_metrica_operacional AS t
                USING (
                    SELECT id_metrica, categoria, subgrupo, nome_metrica, unidade_medida
                    FROM stg_dim_metrica_operacional
                ) AS s ON t.id_metrica = s.id_metrica
                WHEN MATCHED THEN
                    UPDATE SET
                        t.categoria = s.categoria,
                        t.subgrupo = s.subgrupo,
                        t.nome_metrica = s.nome_metrica,
                        t.unidade_medida = s.unidade_medida
                WHEN NOT MATCHED THEN
                    INSERT (id_metrica, categoria, subgrupo, nome_metrica, unidade_medida)
                    VALUES (s.id_metrica, s.categoria, s.subgrupo, s.nome_metrica, s.unidade_medida);

                DROP TABLE IF EXISTS stg_dim_metrica_operacional;
            """))
        elif db_type == "postgresql":
            conn.execute(text("""
                INSERT INTO dim_metrica_operacional (
                    id_metrica, categoria, subgrupo, nome_metrica, unidade_medida
                )
                SELECT id_metrica, categoria, subgrupo, nome_metrica, unidade_medida
                FROM stg_dim_metrica_operacional
                ON CONFLICT (id_metrica) DO UPDATE SET
                    categoria = EXCLUDED.categoria,
                    subgrupo = EXCLUDED.subgrupo,
                    nome_metrica = EXCLUDED.nome_metrica,
                    unidade_medida = EXCLUDED.unidade_medida;

                DROP TABLE IF EXISTS stg_dim_metrica_operacional;
            """))
    logging.info(f"[dim_metrica_operacional] Carga concluída ({len(df)} registros processados).")


def load_fato_indicadores_operacionais(engine: Engine, db_type: str, df: pd.DataFrame) -> None:
    """Executa MERGE/UPSERT da fato fato_indicadores_operacionais sem SELECT * e limpa staging."""
    stg_table = "stg_fato_indicadores_operacionais"
    df.to_sql(stg_table, engine, if_exists="replace", index=False)

    with engine.begin() as conn:
        if db_type == "sqlserver":
            conn.execute(text("""
                MERGE INTO fato_indicadores_operacionais AS t
                USING (
                    SELECT id_metrica, data_fechamento, periodo_codigo, valor_metrica
                    FROM stg_fato_indicadores_operacionais
                    WHERE valor_metrica IS NOT NULL
                ) AS s ON t.id_metrica = s.id_metrica AND t.data_fechamento = s.data_fechamento
                WHEN MATCHED THEN
                    UPDATE SET
                        t.valor_metrica = s.valor_metrica,
                        t.data_carga = GETDATE()
                WHEN NOT MATCHED THEN
                    INSERT (id_metrica, data_fechamento, periodo_codigo, valor_metrica, data_carga)
                    VALUES (s.id_metrica, s.data_fechamento, s.periodo_codigo, s.valor_metrica, GETDATE());

                DROP TABLE IF EXISTS stg_fato_indicadores_operacionais;
            """))
        elif db_type == "postgresql":
            conn.execute(text("""
                INSERT INTO fato_indicadores_operacionais (
                    id_metrica, data_fechamento, periodo_codigo, valor_metrica
                )
                SELECT
                    id_metrica, CAST(data_fechamento AS DATE), periodo_codigo, valor_metrica
                FROM stg_fato_indicadores_operacionais
                WHERE valor_metrica IS NOT NULL
                ON CONFLICT (id_metrica, data_fechamento) DO UPDATE SET
                    valor_metrica = EXCLUDED.valor_metrica,
                    data_carga = NOW();

                DROP TABLE IF EXISTS stg_fato_indicadores_operacionais;
            """))
    logging.info(f"[fato_indicadores_operacionais] Carga concluída ({len(df)} registros processados).")
