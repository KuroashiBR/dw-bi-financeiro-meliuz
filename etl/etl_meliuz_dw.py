"""
Pipeline de Ingestão e Modelagem Dimensional - Méliuz (CASH3)
Executa extração, sanitização, desagregação temporal e upsert idempotente
para PostgreSQL e SQL Server com subgrupos rigorosos e reconciliação da DFC.
"""

import os
import re
import glob
import hashlib
import logging
import urllib.parse
import pandas as pd
from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

class MeliuzETLPipeline:
    def __init__(self, data_folder="./data", db_type="sqlserver", conn_string=None):
        self.data_folder = data_folder
        self.db_type = db_type.lower()
        self.conn_string = conn_string
        self.engine = create_engine(conn_string) if conn_string else None

    def get_latest_file(self):
        """Identifica a planilha mais recente, ignorando arquivos temporários (~$)."""
        pattern = os.path.join(self.data_folder, "*Meliuz*.xlsx")
        files = [f for f in glob.glob(pattern) if not os.path.basename(f).startswith("~$")]
        if not files:
            raise FileNotFoundError(f"Nenhum arquivo válido encontrado em {self.data_folder}")
        return max(files, key=os.path.getmtime)

    @staticmethod
    def generate_hash_id(parts):
        """Gera hash determinístico MD5 baseado nas partes constitutivas da chave natural."""
        clean_parts = [re.sub(r'[^a-zA-Z0-9_]', '', str(p).upper().replace(' ', '_')) for p in parts]
        raw_key = "_".join(clean_parts).encode('utf-8')
        return hashlib.md5(raw_key).hexdigest()[:16]

    def detect_quarter_columns(self, header_row):
        """Varre os trimestres parando na coluna vazia que antecede os anos cheios."""
        quarters = []
        for c_idx, val in header_row.items():
            if pd.isna(val):
                if len(quarters) > 0:
                    break
                continue
            val_str = str(val).split('|')[0].strip()
            match = re.search(r'([1-4]T\d{2})', val_str, re.IGNORECASE)
            if match:
                q_code = match.group(1).upper()
                q_num = int(q_code[0])
                yy = int(q_code[2:])
                full_year = 2000 + yy if yy < 50 else 1900 + yy
                m_end = q_num * 3
                d_end = 31 if q_num in (1, 4) else 30
                quarters.append({
                    "col_idx": c_idx,
                    "periodo_codigo": q_code,
                    "ano": full_year,
                    "trimestre": q_num,
                    "data_fechamento": f"{full_year}-{m_end:02d}-{d_end:02d}"
                })
        return quarters

    def find_section_bounds(self, df_fin):
        """Localiza os limites das seções por âncoras de texto com asserção estrita."""
        bounds = {}
        for idx, val in df_fin['Unnamed: 2'].items():
            if pd.isna(val):
                continue
            s = str(val).strip().lower()
            if 'dre (r$ mil)' in s:
                bounds['dre_start'] = idx + 1
            elif s == 'ebitda':
                bounds['ebitda_start'] = idx
            elif 'balanço patrimonial (r$ mil)' in s:
                bounds['dre_end'] = idx - 1
                bounds['bp_start'] = idx + 1
            elif 'fluxo de caixa (r$ mil)' in s:
                bounds['bp_end'] = idx - 1
                bounds['dfc_start'] = idx + 1
            elif 'variação líquida de caixa e equivalentes de caixa' in s and 'dfc_start' in bounds and idx > 250:
                bounds['dfc_end'] = idx

        required_bounds = ['dre_start', 'ebitda_start', 'dre_end', 'bp_start', 'bp_end', 'dfc_start', 'dfc_end']
        for rb in required_bounds:
            assert rb in bounds, f"Falha de integridade: âncora textual para '{rb}' não foi localizada."
        return bounds

    def parse_financial_statements(self, file_path):
        """Extrai DRE, Balanço e DFC tratando colisões, subtotais e desagregação."""
        df = pd.read_excel(file_path, sheet_name='Finan. Cons. | Finan. Cons.')
        quarters = self.detect_quarter_columns(df.iloc[2])
        bounds = self.find_section_bounds(df)

        dim_contas = {}
        fato_contabil = []
        seen_keys = {}

        current_sec = "HEADER"
        current_sub = "GERAL"

        ignore_exact_headers = {
            'balanço patrimonial (r$ mil)', 'fluxo de caixa (r$ mil)', 'dre (r$ mil)',
            'período acumulado', 'atividades operacionais', 'atividades de investimento',
            'atividades de financiamento'
        }

        for r in range(bounds['dre_start'], bounds['dfc_end'] + 1):
            raw_pt = df.iloc[r]['Unnamed: 2']
            if pd.isna(raw_pt) or str(raw_pt).strip().startswith('¹') or str(raw_pt).strip().lower() == 'notas:':
                continue

            pt_str = str(raw_pt)
            indent = len(pt_str) - len(pt_str.lstrip(' '))
            clean_pt = re.sub(r'[¹²³⁴⁵⁶⁷⁸⁹⁰]', '', pt_str).strip()
            clean_pt = re.sub(r'\s+', ' ', clean_pt)
            clean_lower = clean_pt.lower()

            if r < bounds['ebitda_start']:
                current_sec = "DRE"
                current_sub = "RESULTADO_OPERACIONAL"
            elif r <= bounds['dre_end']:
                current_sec = "DRE"
                current_sub = "CONCILIACAO_EBITDA"
            elif r < bounds['dfc_start']:
                current_sec = "BP"
                if 'ativo circulante' in clean_lower and 'total' not in clean_lower:
                    current_sub = "ATIVO_CIRCULANTE"
                elif 'ativo não circulante' in clean_lower and 'total' not in clean_lower:
                    current_sub = "ATIVO_NAO_CIRCULANTE"
                elif 'realizável a longo prazo' in clean_lower and 'total' not in clean_lower:
                    current_sub = "ATIVO_RLP"
                elif clean_lower == 'investimentos':
                    current_sub = "ATIVO_INVESTIMENTOS"
                elif clean_lower == 'imobilizado':
                    current_sub = "ATIVO_IMOBILIZADO"
                elif clean_lower == 'intangível':
                    current_sub = "ATIVO_INTANGIVEL"
                elif 'passivo circulante' in clean_lower and 'total' not in clean_lower:
                    current_sub = "PASSIVO_CIRCULANTE"
                elif 'passivo não circulante' in clean_lower and 'total' not in clean_lower:
                    current_sub = "PASSIVO_NAO_CIRCULANTE"
                elif 'patrimônio líquido' in clean_lower and 'total' not in clean_lower and 'controladores' not in clean_lower:
                    current_sub = "PATRIMONIO_LIQUIDO"
            else:
                current_sec = "DFC"
                if 'atividades operacionais' in clean_lower and 'caixa' not in clean_lower:
                    current_sub = "FLUXO_OPERACIONAL"
                elif 'atividades de investimento' in clean_lower and 'caixa' not in clean_lower:
                    current_sub = "FLUXO_INVESTIMENTO"
                elif 'atividades de financiamento' in clean_lower and 'caixa' not in clean_lower:
                    current_sub = "FLUXO_FINANCIAMENTO"
                elif any(k in clean_lower for k in ['efeito de variação de câmbio', 'efeito de variacao de cambio', 'variação cambial s/ caixa']):
                    current_sub = "EFEITO_CAMBIAL"
                elif any(k in clean_lower for k in ['saldo inicial', 'no início do período', 'no início do exercício', 'saldo final', 'no final do período', 'no final do exercício']):
                    current_sub = "SALDOS_CAIXA"
                elif 'variação líquida de caixa' in clean_lower:
                    if current_sub in ["FLUXO_FINANCIAMENTO", "FLUXO_INVESTIMENTO", "FLUXO_OPERACIONAL", "EFEITO_CAMBIAL"]:
                        current_sub = "VARIACAO_CAIXA_PERIODO"
                    else:
                        current_sub = "VARIACAO_CAIXA_TOTAL"

            if clean_lower in ignore_exact_headers:
                continue

            base_key = f"{current_sec}_{current_sub}_{clean_pt.upper()}"
            seen_keys[base_key] = seen_keys.get(base_key, 0) + 1
            occ = seen_keys[base_key]
            unique_key_parts = [current_sec, current_sub, clean_pt] if occ == 1 else [current_sec, current_sub, clean_pt, str(occ)]
            id_conta = self.generate_hash_id(unique_key_parts)

            if current_sub == "CONCILIACAO_EBITDA":
                tipo_conta = "Gerencial"
            elif any(k in clean_lower for k in [
                'resultado bruto', 'total do ativo', 'total do passivo', 'total do patrimônio',
                'lucro líquido', 'caixa líquido', 'variação líquida',
                'resultado ajustado', 'no final do exercício', 'no início do exercício',
                'no final do período', 'no início do período', 'custos e despesas operacionais',
                'patrimônio líquido atribuído a controladores'
            ]):
                tipo_conta = "Sintética"
            elif current_sec == "DRE" and any(k in clean_lower for k in ['lucro (prejuízo) antes', 'resultado do período antes dos tributos', 'resultado antes dos tributos']):
                tipo_conta = "Sintética"
            elif current_sec == "DFC" and clean_lower == 'resultado do período antes dos tributos sobre o lucro':
                tipo_conta = "Sintética"
            elif clean_pt == "Cashback" and current_sec == "DRE":
                tipo_conta = "Sintética"
            else:
                tipo_conta = "Analítica"

            series_vals = {}
            numeric_samples = []
            for q in quarters:
                val = df.iloc[r][q["col_idx"]]
                try:
                    num_val = float(val) if pd.notna(val) else None
                except (ValueError, TypeError):
                    num_val = None
                series_vals[q["periodo_codigo"]] = num_val
                if num_val is not None:
                    numeric_samples.append(num_val)

            mean_val = (sum(numeric_samples) / len(numeric_samples)) if numeric_samples else 0.0
            natureza_sinal = -1 if mean_val < 0 else 1
            nivel = 2 if indent > 0 else 1

            dim_contas[id_conta] = {
                "id_conta": id_conta,
                "demonstrativo": current_sec,
                "secao_contabil": current_sec,
                "subgrupo": current_sub,
                "descricao_conta": clean_pt,
                "tipo_conta": tipo_conta,
                "nivel_hierarquia": nivel,
                "ordem_exibicao": r * 10,
                "natureza_sinal": natureza_sinal
            }

            running_dre_ytd = 0.0
            current_dre_year = None

            for idx, q in enumerate(quarters):
                p_code = q["periodo_codigo"]
                cur_val = series_vals[p_code]
                v_discreto = cur_val
                v_ytd = cur_val

                if current_sec == "DRE":
                    if q["ano"] != current_dre_year:
                        current_dre_year = q["ano"]
                        running_dre_ytd = 0.0

                    if cur_val is not None:
                        running_dre_ytd += cur_val
                        v_discreto = cur_val
                        v_ytd = running_dre_ytd
                    else:
                        v_discreto = None
                        v_ytd = None

                elif current_sec == "DFC":
                    if current_sub == "SALDOS_CAIXA":
                        v_discreto = cur_val
                        v_ytd = cur_val
                    else:
                        if q["ano"] < 2020 or (q["ano"] == 2020 and q["trimestre"] in [1, 2]):
                            v_discreto = None
                            v_ytd = None
                        elif q["ano"] == 2020 and q["trimestre"] == 3:
                            v_discreto = None
                            v_ytd = cur_val
                        elif cur_val is not None:
                            v_ytd = cur_val
                            if q["trimestre"] == 1:
                                v_discreto = cur_val
                            else:
                                prev_code = quarters[idx - 1]["periodo_codigo"]
                                prev_val = series_vals.get(prev_code)
                                v_discreto = (cur_val - prev_val) if prev_val is not None else None

                elif current_sec == "BP":
                    v_discreto = cur_val
                    v_ytd = cur_val

                fato_contabil.append({
                    "id_conta": id_conta,
                    "data_fechamento": q["data_fechamento"],
                    "periodo_codigo": p_code,
                    "valor_discreto": v_discreto,
                    "valor_ytd": v_ytd
                })

        return pd.DataFrame(list(dim_contas.values())), pd.DataFrame(fato_contabil)

    def parse_operational_indicators(self, file_path):
        """Extrai métricas operacionais e da tesouraria de Bitcoin com sanitização de zeros."""
        xls = pd.ExcelFile(file_path)
        df_op = pd.read_excel(xls, sheet_name='Dados Oper. | Oper. Data')
        df_btc = pd.read_excel(xls, sheet_name='Bitcoin Tesou. | Bitcoin Treas.')
        quarters = self.detect_quarter_columns(df_op.iloc[2])

        dim_metricas = [
            {"id_metrica": "GMV_SHOPPING_BRASIL", "categoria": "SHOPPING", "subgrupo": "ECOMMERCE", "nome_metrica": "GMV Shopping Brasil", "unidade_medida": "R$ MIL", "row": 5, "source": "OP"},
            {"id_metrica": "TAKE_RATE_BRUTO", "categoria": "SHOPPING", "subgrupo": "MONETIZACAO", "nome_metrica": "Take Rate Méliuz", "unidade_medida": "%", "row": 7, "source": "OP"},
            {"id_metrica": "TAKE_RATE_LIQUIDO", "categoria": "SHOPPING", "subgrupo": "MONETIZACAO", "nome_metrica": "Net Take Rate Méliuz", "unidade_medida": "%", "row": 9, "source": "OP"},
            {"id_metrica": "CONTAS_TOTAIS", "categoria": "USUARIOS", "subgrupo": "BASE", "nome_metrica": "Contas Totais Méliuz", "unidade_medida": "MILHARES", "row": 11, "source": "OP"},
            {"id_metrica": "CONTAS_DIGITAIS_BV", "categoria": "SERVICOS_FINANCEIROS", "subgrupo": "PARCERIA_BV", "nome_metrica": "Contas Digitais Abertas BV", "unidade_medida": "UNIDADES", "row": 15, "source": "OP"},
            {"id_metrica": "CARTOES_EMITIDOS_BV", "categoria": "SERVICOS_FINANCEIROS", "subgrupo": "PARCERIA_BV", "nome_metrica": "Cartões Emitidos BV", "unidade_medida": "UNIDADES", "row": 16, "source": "OP"},
            {"id_metrica": "TPV_BANCO_BV", "categoria": "SERVICOS_FINANCEIROS", "subgrupo": "PARCERIA_BV", "nome_metrica": "TPV Parceria BV", "unidade_medida": "R$ MIL", "row": 17, "source": "OP"},
            {"id_metrica": "TPV_LEGADO", "categoria": "SERVICOS_FINANCEIROS", "subgrupo": "LEGADO", "nome_metrica": "TPV Operação Legada", "unidade_medida": "R$ MIL", "row": 20, "source": "OP"},
            {"id_metrica": "BTC_POSICAO_ACUMULADA", "categoria": "BITCOIN", "subgrupo": "TESOURARIA", "nome_metrica": "Posição Bitcoin em Tesouraria", "unidade_medida": "BTC", "row": 4, "source": "BTC"},
            {"id_metrica": "BTC_PRECO_MEDIO_USD", "categoria": "BITCOIN", "subgrupo": "TESOURARIA", "nome_metrica": "Preço Médio de Compra Bitcoin", "unidade_medida": "USD", "row": 6, "source": "BTC"},
            {"id_metrica": "BTC_SATS_POR_ACAO", "categoria": "BITCOIN", "subgrupo": "TESOURARIA", "nome_metrica": "Sats por Ação", "unidade_medida": "SATS", "row": 10, "source": "BTC"},
            {"id_metrica": "BTC_GAIN_BRL_MI", "categoria": "BITCOIN", "subgrupo": "TESOURARIA", "nome_metrica": "Bitcoin Gain", "unidade_medida": "R$ MILHOES", "row": 16, "source": "BTC"}
        ]

        fato_metricas = []
        for m in dim_metricas:
            target_df = df_op if m["source"] == "OP" else df_btc
            for q in quarters:
                col_match = None
                for c_col, c_val in target_df.iloc[2].items():
                    if pd.notna(c_val) and q["periodo_codigo"] in str(c_val):
                        col_match = c_col
                        break

                if col_match is not None:
                    val = target_df.iloc[m["row"]][col_match]
                    try:
                        num_val = float(val) if pd.notna(val) else None
                    except (ValueError, TypeError):
                        num_val = None

                    if m["id_metrica"] in ["TAKE_RATE_BRUTO", "TAKE_RATE_LIQUIDO"] and q["ano"] == 2019 and num_val == 0.0:
                        num_val = None

                    if num_val is not None:
                        fato_metricas.append({
                            "id_metrica": m["id_metrica"],
                            "data_fechamento": q["data_fechamento"],
                            "periodo_codigo": q["periodo_codigo"],
                            "valor_metrica": num_val
                        })

        df_dim_m = pd.DataFrame(dim_metricas).drop(columns=["row", "source"])
        return df_dim_m, pd.DataFrame(fato_metricas)

    def execute_upsert(self, df_dim_c, df_fato_c, df_dim_m, df_fato_m):
        """Executa carga em lote com declaração explícita de colunas no SQL."""
        if not self.engine:
            logging.info("Engine não conectada. Modo dry-run concluído.")
            return

        df_dim_c.to_sql("stg_dim_plano_contas", self.engine, if_exists="replace", index=False)
        df_fato_c.to_sql("stg_fato_movimento_contabil", self.engine, if_exists="replace", index=False)
        df_dim_m.to_sql("stg_dim_metrica_operacional", self.engine, if_exists="replace", index=False)
        df_fato_m.to_sql("stg_fato_indicadores_operacionais", self.engine, if_exists="replace", index=False)

        with self.engine.begin() as conn:
            if self.db_type == "sqlserver":
                conn.execute(text("""
                    MERGE INTO dim_plano_contas AS t 
                    USING stg_dim_plano_contas AS s ON t.id_conta = s.id_conta
                    WHEN MATCHED THEN 
                        UPDATE SET 
                            t.descricao_conta = s.descricao_conta, 
                            t.tipo_conta = s.tipo_conta, 
                            t.subgrupo = s.subgrupo,
                            t.ordem_exibicao = s.ordem_exibicao,
                            t.natureza_sinal = s.natureza_sinal
                    WHEN NOT MATCHED THEN 
                        INSERT (id_conta, demonstrativo, secao_contabil, subgrupo, descricao_conta, tipo_conta, nivel_hierarquia, ordem_exibicao, natureza_sinal)
                        VALUES (s.id_conta, s.demonstrativo, s.secao_contabil, s.subgrupo, s.descricao_conta, s.tipo_conta, s.nivel_hierarquia, s.ordem_exibicao, s.natureza_sinal);

                    MERGE INTO fato_movimento_contabil AS t 
                    USING stg_fato_movimento_contabil AS s 
                    ON t.id_conta = s.id_conta AND t.data_fechamento = s.data_fechamento
                    WHEN MATCHED THEN 
                        UPDATE SET 
                            t.valor_discreto = s.valor_discreto, 
                            t.valor_ytd = s.valor_ytd, 
                            t.data_carga = GETDATE()
                    WHEN NOT MATCHED THEN 
                        INSERT (id_conta, data_fechamento, periodo_codigo, valor_discreto, valor_ytd, data_carga)
                        VALUES (s.id_conta, s.data_fechamento, s.periodo_codigo, s.valor_discreto, s.valor_ytd, GETDATE());

                    MERGE INTO dim_metrica_operacional AS t 
                    USING stg_dim_metrica_operacional AS s ON t.id_metrica = s.id_metrica
                    WHEN NOT MATCHED THEN 
                        INSERT (id_metrica, categoria, subgrupo, nome_metrica, unidade_medida)
                        VALUES (s.id_metrica, s.categoria, s.subgrupo, s.nome_metrica, s.unidade_medida);

                    MERGE INTO fato_indicadores_operacionais AS t 
                    USING (SELECT * FROM stg_fato_indicadores_operacionais WHERE valor_metrica IS NOT NULL) AS s
                    ON t.id_metrica = s.id_metrica AND t.data_fechamento = s.data_fechamento
                    WHEN MATCHED THEN 
                        UPDATE SET 
                            t.valor_metrica = s.valor_metrica, 
                            t.data_carga = GETDATE()
                    WHEN NOT MATCHED THEN 
                        INSERT (id_metrica, data_fechamento, periodo_codigo, valor_metrica, data_carga)
                        VALUES (s.id_metrica, s.data_fechamento, s.periodo_codigo, s.valor_metrica, GETDATE());
                """))
        logging.info("Upsert atômico concluído com sucesso no SQL Server.")

if __name__ == "__main__":
    DB_NAME = "dwmeliuz"
    params = urllib.parse.quote_plus(
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER=localhost;"
        f"DATABASE={DB_NAME};"
        f"Trusted_Connection=yes;"
        f"TrustServerCertificate=yes;"
    )
    conn_string = f"mssql+pyodbc:///?odbc_connect={params}"

    pipeline = MeliuzETLPipeline(data_folder="./data", db_type="sqlserver", conn_string=conn_string)
    arquivo = pipeline.get_latest_file()
    print(f"Lendo arquivo: {arquivo}")

    dim_c, fato_c = pipeline.parse_financial_statements(arquivo)
    dim_m, fato_m = pipeline.parse_operational_indicators(arquivo)

    pipeline.execute_upsert(dim_c, fato_c, dim_m, fato_m)
