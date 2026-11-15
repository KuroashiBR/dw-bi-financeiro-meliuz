"""Orquestrador principal do pipeline ETL - Méliuz (CASH3).

Uso (a partir de qualquer diretório):
    python etl/main.py                                  # padrões vindos de config/.env
    python etl/main.py --db postgresql --server localhost --database dwmeliuz
    python etl/main.py --file "data/Dados historicos Meliuz_3T26.xlsx"
"""

import argparse
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


def run_pipeline(
    db_type: str = DEFAULT_DB_TYPE,
    db_name: str = DEFAULT_DB_NAME,
    server: str = DEFAULT_SERVER,
    arquivo: str | None = None,
) -> None:
    arquivo = arquivo or get_latest_file(DATA_FOLDER)
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


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Carrega a planilha de RI da Méliuz no Data Warehouse.")
    p.add_argument("--db", choices=["sqlserver", "postgresql"], default=DEFAULT_DB_TYPE, help="SGBD de destino")
    p.add_argument("--server", default=DEFAULT_SERVER, help="host do servidor")
    p.add_argument("--database", default=DEFAULT_DB_NAME, help="nome do banco")
    p.add_argument("--file", default=None, help="planilha .xlsx (padrão: a mais recente em data/)")
    return p.parse_args(argv)


if __name__ == "__main__":
    args = parse_args()
    run_pipeline(db_type=args.db, db_name=args.database, server=args.server, arquivo=args.file)
