import pandas as pd
import unicodedata
import re
import argparse
from datetime import datetime
import io
import os
import threading
import time

def clean_acentuacao(text):
    text = unicodedata.normalize('NFKD', str(text))
    text = ''.join([c for c in text if not unicodedata.combining(c)])
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', '', text)
    return text

def load_excel(file_path):
    if isinstance(file_path, str):
        excel_file = pd.ExcelFile(file_path)
    else:
        excel_file = pd.ExcelFile(file_path)
        
    worksheet_names = excel_file.sheet_names  
    
    dataframes = {}
    for sheet_name in worksheet_names:
        dataframes[sheet_name] = pd.read_excel(excel_file, sheet_name=sheet_name, dtype=str)
    
    for sheet_name, df in dataframes.items():
        column_mapping = {col: clean_acentuacao(col.upper()) for col in df.columns}
        dataframes[sheet_name] = df.rename(columns=column_mapping)

    processed_dataframes = {}
    for sheet_name, df in dataframes.items():
        new_sheet_name = clean_acentuacao(sheet_name.upper())
        processed_dataframes[new_sheet_name] = df

    return processed_dataframes

def check_columns(df, search_terms):
    matching_columns = []
    for col in df.columns:
        for term in search_terms:
            if col == term or term in col:
                matching_columns.append(col)
                break
    return matching_columns

def analyze_dataframes(dataframes):
    search_terms = ['424', 'CPF', 'FILIAL', 'VALOR', 'TITULAR',
                   '441', '442', 'PARENTESCO', 'TIPO', '406', 'SINTRACAP']
    
    results = {}
    for name, df in dataframes.items():
        matched_cols = check_columns(df, search_terms)
        if matched_cols:
            results[name] = matched_cols
    
    return results

def extract_unique_cpfs(dataframes):
    all_cpfs = []
    cpf_terms = ['CPFTITULAR']
    
    for name, df in dataframes.items():
        cpf_columns = []
        for col in df.columns:
            if any(term in col for term in cpf_terms):
                cpf_columns.append(col)
        
        for col in cpf_columns:
            cpfs = df[col].apply(lambda x: clean_acentuacao(str(x)) if pd.notna(x) else None)
            valid_cpfs = [cpf for cpf in cpfs.dropna().tolist() if cpf and len(cpf) >= 11]
            all_cpfs.extend(valid_cpfs)

    unique_cpfs = list(set(all_cpfs))
    return unique_cpfs

def process_dataframe(df, is_sv2=False):
    processed_df = df.copy()
    
    def convert_to_float(value):
        if pd.isna(value) or value == '':
            return 0.0
        try:
            return float(value)
        except ValueError:
            try:
                return float(str(value).replace(',', '.'))
            except:
                return None
    
    if is_sv2:
        if 'SINTRACAP' in processed_df.columns:
            processed_df['SINTRACAP'] = processed_df['SINTRACAP'].apply(convert_to_float)
        return processed_df
    
    if 'VALOR' not in processed_df.columns:
        return processed_df
    
    valor_index = list(processed_df.columns).index('VALOR')
    numeric_columns = list(processed_df.columns)[valor_index:]
    
    for col in numeric_columns:
        processed_df[col] = processed_df[col].apply(convert_to_float)

    processed_df['FINAL'] = processed_df['VALOR']
    for col in numeric_columns[1:]:
        processed_df['FINAL'] = processed_df['FINAL'] - processed_df[col]
    
    return processed_df

def process_full(dataframes, ednaldo=False):
    if ednaldo:
        unimed = dataframes.get('UNIMED')
        va = dataframes.get('VA')
        clin = dataframes.get('CLIN')
        sv = dataframes.get('SURA')
        sv2 = dataframes.get('BEMMAIS')
        unimed = process_dataframe(unimed)
        va = process_dataframe(va)
        clin = process_dataframe(clin)
        sv = process_dataframe(sv)
        sv2 = process_dataframe(sv2, is_sv2=True)
        return unimed, va, clin, sv, sv2
    else:
        unimed = dataframes.get('UNIMED')
        va = dataframes.get('VA')
        clin = dataframes.get('CLIN')
        sv = dataframes.get('SV')
        unimed = process_dataframe(unimed)
        va = process_dataframe(va)
        clin = process_dataframe(clin)
        sv = process_dataframe(sv)
        return unimed, va, clin, sv

