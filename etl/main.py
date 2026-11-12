"""Orquestrador principal do pipeline ETL - Méliuz (CASH3)."""

import logging
from config import DATA_FOLDER, DEFAULT_DB_TYPE, DEFAULT_DB_NAME, DEFAULT_SERVER, get_db_engine
from extractors import get_latest_file, extract_financial_statements, extract_operational_indicators
from loaders import (
    load_dim_plano_contas,
    load_fato_movimento_contabil,
    load_dim_metrica_operacional,
    load_fato_indicadores_operacionais,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


def run_pipeline(db_type: str = DEFAULT_DB_TYPE, db_name: str = DEFAULT_DB_NAME, server: str = DEFAULT_SERVER) -> None:
    arquivo = get_latest_file(DATA_FOLDER)
    logging.info(f"Iniciando ingestão do arquivo: {arquivo}")

    engine = get_db_engine(db_type=db_type, db_name=db_name, server=server)

    # Domínio 1: Demonstrações Financeiras Consolidadas
    df_dim_contas, df_fato_contabil = extract_financial_statements(arquivo)
    load_dim_plano_contas(engine, db_type, df_dim_contas)
    load_fato_movimento_contabil(engine, db_type, df_fato_contabil)

    # Domínio 2: Indicadores Operacionais e Tesouraria Bitcoin
    df_dim_metricas, df_fato_metricas = extract_operational_indicators(arquivo)
    load_dim_metrica_operacional(engine, db_type, df_dim_metricas)
    load_fato_indicadores_operacionais(engine, db_type, df_fato_metricas)

    logging.info("Pipeline ETL finalizado com sucesso.")


if __name__ == "__main__":
    run_pipeline()
