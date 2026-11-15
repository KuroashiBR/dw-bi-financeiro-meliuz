"""Utilitários compartilhados pelos testes de reconciliação."""

import pandas as pd

# A planilha de RI é publicada em R$ mil já arredondada; subtotais e componentes
# podem divergir em até ~1 por arredondamento da própria fonte.
TOL = 1.5


def exige_zero(diff: pd.Series, nome: str, tol: float = TOL, min_n: int = 1, ignorar=()) -> None:
    """Falha listando os períodos em que |diff| > tol. Ignora NaN e períodos em `ignorar`."""
    d = diff.drop(labels=[p for p in ignorar if p in diff.index]).dropna()
    assert len(d) >= min_n, f"{nome}: apenas {len(d)} períodos comparáveis (mínimo esperado: {min_n})"
    ruins = d[d.abs() > tol]
    assert ruins.empty, f"{nome}: {len(ruins)} período(s) fora da tolerância de {tol}: {ruins.round(2).to_dict()}"


def ano_do_periodo(periodo: str) -> int:
    """'3T26' -> 2026."""
    return 2000 + int(periodo[2:])
