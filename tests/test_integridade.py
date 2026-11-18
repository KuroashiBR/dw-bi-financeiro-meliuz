"""Integridade estrutural da saída do extrator (dimensões e fatos contábeis).

Testes marcados com xfail(strict) documentam problemas conhecidos ainda não corrigidos:
quando forem corrigidos o teste vira XPASS (falha) e o marcador deve ser removido.
"""

import re
from pathlib import Path

import pandas as pd
import pytest

from helpers import ano_do_periodo

DDL_DIR = Path(__file__).resolve().parent.parent / "database"


def _escala_no_ddl(coluna: str) -> set[int]:
    """Escala (casas decimais) declarada para `coluna` em cada DDL (Postgres e SQL Server)."""
    escalas = set()
    for sql in DDL_DIR.glob("*/01_ddl_schema.sql"):
        m = re.search(rf"{coluna}\s+(?:NUMERIC|DECIMAL)\(\d+,\s*(\d+)\)", sql.read_text(encoding="utf-8"))
        assert m, f"{coluna} não encontrada em {sql}"
        escalas.add(int(m.group(1)))
    return escalas


def _casas(v: pd.Series, escala: int) -> pd.Series:
    """Valores que perderiam informação ao serem arredondados para `escala` casas."""
    v = v.dropna()
    return v[(v - v.round(escala)).abs() > 1e-9]


FIM_DO_TRIMESTRE = {"1": "03-31", "2": "06-30", "3": "09-30", "4": "12-31"}


class TestEstrutura:
    def test_trimestres_contiguos_desde_1t19(self, contabil, planilha_bruta):
        _, fato = contabil
        publicados = [str(v).split("|")[0].strip() for v in planilha_bruta.iloc[2]]
        publicados = [p for p in publicados if re.fullmatch(r"[1-4]T\d{2}", p)]
        assert len(publicados) >= 31
        esperados = [f"{i % 4 + 1}T{(19 + i // 4):02d}" for i in range(len(publicados))]
        assert publicados == esperados
        assert set(fato.periodo_codigo) == set(esperados)

    def test_data_de_fechamento_compativel_com_periodo(self, contabil):
        _, fato = contabil
        esperado = fato.periodo_codigo.map(lambda p: f"{ano_do_periodo(p)}-{FIM_DO_TRIMESTRE[p[0]]}")
        assert (fato.data_fechamento == esperado).all()

    def test_chave_natural_da_fato_sem_duplicatas(self, contabil):
        _, fato = contabil
        dup = fato[fato.duplicated(["id_conta", "data_fechamento"], keep=False)]
        assert dup.empty, f"{len(dup)} linhas duplicadas na chave (id_conta, data_fechamento)"

    def test_id_conta_unico_na_dimensao(self, contabil):
        dim, _ = contabil
        assert dim.id_conta.is_unique

    def test_toda_fato_tem_conta_na_dimensao(self, contabil):
        dim, fato = contabil
        orfas = set(fato.id_conta) - set(dim.id_conta)
        assert not orfas, f"{len(orfas)} id_conta na fato sem dimensão"

    def test_cada_conta_tem_um_registro_por_trimestre(self, contabil):
        _, fato = contabil
        contagem = fato.groupby("id_conta").size()
        assert (contagem == fato.periodo_codigo.nunique()).all(), contagem[contagem != fato.periodo_codigo.nunique()].to_dict()

    def test_dominios_da_dimensao(self, contabil):
        dim, _ = contabil
        assert set(dim.demonstrativo) == {"DRE", "BP", "DFC"}
        assert set(dim.tipo_conta) <= {"Analítica", "Sintética", "Gerencial"}
        assert set(dim.nivel_hierarquia) <= {1, 2}
        assert set(dim.natureza_sinal) <= {-1, 1}

    def test_tamanho_do_id_cabe_no_ddl(self, contabil):
        dim, _ = contabil
        assert dim.id_conta.str.len().max() <= 64  # VARCHAR(64) nos DDLs


class TestQualidadeDosDados:
    def test_ytd_da_dre_nunca_tem_buraco_no_meio_do_ano(self, contas):
        """Se um trimestre for NULL, os seguintes do mesmo ano também ficariam subestimados."""
        dre = contas.m[(contas.m.demonstrativo == "DRE") & (contas.m.tipo_conta != "Gerencial")].copy()
        dre["ano"] = dre.periodo_codigo.map(ano_do_periodo)
        buracos = dre[dre.valor_discreto.isna()].groupby("descricao_conta").size()
        # Linhas que só existem em parte da série (ex.: Operações descontinuadas) são toleradas;
        # o que não pode é uma conta central sumir.
        centrais = ["Receita operacional líquida", "Custos e despesas operacionais", "Resultado bruto"]
        assert not buracos.reindex(centrais).fillna(0).any()

    def test_saldo_final_de_caixa_nao_e_zero_fabricado(self, contas):
        """4T19–2T20 não têm DFC: o 0 da planilha deve virar NULL."""
        fim = contas.serie("DFC", "No final do exercício").dropna()
        assert (fim != 0).all(), f"zeros em: {list(fim[fim == 0].index)}"

    def test_ddl_dos_valores_contabeis_preserva_a_precisao_da_fonte(self, contabil):
        """A fonte traz até 5 casas em R$ mil; o DDL não pode arredondar mais que isso."""
        _, fato = contabil
        for col in ("valor_discreto", "valor_ytd"):
            escalas = _escala_no_ddl(col)
            assert len(escalas) == 1, f"{col}: DDLs divergentes entre bancos: {escalas}"
            escala = escalas.pop()
            perdas = _casas(fato[col], escala)
            assert perdas.empty, f"{col}: {len(perdas)} valores perdem precisão em {escala} casas"

    def test_valores_nao_tem_ruido_de_ponto_flutuante(self, contabil):
        """Ex.: 16959.278090000007 deve sair como 16959.27809."""
        _, fato = contabil
        v = fato[["valor_discreto", "valor_ytd"]].stack().dropna()
        assert (v == v.round(5)).all(), v[v != v.round(5)].head().tolist()

    def test_rotulos_sem_nota_de_rodape_colada(self, contabil):
        dim, _ = contabil
        sujos = dim[dim.descricao_conta.str.contains(r"[A-Za-zÀ-ÿ\)]\d$", regex=True)].descricao_conta.tolist()
        assert not sujos, sujos

    def test_rotulos_repetidos_no_mesmo_bloco_sao_desambiguados(self, contabil):
        """Rótulos repetidos (ex.: '(-) Redução ao valor recuperável de ativos') precisam de ids distintos."""
        dim, _ = contabil
        grupo = dim.groupby(["demonstrativo", "subgrupo", "descricao_conta"]).id_conta.nunique()
        repetidos = grupo[grupo > 1]
        # Não é erro: documenta quais rótulos dependem do contador de ocorrência (frágil se a RI inserir linhas).
        assert len(repetidos) <= 10, f"muitos rótulos dependem do contador de ocorrência: {len(repetidos)}"