def load_recorrentes(recorrentes_file, mes_analise):
    recorrente = pd.read_excel(recorrentes_file, dtype=str)
    recorrente['CPF'] = recorrente['CPF'].fillna('').str.replace('.', '').str.replace('-', '').str.zfill(11)
            
    atual_ano = datetime.now().strftime('%Y')
    anomes = f"{atual_ano}{mes_analise}"
    recorrente = recorrente[recorrente['ANOMES'] == anomes]
    return recorrente, list(set(recorrente['CPF']))

def merge_dataframes(consolidated_df, unimed, va, clin, sv, sv2=None, ednaldo=False):
    if ednaldo:
        if consolidated_df is not None and 'CPFTITULAR' not in consolidated_df.columns:
            print("ERRO: CPFTITULAR não existe no consolidated_df")
            print("Colunas disponíveis:", consolidated_df.columns.tolist())

        if unimed is not None and 'CPFTITULAR' in unimed.columns:
            unimed['CPFBENEFICIARIO'] = unimed['CPFBENEFICIARIO'].apply(lambda x: clean_acentuacao(str(x)) if pd.notna(x) else None)
        if va is not None and 'CPFTITULAR' in va.columns:
            va['CPFTITULAR'] = va['CPFTITULAR'].apply(lambda x: clean_acentuacao(str(x)) if pd.notna(x) else None)
        if clin is not None and 'CPFTITULAR' in clin.columns:
            clin['CPFDOBENEFICIARIO'] = clin['CPFDOBENEFICIARIO'].apply(lambda x: clean_acentuacao(str(x)) if pd.notna(x) else None)
        if sv is not None and 'CPFTITULAR' in sv.columns:
            sv['CPFTITULAR'] = sv['CPFTITULAR'].apply(lambda x: clean_acentuacao(str(x)) if pd.notna(x) else None)
        if sv2 is not None and 'CPFTITULAR' in sv2.columns:
            sv2['CPFTITULAR'] = sv2['CPFTITULAR'].apply(lambda x: clean_acentuacao(str(x)) if pd.notna(x) else None)

        unimed_merge = pd.DataFrame()
        va_merge = pd.DataFrame()
        clin_merge = pd.DataFrame()
        sv_merge = pd.DataFrame()
        sv2_merge = pd.DataFrame()

        if unimed is not None and 'CPFBENEFICIARIO' in unimed.columns and 'FINAL' in unimed.columns:
            unimed_merge = unimed[['CPFBENEFICIARIO', 'FINAL', 'FILIAL']].rename(columns={'FINAL': 'realizado_unimed',
                                                                                            'FILIAL': 'frealizado_un'})
        if va is not None and 'CPFTITULAR' in va.columns and 'FINAL' in va.columns:
            va_merge = va[['CPFTITULAR', 'FINAL', 'FILIAL']].rename(columns={'FINAL': 'realizado_va',
                                                                                'FILIAL': 'frealizado_va'})
        if clin is not None and 'CPFDOBENEFICIARIO' in clin.columns and 'FINAL' in clin.columns:
            clin_merge = clin[['CPFDOBENEFICIARIO', 'FINAL', 'FILIAL']].rename(columns={'FINAL': 'realizado_clin',
                                                                                        'FILIAL': 'frealizado_cl'})
        if sv is not None and 'CPFTITULAR' in sv.columns and 'VALOR' in sv.columns:
            sv_merge = sv[['CPFTITULAR', 'VALOR', 'FILIAL']].rename(columns={'VALOR': 'VALOR_sv',
                                                                                'FILIAL': 'frealizado_sv'})
        if sv2 is not None and 'CPFTITULAR' in sv2.columns and 'SINTRACAP' in sv2.columns:
            sv2_merge = sv2[['CPFTITULAR', 'SINTRACAP', 'FILIAL']]

        result_df = consolidated_df.copy()

        if not unimed_merge.empty:
            result_df = result_df.merge(unimed_merge,  left_on= 'CPFTITULAR', right_on='CPFBENEFICIARIO', how='left')
        if not va_merge.empty:
            result_df = result_df.merge(va_merge, on='CPFTITULAR', how='left')
        if not clin_merge.empty:
            result_df = result_df.merge(clin_merge, left_on= 'CPFTITULAR', right_on='CPFDOBENEFICIARIO', how='left')
        if not sv_merge.empty:
            result_df = result_df.merge(sv_merge, on='CPFTITULAR', how='left')
        if not sv2_merge.empty:
            result_df = result_df.merge(sv2_merge, on='CPFTITULAR', how='left')

        result_df['SEGURO_VIDA'] = result_df['SINTRACAP']
        result_df['realizado_sv'] = result_df.apply(
            lambda row: row['VALOR_sv'] if (pd.isna(row['SINTRACAP']) or row['SINTRACAP'] == 0) and pd.notna(row['VALOR_sv']) else row['SEGURO_VIDA'], 
            axis=1
        )

        result_df.drop(columns=['SINTRACAP', 'SEGURO_VIDA', 'VALOR_sv', 'CPFBENEFICIARIO', 'CPFDOBENEFICIARIO', 'FILIAL'], inplace=True)

    else:
        if consolidated_df is not None and 'CPFTITULAR' not in consolidated_df.columns:
            print("ERRO: CPFTITULAR não existe no consolidated_df")
            print("Colunas disponíveis:", consolidated_df.columns.tolist())

        if unimed is not None and 'CPFTITULAR' in unimed.columns:
            unimed['CPFDOBENEFICIARIO'] = unimed['CPFDOBENEFICIARIO'].apply(lambda x: clean_acentuacao(str(x)) if pd.notna(x) else None)
        if va is not None and 'CPFTITULAR' in va.columns:
            va['CPFTITULAR'] = va['CPFTITULAR'].apply(lambda x: clean_acentuacao(str(x)) if pd.notna(x) else None)
        if clin is not None and 'CPFTITULAR' in clin.columns:
            clin['CPFDOBENEFICIARIO'] = clin['CPFDOBENEFICIARIO'].apply(lambda x: clean_acentuacao(str(x)) if pd.notna(x) else None)
        if sv is not None and 'CPFTITULAR' in sv.columns:
            sv['CPFTITULAR'] = sv['CPFTITULAR'].apply(lambda x: clean_acentuacao(str(x)) if pd.notna(x) else None)

        unimed_merge = pd.DataFrame()
        va_merge = pd.DataFrame()
        clin_merge = pd.DataFrame()
        sv_merge = pd.DataFrame()

        if unimed is not None and 'CPFDOBENEFICIARIO' in unimed.columns and 'FINAL' in unimed.columns:
            unimed_merge = unimed[['CPFDOBENEFICIARIO', 'FINAL', 'FILIAL']].rename(columns={'FINAL': 'realizado_unimed',
                                                                                            'FILIAL': 'frealizado_un'})
        if va is not None and 'CPFTITULAR' in va.columns and 'FINAL' in va.columns:
            va_merge = va[['CPFTITULAR', 'FINAL', 'FILIAL']].rename(columns={'FINAL': 'realizado_va',
                                                                                'FILIAL': 'frealizado_va'})
        if clin is not None and 'CPFDOBENEFICIARIO' in clin.columns and 'FINAL' in clin.columns:
            clin_merge = clin[['CPFDOBENEFICIARIO', 'FINAL', 'FILIAL']].rename(columns={'FINAL': 'realizado_clin',
                                                                                        'FILIAL': 'frealizado_cl'})
        if sv is not None and 'CPFTITULAR' in sv.columns and 'VALOR' in sv.columns:
            sv_merge = sv[['CPFTITULAR', 'VALOR', 'FILIAL']].rename(columns={'VALOR': 'realizado_sv',
                                                                                'FILIAL': 'frealizado_sv'})

        result_df = consolidated_df.copy()

        if not unimed_merge.empty:
            result_df = result_df.merge(unimed_merge,  left_on= 'CPFTITULAR', right_on='CPFDOBENEFICIARIO', how='left')
        if not va_merge.empty:
            result_df = result_df.merge(va_merge, on='CPFTITULAR', how='left')
        if not clin_merge.empty:
            result_df = result_df.merge(clin_merge, left_on= 'CPFTITULAR', right_on='CPFDOBENEFICIARIO', how='left')
        if not sv_merge.empty:
            result_df = result_df.merge(sv_merge, on='CPFTITULAR', how='left')

        result_df = result_df.drop_duplicates(subset=['CPFTITULAR'], keep='first')
        result_df.drop(columns=['CPFDOBENEFICIARIO_x', 'CPFDOBENEFICIARIO_y'], inplace=True)
        
        result_df.reset_index(drop=True, inplace=True)
    
    return result_df

