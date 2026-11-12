-- =========================================================================
-- VIEWS ANALÍTICAS E DE AUDITORIA CONTÁBIL - MÉLIUZ (CASH3) | SQL SERVER
-- =========================================================================

-- 1. Visão Consolidada das Demonstrações Financeiras (DRE, BP, DFC)
CREATE OR ALTER VIEW vw_analise_contabil_consolidada AS
SELECT
    f.data_fechamento,
    f.periodo_codigo,
    YEAR(f.data_fechamento) AS ano,
    DATEPART(QUARTER, f.data_fechamento) AS trimestre,
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
GO

-- 2. Visão Consolidada dos Indicadores Operacionais e Tesouraria Bitcoin
CREATE OR ALTER VIEW vw_analise_indicadores_operacionais AS
SELECT
    f.data_fechamento,
    f.periodo_codigo,
    YEAR(f.data_fechamento) AS ano,
    DATEPART(QUARTER, f.data_fechamento) AS trimestre,
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
GO

-- 3. View de Homologação e Auditoria Contábil (Balizadores 3T26)
CREATE OR ALTER VIEW vw_auditoria_homologacao_3t26 AS
SELECT
    d.demonstrativo,
    d.subgrupo,
    d.descricao_conta AS metrica_auditada,
    f.periodo_codigo,
    f.valor_discreto,
    f.valor_ytd
FROM fato_movimento_contabil f
INNER JOIN dim_plano_contas d
    ON f.id_conta = d.id_conta
WHERE f.periodo_codigo = '3T26'
  AND (
      (d.demonstrativo = 'DRE' AND d.descricao_conta IN ('Receita operacional líquida', 'Lucro líquido (prejuízo) do exercício'))
      OR (d.demonstrativo = 'DFC' AND d.descricao_conta IN (
          'Caixa líquido gerado nas atividades operacionais',
          'Caixa líquido usado nas atividades de financiamento',
          'Recebimento pela venda de Bitcoin'
      ))
  )
UNION ALL
SELECT
    'OPERACIONAL' AS demonstrativo,
    m.subgrupo,
    m.nome_metrica AS metrica_auditada,
    f.periodo_codigo,
    CAST(f.valor_metrica AS DECIMAL(18, 2)) AS valor_discreto,
    CAST(f.valor_metrica AS DECIMAL(18, 2)) AS valor_ytd
FROM fato_indicadores_operacionais f
INNER JOIN dim_metrica_operacional m
    ON f.id_metrica = m.id_metrica
WHERE f.periodo_codigo = '3T26'
  AND m.id_metrica = 'BTC_POSICAO_ACUMULADA';
GO
