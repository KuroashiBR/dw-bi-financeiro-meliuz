"""Reconciliações internas das demonstrações (BP, DRE, DFC) e entre elas.

Cada teste valida uma identidade contábil sobre a SAÍDA do extrator (o que seria carregado no DW).
Se a RI mudar o layout ou republicar um número inconsistente, o teste correspondente falha.
"""

import pandas as pd
import pytest

from conftest import valor_anual
from helpers import TOL, ano_do_periodo, exige_zero

# ----------------------------------------------------------------------------- Balanço


class TestBalanco:
    def test_ativo_igual_passivo_mais_pl(self, contas):
        ativo = contas.serie("BP", "Total do ativo")
        pas_pl = contas.serie("BP", "Total do passivo e patrimônio líquido")
        exige_zero(ativo - pas_pl, "Total do ativo = Total do passivo + PL", min_n=25)

    def test_ativo_igual_soma_dos_grupos_do_passivo(self, contas):
        soma = (
            contas.serie("BP", "Total do passivo circulante")
            + contas.serie("BP", "Total do passivo não circulante")
            + contas.serie("BP", "Total do patrimônio líquido")
        )
        exige_zero(contas.serie("BP", "Total do ativo") - soma, "Ativo = PC + PNC + PL", min_n=25)

    def test_ativo_igual_circulante_mais_nao_circulante(self, contas):
        soma = contas.serie("BP", "Total do ativo circulante") + contas.serie("BP", "Total do ativo não circulante")
        exige_zero(contas.serie("BP", "Total do ativo") - soma, "Ativo = AC + ANC", min_n=25)

    def test_pl_igual_controladores_mais_nao_controladores(self, contas):
        diff = (
            contas.serie("BP", "Total do patrimônio líquido")
            - contas.serie("BP", "Patrimônio líquido atribuído a controladores")
            - contas.serie("BP", "Patrimônio líquido atribuído a não controladores")
        )
        exige_zero(diff, "PL total = controladores + não controladores", min_n=25)

    @pytest.mark.parametrize(
        "total, subgrupo",
        [
            ("Total do ativo circulante", "ATIVO_CIRCULANTE"),
            ("Total do passivo circulante", "PASSIVO_CIRCULANTE"),
            ("Total do passivo não circulante", "PASSIVO_NAO_CIRCULANTE"),
        ],
    )
    def test_subtotal_igual_soma_das_contas_analiticas(self, contas, total, subgrupo):
        """Valida a classificação Analítica/Sintética: se uma conta for mal tipada, a soma não fecha."""
        diff = contas.serie("BP", total) - contas.soma_analiticas("BP", subgrupo)
        exige_zero(diff, f"{total} = soma das analíticas de {subgrupo}", min_n=25)

    def test_total_do_ativo_nunca_e_zero_fabricado(self, contas):
        """1T19–3T19 não têm balanço: deve ser NULL, nunca 0."""
        s = contas.serie("BP", "Total do ativo").dropna()
        assert (s > 0).all(), f"Total do ativo com valor <= 0 em: {s[s <= 0].to_dict()}"


# ----------------------------------------------------------------------------- DRE


