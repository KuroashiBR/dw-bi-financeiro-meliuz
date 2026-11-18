"""Reconciliações das métricas operacionais e da tesouraria de Bitcoin."""

import pandas as pd
import pytest

from helpers import ano_do_periodo

IDS_ESPERADOS = {
    "GMV_SHOPPING_BRASIL", "TAKE_RATE_BRUTO", "TAKE_RATE_LIQUIDO", "CONTAS_TOTAIS",
    "CONTAS_DIGITAIS_BV", "CARTOES_EMITIDOS_BV", "TPV_BANCO_BV", "TPV_LEGADO",
    "BTC_POSICAO_ACUMULADA", "BTC_PRECO_MEDIO_USD", "BTC_SATS_POR_ACAO", "BTC_GAIN_BRL_MI",
}


def serie(operacional, id_metrica) -> pd.Series:
    _, fato = operacional
    x = fato[fato.id_metrica == id_metrica].sort_values("data_fechamento")
    assert not x.empty, f"{id_metrica} sem dados"
    return x.set_index("periodo_codigo").valor_metrica


class TestEstruturaOperacional:
    def test_todas_as_metricas_esperadas_estao_presentes(self, operacional):
        dim, fato = operacional
        assert set(dim.id_metrica) == IDS_ESPERADOS
        assert set(fato.id_metrica) == IDS_ESPERADOS

    def test_chave_natural_sem_duplicatas(self, operacional):
        _, fato = operacional
        assert not fato.duplicated(["id_metrica", "data_fechamento"]).any()

    def test_toda_fato_tem_metrica_na_dimensao(self, operacional):
        dim, fato = operacional
        assert set(fato.id_metrica) <= set(dim.id_metrica)

    def test_metricas_de_base_cobrem_toda_a_serie(self, operacional, contabil):
        for m in ["GMV_SHOPPING_BRASIL", "CONTAS_TOTAIS"]:
            assert set(serie(operacional, m).index) == set(contabil[1].periodo_codigo), m

    def test_bitcoin_cobre_desde_1t25(self, operacional, contabil):
        s = serie(operacional, "BTC_POSICAO_ACUMULADA")
        assert list(s.index) == list(contabil[1].loc[contabil[1].data_fechamento >= "2025-03-31", "periodo_codigo"].drop_duplicates())


class TestValoresOperacionais:
    @pytest.mark.parametrize("m", ["GMV_SHOPPING_BRASIL", "CONTAS_TOTAIS", "TPV_LEGADO"])
    def test_metricas_de_volume_positivas(self, operacional, m):
        s = serie(operacional, m)
        assert (s >= 0).all() and s.max() > 0

    def test_net_take_rate_nao_excede_take_rate_bruto(self, operacional):
        bruto = serie(operacional, "TAKE_RATE_BRUTO")
        liquido = serie(operacional, "TAKE_RATE_LIQUIDO")
        comum = bruto.index.intersection(liquido.index)
        ruins = (liquido[comum] - bruto[comum])
        assert (ruins <= 1e-9).all(), ruins[ruins > 1e-9].to_dict()

    @pytest.mark.parametrize("m", ["CONTAS_DIGITAIS_BV", "CARTOES_EMITIDOS_BV"])
    def test_acumulados_da_parceria_bv_nunca_diminuem(self, operacional, m):
        s = serie(operacional, m)
        assert s.is_monotonic_increasing, s.diff()[s.diff() < 0].to_dict()

    @pytest.mark.parametrize("m", ["TAKE_RATE_BRUTO", "TAKE_RATE_LIQUIDO"])
    def test_take_rate_sem_zeros_fabricados(self, operacional, m):
        """Zeros anteriores à 1ª medição real (2019–2020 na fonte) devem ser NULL."""
        s = serie(operacional, m)
        assert (s > 0).all(), f"zeros em: {list(s[s <= 0].index)}"

    @pytest.mark.parametrize("m, primeiro", [("TAKE_RATE_BRUTO", "3T20"), ("TAKE_RATE_LIQUIDO", "1T21")])
    def test_take_rate_comeca_no_primeiro_periodo_com_medicao(self, operacional, m, primeiro):
        """Primeiro valor > 0 conferido na aba 'Dados Oper.' (linhas 'Take rate' e 'Net take rate')."""
        assert serie(operacional, m).index[0] == primeiro

    def test_ddl_das_metricas_preserva_a_precisao(self, operacional):
        """Take rate é fração com até 10 casas; o DDL não pode truncar (antes era NUMERIC(18,4))."""
        import re
        from pathlib import Path

        _, fato = operacional
        for sql in (Path(__file__).resolve().parent.parent / "database").glob("*/01_ddl_schema.sql"):
            m = re.search(r"valor_metrica\s+(?:NUMERIC|DECIMAL)\(\d+,\s*(\d+)\)", sql.read_text(encoding="utf-8"))
            escala = int(m.group(1))
            perdas = fato.valor_metrica[(fato.valor_metrica - fato.valor_metrica.round(escala)).abs() > 1e-12]
            assert perdas.empty, f"{sql.parent.name}: {len(perdas)} métricas perdem precisão em {escala} casas"


class TestBitcoin:
    def test_venda_na_dfc_coincide_com_queda_da_posicao(self, contas, operacional):
        """Se a posição em BTC cai no trimestre, deve haver recebimento pela venda de Bitcoin na DFC (e vice-versa)."""
        pos = serie(operacional, "BTC_POSICAO_ACUMULADA")
        venda = contas.serie("DFC", "Recebimento pela venda de Bitcoin", "valor_discreto").fillna(0)
        resultados = {}
        for ant, atual in zip(pos.index[:-1], pos.index[1:]):
            caiu = pos[atual] < pos[ant] - 1e-9
            vendeu = venda[atual] > 0
            resultados[atual] = (caiu, vendeu)
        errados = {p: r for p, r in resultados.items() if r[0] != r[1]}
        assert not errados, f"(posição caiu, houve venda na DFC) divergente em: {errados}"

    def test_posicao_so_cai_quando_ha_venda_e_preco_medio_nao_muda_na_venda(self, operacional):
        """Venda não altera o preço médio de compra acumulado."""
        pos = serie(operacional, "BTC_POSICAO_ACUMULADA")
        preco = serie(operacional, "BTC_PRECO_MEDIO_USD")
        for ant, atual in zip(pos.index[:-1], pos.index[1:]):
            if pos[atual] < pos[ant]:
                assert preco[atual] == pytest.approx(preco[ant], rel=1e-6), f"preço médio mudou na venda de {atual}"
