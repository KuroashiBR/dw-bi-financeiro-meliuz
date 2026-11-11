let
    DataInicial = #date(2019, 1, 1),
    DataFinal = Date.EndOfYear(DateTime.Date(DateTime.LocalNow())),
    TotalDias = Duration.Days(DataFinal - DataInicial) + 1,
    ListaDatas = List.Dates(DataInicial, TotalDias, #duration(1, 0, 0, 0)),
    Tabela = Table.FromList(ListaDatas, Splitter.SplitByNothing(), {"Data"}, null, ExtraValues.Error),
    AlteraTipo = Table.TransformColumnTypes(Tabela, {{"Data", type date}}),
    AdicionaAno = Table.AddColumn(AlteraTipo, "Ano", each Date.Year([Data]), Int64.Type),
    AdicionaTrimestre = Table.AddColumn(AdicionaAno, "Trimestre", each Date.QuarterOfYear([Data]), Int64.Type),
    AdicionaPeriodo = Table.AddColumn(AdicionaTrimestre, "Periodo", each Text.From([Trimestre]) & "T" & Text.End(Text.From([Ano]), 2), type text),
    AdicionaMesAno = Table.AddColumn(AdicionaPeriodo, "MesAno", each Date.ToText([Data], "MMM/yy"), type text),
    AdicionaFimTrimestre = Table.AddColumn(AdicionaMesAno, "DataFimTrimestre", each Date.EndOfQuarter([Data]), type date)
in
    AdicionaFimTrimestre