class TestDRE:
    @pytest.fixture
    def d(self, contas):
        return lambda nome, **kw: contas.serie("DRE", nome, "valor_discreto", **kw)

    def test_resultado_bruto(self, d):
        diff = d("Resultado bruto") - d("Receita operacional líquida") - d("Custos e despesas operacionais")
        exige_zero(diff, "Resultado bruto = Receita + Custos", min_n=31)

    def test_ebit(self, d):
        diff = (
            d("Lucro (prejuízo) antes do resultado financeiro e impostos")
            - d("Resultado bruto")
            - d("Resultado de participações societárias")
        )
        exige_zero(diff, "EBIT = Resultado bruto + participações", min_n=31)

    def test_lucro_antes_dos_tributos(self, d):
        diff = (
            d("Lucro (prejuízo) antes dos tributos sobre o lucro")
            - d("Lucro (prejuízo) antes do resultado financeiro e impostos")
            - d("Resultado financeiro, líquido")
        )
        exige_zero(diff, "LAIR = EBIT + resultado financeiro", min_n=31)

    def test_lucro_operacoes_continuadas(self, d):
        diff = (
            d("Lucro líquido (prejuízo) do período de operações em continuidade")
            - d("Lucro (prejuízo) antes dos tributos sobre o lucro")
            - d("Imposto de renda e contribuição social corrente e diferido")
        )
        exige_zero(diff, "LL continuadas = LAIR + IR/CS", min_n=31)

    def test_lucro_liquido_total(self, d):
        diff = (
            d("Lucro líquido (prejuízo) do exercício")
            - d("Lucro líquido (prejuízo) do período de operações em continuidade")
            - d("Operações descontinuadas")
        )
        # Operações descontinuadas só existem na planilha a partir de 2022 (Bankly): antes é NULL.
        exige_zero(diff, "LL = continuadas + descontinuadas", min_n=15)

    def test_custos_igual_soma_dos_componentes(self, d):
        componentes = [
            ("Cashback", None),
            ("Pessoal", None),
            ("Publicidade e propaganda", None),
            ("Softwares", None),
            ("Serviços de terceiros", None),
            ("Depreciação e amortização", None),
            ("Reversão (redução) ao valor recuperável de ativos", None),
            ("Ajuste a valor justo de earn-out a pagar e de opção de compra", None),
            ("Outros", 1),  # 2ª ocorrência: a 1ª é o 'Outros' filho de Cashback
        ]
        soma = sum(d(c, sub="RESULTADO_OPERACIONAL", ocorrencia=o).fillna(0) for c, o in componentes)
        exige_zero(d("Custos e despesas operacionais") - soma, "Custos = soma dos componentes", min_n=31)

    def test_cashback_igual_shopping_mais_outros_desde_1t21(self, d):
        """A abertura do cashback só existe a partir do 1T21 (antes, os dois filhos são 0)."""
        diff = (
            d("Cashback")
            - d("Shopping", sub="RESULTADO_OPERACIONAL")
            - d("Outros", sub="RESULTADO_OPERACIONAL", ocorrencia=0)  # filho de Cashback
        )
        diff = diff[[p for p in diff.index if ano_do_periodo(p) >= 2021]]
        exige_zero(diff, "Cashback = Shopping + Outros (>=1T21)", min_n=20)

    def test_ebitda_igual_ebit_mais_da(self, d):
        """O D&A é negativo na DRE, então EBITDA = EBIT - D&A."""
        diff = (
            d("EBITDA")
            - d("Lucro (prejuízo) antes do resultado financeiro e impostos")
            + d("Depreciação e amortização", sub="RESULTADO_OPERACIONAL")
        )
        exige_zero(diff, "EBITDA = EBIT + |D&A|", min_n=31)

    def test_ebitda_ajustado(self, d):
        diff = d("EBITDA Ajustado") - d("EBITDA") - d("Itens extraordinários")
        exige_zero(diff, "EBITDA Ajustado = EBITDA + itens extraordinários", min_n=31)

    def test_ytd_do_4t_igual_soma_dos_quatro_discretos(self, contas):
        dre = contas.m[contas.m.demonstrativo == "DRE"].copy()
        dre["ano"] = dre.periodo_codigo.map(ano_do_periodo)
        ruins = []
        for (id_conta, ano), g in dre.groupby(["id_conta", "ano"]):
            if len(g) != 4 or g.valor_discreto.isna().any():
                continue
            ytd_4t = g.loc[g.periodo_codigo.str[0] == "4", "valor_ytd"].iloc[0]
            if abs(g.valor_discreto.sum() - ytd_4t) > TOL:
                ruins.append((g.descricao_conta.iloc[0], ano))
        assert not ruins, f"YTD do 4T != soma dos discretos em: {ruins[:10]}"

    @pytest.mark.parametrize(
        "rotulo, nome",
        [
            ("Receita operacional líquida", "Receita operacional líquida"),
            ("Custos e despesas operacionais", "Custos e despesas operacionais"),
            ("Lucro líquido (prejuízo) do exercício", "Lucro líquido (prejuízo) do exercício"),
        ],
    )
    def test_ytd_do_4t_igual_coluna_anual_da_planilha(self, contas, planilha_bruta, rotulo, nome):
        """Compara com as colunas anuais da PRÓPRIA fonte (2019–2025): pega erro de extração/YTD."""
        ytd = contas.serie("DRE", nome, "valor_ytd", sub="RESULTADO_OPERACIONAL")
        diffs = pd.Series(
            {f"4T{a % 100}": ytd[f"4T{a % 100}"] - valor_anual(planilha_bruta, rotulo, a) for a in range(2019, 2026)}
        )
        exige_zero(diffs, f"YTD 4T x coluna anual: {nome}", min_n=7)


