"""Configurações de conexão e caminhos do pipeline ETL - Méliuz (CASH3).

Credenciais e destino vêm de variáveis de ambiente (ou de um arquivo `.env` na raiz do repositório,
ver `.env.example`). Nada sensível fica versionado.
"""

import os
import urllib.parse
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parent.parent

try:  # python-dotenv é opcional: sem ele, valem apenas as variáveis já definidas no ambiente
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# Independe do diretório de onde o comando é executado.
DATA_FOLDER = str(ROOT / "data")

DEFAULT_DB_TYPE = os.environ.get("DW_DB_TYPE", "sqlserver")
DEFAULT_DB_NAME = os.environ.get("DW_DB_NAME", "dwmeliuz")
DEFAULT_SERVER = os.environ.get("DW_DB_SERVER", "localhost")


def build_connection(db_type: str, db_name: str, server: str, env=None):
    """Monta a URL de conexão SQLAlchemy conforme o SGBD alvo.

    Variáveis lidas: DW_DB_USER, DW_DB_PASSWORD, DW_DB_PORT, DW_ODBC_DRIVER.
    - SQL Server: sem DW_DB_USER usa autenticação integrada do Windows (Trusted_Connection).
    - PostgreSQL: DW_DB_USER (padrão `postgres`) e DW_DB_PASSWORD (obrigatória).
    """
    env = os.environ if env is None else env
    db_type = db_type.lower()
    user = env.get("DW_DB_USER")
    password = env.get("DW_DB_PASSWORD")
    port = env.get("DW_DB_PORT")

    if db_type == "sqlserver":
        driver = env.get("DW_ODBC_DRIVER", "ODBC Driver 17 for SQL Server")
        host = f"{server},{port}" if port else server
        parts = [f"DRIVER={{{driver}}}", f"SERVER={host}", f"DATABASE={db_name}", "TrustServerCertificate=yes"]
        if user:
            if password is None:
                raise ValueError("DW_DB_USER definido sem DW_DB_PASSWORD para SQL Server.")
            parts += [f"UID={user}", f"PWD={password}"]
        else:
            parts.append("Trusted_Connection=yes")
        odbc = urllib.parse.quote_plus(";".join(parts) + ";")
        return f"mssql+pyodbc:///?odbc_connect={odbc}"

    if db_type == "postgresql":
        if not password:
            raise ValueError("Defina DW_DB_PASSWORD (variável de ambiente ou .env) para conectar ao PostgreSQL.")
        return URL.create(
            "postgresql+psycopg2",
            username=user or "postgres",
            password=password,
            host=server,
            port=int(port) if port else 5432,
            database=db_name,
        )

    raise ValueError(f"SGBD não suportado: {db_type}")


def get_db_engine(db_type: str = DEFAULT_DB_TYPE, db_name: str = DEFAULT_DB_NAME, server: str = DEFAULT_SERVER):
    """Instancia a engine SQLAlchemy conforme o SGBD alvo."""
    return create_engine(build_connection(db_type, db_name, server))
