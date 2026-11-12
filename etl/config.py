"""Configurações de conexão e caminhos do pipeline ETL - Méliuz (CASH3)."""

import urllib.parse
from sqlalchemy import create_engine

DATA_FOLDER = "./data"
DEFAULT_DB_TYPE = "sqlserver"
DEFAULT_DB_NAME = "dwmeliuz"
DEFAULT_SERVER = "localhost"


def get_db_engine(db_type: str = DEFAULT_DB_TYPE, db_name: str = DEFAULT_DB_NAME, server: str = DEFAULT_SERVER):
    """Instancia a engine SQLAlchemy conforme o SGBD alvo."""
    db_type = db_type.lower()

    if db_type == "sqlserver":
        params = urllib.parse.quote_plus(
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={server};"
            f"DATABASE={db_name};"
            f"Trusted_Connection=yes;"
            f"TrustServerCertificate=yes;"
        )
        conn_string = f"mssql+pyodbc:///?odbc_connect={params}"
        return create_engine(conn_string)

    if db_type == "postgresql":
        # Ajuste usuário/senha caso utilize PostgreSQL local
        conn_string = f"postgresql+psycopg2://postgres:postgres@{server}:5432/{db_name}"
        return create_engine(conn_string)

    raise ValueError(f"SGBD não suportado: {db_type}")