# ----------------------------------------------------------------------------- DFC


class TestDFC:
    CFO = "Caixa líquido gerado nas atividades operacionais"
    CFI = "Caixa líquido gerado pelas (utilizado nas) atividades de investimento"
    CFF = "Caixa líquido gerado pelas (utilizado nas) atividades de financiamento"
    CAMBIO = "Efeito de variação de câmbio de ajuste de conversão"
    VAR = "Variação líquida de caixa e equivalentes de caixa"

    def _soma_fluxos(self, contas, col):
        s = lambda n, **kw: contas.serie("DFC", n, col, **kw)  # noqa: E731
        return s(self.CFO) + s(self.CFI) + s(self.CFF) + s(self.CAMBIO).fillna(0)

    def test_fluxos_somam_a_variacao_de_caixa_ytd(self, contas):
        var = contas.serie("DFC", self.VAR, "valor_ytd", sub="VARIACAO_CAIXA_PERIODO")
        exige_zero(self._soma_fluxos(contas, "valor_ytd") - var, "CFO+CFI+CFF+câmbio = variação (YTD)", min_n=20)

    def test_fluxos_somam_a_variacao_de_caixa_discreta(self, contas):
        var = contas.serie("DFC", self.VAR, "valor_discreto", sub="VARIACAO_CAIXA_PERIODO")
        exige_zero(self._soma_fluxos(contas, "valor_discreto") - var, "CFO+CFI+CFF+câmbio = variação (discreto)", min_n=15)

    def test_saldo_inicial_mais_variacao_igual_saldo_final(self, contas):
        ini = contas.serie("DFC", "No início do exercício")
        fim = contas.serie("DFC", "No final do exercício")
        var = contas.serie("DFC", self.VAR, "valor_ytd", sub="VARIACAO_CAIXA_PERIODO")
        # 4T19–2T20 não têm DFC na fonte; o saldo final dessa fase é tratado em test_integridade.
        exige_zero(ini + var - fim, "Saldo inicial + variação = saldo final", min_n=20,
                   ignorar=["1T19", "2T19", "3T19", "4T19", "1T20", "2T20"])

    def test_saldo_inicial_do_ano_igual_saldo_final_do_4t_anterior(self, contas):
        ini = contas.serie("DFC", "No início do exercício")
        fim = contas.serie("DFC", "No final do exercício")
        diffs = pd.Series(
            {p: ini[p] - fim[f"4T{ano_do_periodo(p) - 1 - 2000}"] for p in ini.index if ano_do_periodo(p) >= 2021}
        )
        exige_zero(diffs, "Saldo inicial do ano = saldo final do 4T anterior", min_n=20)

    # No 2T23 e 3T23 o caixa da Bankly/Acessopar foi reclassificado para "ativo mantido para venda"
    # (CPC 31 / IFRS 5). O balanço o exclui do "Caixa e equivalentes de caixa", mas a DFC consolidada o
    # mantém no saldo final. Valores conferidos nos ITRs (nota 3.a e nota 8):
    #   2T23: Bankly 11.669 + Acessopar 185 = 11.854   | DFC final consolidada: 71.558
    #   3T23: Bankly 92.767 + Acessopar 182 = 92.949   | DFC final consolidada: 258.638
    CAIXA_OPERACOES_DESCONTINUADAS = {"2T23": 11854.0, "3T23": 92949.0}
    DFC_FINAL_ITR = {"2T23": 71558.0, "3T23": 258638.0}

    def test_caixa_final_da_dfc_igual_caixa_do_balanco_mais_descontinuadas(self, contas):
        """Caixa final (DFC) = caixa do BP + caixa atribuível a operações descontinuadas (nota 3.a do ITR)."""
        fim = contas.serie("DFC", "No final do exercício")
        bp = contas.serie("BP", "Caixa e equivalentes de caixa", sub="ATIVO_CIRCULANTE")
        ajuste = pd.Series(self.CAIXA_OPERACOES_DESCONTINUADAS).reindex(fim.index).fillna(0.0)
        diff = (fim - bp - ajuste)[[p for p in fim.index if (ano_do_periodo(p), p[0]) >= (2020, "3")]]
        exige_zero(diff, "Caixa final (DFC) = BP + caixa de operações descontinuadas", min_n=20)

    def test_ajuste_de_descontinuadas_e_realmente_necessario(self, contas):
        """Guarda contra exceção esquecida: sem o ajuste, 2T23 e 3T23 NÃO reconciliam."""
        fim = contas.serie("DFC", "No final do exercício")
        bp = contas.serie("BP", "Caixa e equivalentes de caixa", sub="ATIVO_CIRCULANTE")
        for p in self.CAIXA_OPERACOES_DESCONTINUADAS:
            assert abs(fim[p] - bp[p]) > TOL, f"{p} reconcilia sem ajuste: remova-o de CAIXA_OPERACOES_DESCONTINUADAS"

    @pytest.mark.parametrize("periodo", ["2T23", "3T23"])
    def test_saldo_final_da_dfc_bate_com_o_itr(self, contas, periodo):
        """Âncora externa: saldo final consolidado impresso na DFC do ITR de cada trimestre."""
        fim = contas.serie("DFC", "No final do exercício")
        assert fim[periodo] == pytest.approx(self.DFC_FINAL_ITR[periodo], abs=TOL)

    def test_ytd_do_4t_igual_soma_dos_discretos(self, contas):
        dfc = contas.m[(contas.m.demonstrativo == "DFC") & (contas.m.subgrupo != "SALDOS_CAIXA")].copy()
        dfc["ano"] = dfc.periodo_codigo.map(ano_do_periodo)
        ruins = []
        for (id_conta, ano), g in dfc[dfc.ano.between(2021, 2025)].groupby(["id_conta", "ano"]):
            if len(g) != 4 or g.valor_discreto.isna().any() or g.valor_ytd.isna().any():
                continue
            if abs(g.valor_discreto.sum() - g.loc[g.periodo_codigo.str[0] == "4", "valor_ytd"].iloc[0]) > TOL:
                ruins.append((g.descricao_conta.iloc[0], ano))
        assert not ruins, f"Soma dos discretos != YTD do 4T: {ruins[:10]}"

    @pytest.mark.parametrize(
        "rotulo",
        [CFO, CFI, CFF],
    )
    def test_ytd_do_4t_igual_coluna_anual_da_planilha(self, contas, planilha_bruta, rotulo):
        ytd = contas.serie("DFC", rotulo, "valor_ytd")
        diffs = pd.Series(
            {f"4T{a % 100}": ytd[f"4T{a % 100}"] - valor_anual(planilha_bruta, rotulo, a) for a in range(2021, 2026)}
        )
        exige_zero(diffs, f"DFC YTD 4T x coluna anual: {rotulo[:45]}", min_n=5)


# ----------------------------------------------------------------------------- Cruzadas


class TestCruzadas:
    def test_lair_da_dre_igual_lair_das_operacoes_continuadas_da_dfc(self, contas):
        """A DFC parte do resultado antes dos tributos das operações em CONTINUIDADE.

        (A linha consolidada da DFC inclui operações descontinuadas e não deve ser usada aqui.)
        """
        dre = contas.serie("DRE", "Lucro (prejuízo) antes dos tributos sobre o lucro", "valor_ytd")
        dfc = contas.serie(
            "DFC", "Resultado do período antes dos tributos sobre o lucro das operações em continuidade", "valor_ytd"
        )
        exige_zero(dfc - dre, "LAIR (DFC, continuadas) = LAIR (DRE)", min_n=20)
