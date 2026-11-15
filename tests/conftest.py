"""Fixtures: roda o ETL de extração uma única vez sobre a planilha real e expõe os resultados."""

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "etl"))

from extractors import (  # noqa: E402
    extract_financial_statements,
    extract_operational_indicators,
    get_latest_file,
)

ABA_FINANCEIRA = "Finan. Cons. | Finan. Cons."


class Contas:
    """Acesso às séries contábeis por (demonstrativo, descrição[, subgrupo])."""

    def __init__(self, dim: pd.DataFrame, fato: pd.DataFrame):
        self.dim = dim
        self.fato = fato
        self.m = fato.merge(dim, on="id_conta").sort_values("data_fechamento")

    def serie(
        self,
        demonstrativo: str,
        descricao: str,
        col: str = "valor_ytd",
        sub: str | None = None,
        ocorrencia: int | None = None,
    ) -> pd.Series:
        """Série de uma conta. `ocorrencia` (0, 1, ...) escolhe entre rótulos repetidos no mesmo
        subgrupo, na ordem em que aparecem na planilha (ordem_exibicao)."""
        x = self.m[(self.m.demonstrativo == demonstrativo) & (self.m.descricao_conta == descricao)]
        if sub:
            x = x[x.subgrupo == sub]
        if ocorrencia is not None:
            ordem = x.drop_duplicates("id_conta").sort_values("ordem_exibicao").id_conta.tolist()
            assert ocorrencia < len(ordem), f"'{descricao}' tem só {len(ordem)} ocorrência(s)"
            x = x[x.id_conta == ordem[ocorrencia]]
        ids = x.id_conta.nunique()
        assert ids == 1, (
            f"'{descricao}' ({demonstrativo}, sub={sub}) resolveu para {ids} contas; "
            f"informe `sub` ou `ocorrencia`. Subgrupos: {sorted(x.subgrupo.unique())}"
        )
        return x.set_index("periodo_codigo")[col].astype(float)

    def soma_analiticas(self, demonstrativo: str, subgrupo: str, col: str = "valor_ytd") -> pd.Series:
        x = self.m[
            (self.m.demonstrativo == demonstrativo)
            & (self.m.subgrupo == subgrupo)
            & (self.m.tipo_conta == "Analítica")
        ]
        return x.groupby("periodo_codigo")[col].sum(min_count=1)


@pytest.fixture(scope="session")
def arquivo() -> str:
    env = os.environ.get("DW_XLSX")
    return env if env else get_latest_file(str(ROOT / "data"))


@pytest.fixture(scope="session")
def contabil(arquivo):
    dim, fato = extract_financial_statements(arquivo)
    return dim, fato


@pytest.fixture(scope="session")
def contas(contabil) -> Contas:
    return Contas(*contabil)


@pytest.fixture(scope="session")
def operacional(arquivo):
    return extract_operational_indicators(arquivo)


@pytest.fixture(scope="session")
def planilha_bruta(arquivo) -> pd.DataFrame:
    """Aba financeira lida sem transformação, para comparar com as colunas anuais da própria fonte."""
    return pd.read_excel(arquivo, sheet_name=ABA_FINANCEIRA)


def valor_anual(df: pd.DataFrame, rotulo: str, ano: int) -> float:
    """Valor da coluna anual `ano` na primeira linha cujo rótulo (coluna C) é `rotulo`."""
    cols = [c for c, v in df.iloc[2].items() if isinstance(v, (int, float)) and not pd.isna(v) and int(v) == ano]
    assert len(cols) == 1, f"coluna anual {ano} não localizada (achadas: {cols})"
    rotulos = df["Unnamed: 2"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    linhas = df.index[rotulos == rotulo]
    assert len(linhas) >= 1, f"rótulo '{rotulo}' não encontrado na planilha"
    return float(df.loc[linhas[0], cols[0]])