def merge_benefits(result_df, recorrente):
    benefit_columns = ['CPF', 'VALE ALIMENTACAO', 'ASSISTENCIA MEDICA', 
                       'SEGURO DE VIDA', 'ASSISTENCIA ODONTOLOGICA', 'FILIAL']
    
    columns_to_use = [col for col in benefit_columns if col in recorrente.columns]
    
    recorrente_subset = recorrente[columns_to_use]
    
    merged_df = result_df.merge(
        recorrente_subset,
        left_on='CPFTITULAR',
        right_on='CPF',
        how='left'
    )
    
    merged_df.drop(columns=['CPF'], inplace=True)
    
    merged_df.rename(columns={
        'VALE ALIMENTACAO': 'previsto_va',
        'ASSISTENCIA MEDICA': 'previsto_unimed',
        'SEGURO DE VIDA': 'previsto_sv',
        'ASSISTENCIA ODONTOLOGICA': 'previsto_clin',
        'FILIAL': 'previsto_filial'
    }, inplace=True)

    merged_df = merged_df[['CPFTITULAR', 'previsto_filial', 'previsto_va', 'frealizado_va', 'realizado_va' ,
                          'previsto_unimed', 'frealizado_un', 'realizado_unimed', 
                          'previsto_clin', 'frealizado_cl', 'realizado_clin', 
                          'previsto_sv', 'frealizado_sv', 'realizado_sv']]
    
    benefit_columns = ['previsto_va', 'previsto_unimed', 'previsto_clin', 'previsto_sv']
    for col in benefit_columns:
        if col in merged_df.columns:
            merged_df[col] = merged_df[col].apply(
                lambda x: float(str(x).replace(',', '.')) if pd.notna(x) and x != '' else 0.0
            )
    
    filial_columns = ['previsto_filial', 'frealizado_va', 'frealizado_un', 'frealizado_cl', 'frealizado_sv']
    for col in filial_columns:
        if col in merged_df.columns:
            merged_df[col] = merged_df[col].apply(
                lambda x: str(x).split(' ')[0].split('-')[0].strip() if pd.notna(x) and x != '' else '0'
            )
            merged_df[col] = merged_df[col].apply(
                lambda x: str(x).zfill(2) if pd.notna(x) else None
            )

    return merged_df

