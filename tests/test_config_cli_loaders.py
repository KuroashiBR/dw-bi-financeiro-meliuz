"""Configuração, CLI, seleção de arquivo e comportamento transacional da staging dos loaders.

Nada aqui exige um banco instalado: o comportamento de SQL específico (MERGE/UPSERT) continua sem
teste automatizado contra SGBD real.
"""

import inspect
import os
import time
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import event

import config
import loaders
import main
from config import build_connection
from extractors import get_latest_file


# ----------------------------------------------------------------------------- get_latest_file


class TestGetLatestFile:
    def _cria(self, pasta: Path, nome: str, mtime: float) -> Path:
        f = pasta / nome
        f.write_bytes(b"x")
        os.utime(f, (mtime, mtime))
        return f

    def test_escolhe_pelo_trimestre_do_nome_e_nao_pela_data_de_modificacao(self, tmp_path):
        agora = time.time()
        self._cria(tmp_path, "Dados historicos Meliuz_2T26.xlsx", agora)          # mais "novo" no disco
        esperado = self._cria(tmp_path, "Dados historicos Meliuz_3T26.xlsx", agora - 9999)
        self._cria(tmp_path, "Dados historicos Meliuz_4T25.xlsx", agora + 9999)    # ano anterior, mtime maior
        assert get_latest_file(str(tmp_path)) == str(esperado)

    def test_ignora_arquivos_temporarios_do_office(self, tmp_path):
        valido = self._cria(tmp_path, "Dados historicos Meliuz_1T26.xlsx", 1)
        self._cria(tmp_path, "~$Dados historicos Meliuz_3T26.xlsx", 2)
        assert get_latest_file(str(tmp_path)) == str(valido)

    def test_sem_trimestre_no_nome_usa_data_de_modificacao(self, tmp_path):
        self._cria(tmp_path, "Meliuz_antigo.xlsx", 1)
        esperado = self._cria(tmp_path, "Meliuz_novo.xlsx", 100)
        assert get_latest_file(str(tmp_path)) == str(esperado)

    def test_pasta_sem_arquivo_valido_falha(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            get_latest_file(str(tmp_path))

    def test_data_folder_nao_depende_do_diretorio_atual(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        assert Path(config.DATA_FOLDER).is_absolute()
        assert Path(get_latest_file(config.DATA_FOLDER)).exists()


# ----------------------------------------------------------------------------- conexão / credenciais


class TestConexao:
    def test_sqlserver_usa_autenticacao_integrada_sem_usuario(self):
        url = build_connection("sqlserver", "dw", "srv", env={})
        assert "Trusted_Connection%3Dyes" in url and "PWD" not in url

    def test_sqlserver_com_usuario_e_senha_e_porta(self):
        url = build_connection("sqlserver", "dw", "srv", env={"DW_DB_USER": "u", "DW_DB_PASSWORD": "p@ss", "DW_DB_PORT": "1444"})
        assert "UID%3Du" in url and "SERVER%3Dsrv%2C1444" in url and "Trusted_Connection" not in url

    def test_sqlserver_usuario_sem_senha_falha(self):
        with pytest.raises(ValueError, match="DW_DB_PASSWORD"):
            build_connection("sqlserver", "dw", "srv", env={"DW_DB_USER": "u"})

    def test_postgres_exige_senha_e_nao_tem_senha_padrao(self):
        with pytest.raises(ValueError, match="DW_DB_PASSWORD"):
            build_connection("postgresql", "dw", "srv", env={})

    def test_postgres_aceita_senha_com_caracteres_especiais(self):
        url = build_connection("postgresql", "dw", "srv", env={"DW_DB_PASSWORD": "a@b/c:d#"})
        assert url.username == "postgres" and url.password == "a@b/c:d#"
        assert (url.host, url.port, url.database) == ("srv", 5432, "dw")

    def test_sgbd_nao_suportado(self):
        with pytest.raises(ValueError, match="não suportado"):
            build_connection("oracle", "dw", "srv", env={})

    def test_nenhuma_credencial_fixa_no_codigo(self):
        fonte = inspect.getsource(config)
        assert "postgres:postgres" not in fonte


# ----------------------------------------------------------------------------- CLI


class TestCLI:
    def test_padroes_vem_da_configuracao(self):
        a = main.parse_args([])
        assert (a.db, a.server, a.database, a.file) == (config.DEFAULT_DB_TYPE, config.DEFAULT_SERVER, config.DEFAULT_DB_NAME, None)

    def test_argumentos_explicitos(self):
        a = main.parse_args(["--db", "postgresql", "--server", "h", "--database", "d", "--file", "x.xlsx"])
        assert (a.db, a.server, a.database, a.file) == ("postgresql", "h", "d", "x.xlsx")

    def test_sgbd_invalido_e_rejeitado(self):
        with pytest.raises(SystemExit):
            main.parse_args(["--db", "mysql"])


# ----------------------------------------------------------------------------- loaders


def _engine_sqlite_transacional(caminho):
    """SQLite em arquivo (conexões independentes) com DDL transacional (receita do SQLAlchemy)."""
    engine = create_engine(f"sqlite:///{caminho}")

    @event.listens_for(engine, "connect")
    def _connect(dbapi_conn, _):
        dbapi_conn.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin(conn):
        conn.exec_driver_sql("BEGIN")

    return engine


class TestLoaders:
    def test_staging_some_se_a_carga_falhar(self, tmp_path):
        engine = _engine_sqlite_transacional(tmp_path / "t.db")
        df = pd.DataFrame({"a": [1, 2]})
        with pytest.raises(RuntimeError):
            with engine.begin() as conn:
                loaders._carrega_staging(conn, "stg_x", df)
                raise RuntimeError("falha simulada no MERGE/UPSERT")
        assert not sa_inspect(engine).has_table("stg_x")

    def test_staging_persiste_ate_o_commit_quando_tudo_da_certo(self, tmp_path):
        engine = _engine_sqlite_transacional(tmp_path / "t.db")
        with engine.begin() as conn:
            loaders._carrega_staging(conn, "stg_y", pd.DataFrame({"a": [1]}))
        assert sa_inspect(engine).has_table("stg_y")

    def test_o_teste_de_rollback_detecta_o_comportamento_antigo(self, tmp_path):
        """Controle: gravar a staging pela ENGINE (como era antes) deixa tabela órfã após a falha."""
        engine = _engine_sqlite_transacional(tmp_path / "t.db")
        with pytest.raises(RuntimeError):
            with engine.begin() as conn:
                pd.DataFrame({"a": [1]}).to_sql("stg_antigo", engine, if_exists="replace", index=False)
                raise RuntimeError("falha simulada")
        assert sa_inspect(engine).has_table("stg_antigo")

    @pytest.mark.parametrize(
        "funcao",
        [
            loaders.load_dim_plano_contas,
            loaders.load_fato_movimento_contabil,
            loaders.load_dim_metrica_operacional,
            loaders.load_fato_indicadores_operacionais,
        ],
    )
    def test_nenhum_loader_grava_staging_fora_da_transacao(self, funcao):
        fonte = inspect.getsource(funcao)
        assert "to_sql(" not in fonte
        assert fonte.index("engine.begin()") < fonte.index("_carrega_staging(")

    @pytest.mark.parametrize("coluna", [
        "demonstrativo", "secao_contabil", "subgrupo", "descricao_conta",
        "tipo_conta", "nivel_hierarquia", "ordem_exibicao", "natureza_sinal",
    ])
    def test_upsert_da_dim_plano_contas_atualiza_todas_as_colunas_nao_chave(self, coluna):
        fonte = inspect.getsource(loaders.load_dim_plano_contas)
        assert f"t.{coluna} = s.{coluna}" in fonte, f"MERGE (SQL Server) não atualiza {coluna}"
        assert f"{coluna} = EXCLUDED.{coluna}" in fonte, f"UPSERT (PostgreSQL) não atualiza {coluna}"


# ----------------------------------------------------------------------------- DDL


class TestDDL:
    def test_indices_do_sqlserver_sao_idempotentes(self):
        sql = (Path(__file__).resolve().parent.parent / "database/sqlserver/01_ddl_schema.sql").read_text(encoding="utf-8")
        for linha in [l for l in sql.splitlines() if "CREATE NONCLUSTERED INDEX" in l]:
            anterior = sql.splitlines()[sql.splitlines().index(linha) - 1]
            assert "IF NOT EXISTS" in anterior and "sys.indexes" in anterior, linha
