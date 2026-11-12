CREATE OR REPLACE VIEW vw_analise_contabil_consolidada AS
SELECT
    f.data_fechamento,
    f.periodo_codigo,
    EXTRACT(YEAR FROM f.data_fechamento)::INT AS ano,
    EXTRACT(QUARTER FROM f.data_fechamento)::INT AS trimestre,
    d.id_conta,
    d.demonstrativo,
    d.secao_contabil,
    d.subgrupo,
    d.descricao_conta,
    d.tipo_conta,
    d.nivel_hierarquia,
    d.ordem_exibicao,
    d.natureza_sinal,
    f.valor_discreto,
    f.valor_ytd,
    f.data_carga
FROM fato_movimento_contabil f
INNER JOIN dim_plano_contas d
    ON f.id_conta = d.id_conta;

CREATE OR REPLACE VIEW vw_analise_indicadores_operacionais AS
SELECT
    f.data_fechamento,
    f.periodo_codigo,
    EXTRACT(YEAR FROM f.data_fechamento)::INT AS ano,
    EXTRACT(QUARTER FROM f.data_fechamento)::INT AS trimestre,
    m.id_metrica,
    m.categoria,
    m.subgrupo,
    m.nome_metrica,
    m.unidade_medida,
    f.valor_metrica,
    f.data_carga
FROM fato_indicadores_operacionais f
INNER JOIN dim_metrica_operacional m
    ON f.id_metrica = m.id_metrica;