def process_report(beneficios_file, recorrentes_file, ednaldo=False, output_path=None, 
                  mes_analise=None, progress_callback=None):
    def update_progress(progress, message=""):
        if progress_callback:
            progress_callback(progress, message)
    
    update_progress(0, "Carregando arquivos...")
    
    dataframes = load_excel(beneficios_file)
    
    update_progress(20, "Arquivos carregados com sucesso")
    
    columns_to_keep = analyze_dataframes(dataframes)
    for name, columns in columns_to_keep.items():
        if name in dataframes:
            try:
                dataframes[name] = dataframes[name][columns]
            except KeyError as e:
                error_msg = f"Erro ao filtrar colunas para {name}: {e}"
                print(error_msg)
                update_progress(0, error_msg)
    
    update_progress(40, "Colunas relevantes extraídas")
    
    cpfs_unicos = extract_unique_cpfs(dataframes)
    
    recorrente_df, recorrentes_cpfs = load_recorrentes(recorrentes_file, mes_analise)
    
    update_progress(60, "CPFs extraídos e processados")
    
    if ednaldo:
        unimed, va, clin, sv, sv2 = process_full(dataframes, ednaldo=ednaldo)
    else:
        unimed, va, clin, sv = process_full(dataframes, ednaldo=ednaldo)
        sv2 = None
    
    consolidated_df = pd.DataFrame(list(set(recorrentes_cpfs + cpfs_unicos)), columns=['CPFTITULAR'])
    
    update_progress(80, "Dados processados, gerando relatório final")
    
    result_df = merge_dataframes(consolidated_df, unimed, va, clin, sv, sv2, ednaldo)
    result_df = merge_benefits(result_df, recorrente_df)
    
    if output_path:
        result_df.to_excel(output_path, index=False)
        print(f"Relatório salvo em: {output_path}")
    
    update_progress(100, "Relatório finalizado")
    
    return result_df
