import streamlit as st
import pandas as pd

def calculate_totals(result_df):
    benefit_types = {
        'Vale Alimentação': ('previsto_va', 'realizado_va'),
        'Assistência Médica': ('previsto_unimed', 'realizado_unimed'),
        'Assistência Odontológica': ('previsto_clin', 'realizado_clin'),
        'Seguro de Vida': ('previsto_sv', 'realizado_sv')
    }
    
    totais = {}
    prev_cols = []
    real_cols = []
    
    for benefit, (prev_col, real_col) in benefit_types.items():
        prev_cols.append(prev_col)
        real_cols.append(real_col)
        
        prev_sum = result_df[prev_col].sum()
        real_sum = result_df[real_col].sum()
        
        totais[benefit] = {
            'Previsto': prev_sum,
            'Realizado': real_sum,
            'Diferença': real_sum - prev_sum
        }
    totais['Total Geral'] = {
        'Previsto': result_df[prev_cols].sum().sum(),
        'Realizado': result_df[real_cols].sum().sum(),
        'Diferença': result_df[real_cols].sum().sum() - result_df[prev_cols].sum().sum()
    }
    
    return totais

def process_filial_comparativo(result_df, result_bi=None, selected_benefit=None):
    df = result_df.copy()
    df.loc[:, 'previsto_filial'] = df['previsto_filial'].fillna('00')

    benefit_mapping = {
        "Vale Alimentação": ('va', 'previsto_va', 'realizado_va', 'filial_realizada_va', 'VA'),
        "Assistência Médica": ('unimed', 'previsto_unimed', 'realizado_unimed', 'filial_realizada_unimed', 'UNIMED'),
        "Assistência Odontológica": ('clin', 'previsto_clin', 'realizado_clin', 'filial_realizada_clin', 'CLIN'),
        "Seguro de Vida": ('sv', 'previsto_sv', 'realizado_sv', 'filial_realizada_sv', 'SV')
    }

    # Get the columns for the selected benefit
    benefit_type, prev_col, real_col, filial_real_col, bi_benefit_name = benefit_mapping[selected_benefit]

    comparativo_filiais = []

    # Get all unique filiais to analyze from previsto in result_df
    all_filiais = set(df['previsto_filial'].unique())
    
    # Also add filiais from filial_realizada in result_df
    all_filiais.update(df[filial_real_col].unique())
    
    # Add filiais from result_bi if available
    if result_bi is not None:
        filtered_bi = result_bi[result_bi['BENEFICIO'] == bi_benefit_name]
        all_filiais.update(filtered_bi['FILIAL'].unique())
    
    all_filiais = sorted(list(all_filiais))

    for filial in all_filiais:
        # Sum previsto values where previsto_filial matches the current filial
        filial_previsto_df = df[df['previsto_filial'] == filial]
        previsto_sum = filial_previsto_df[prev_col].sum()
        
        # Count collaborators with budget in this filial for this benefit
        # Filter where previsto value is not 0 or None
        previsto_count = filial_previsto_df[filial_previsto_df[prev_col] > 0].shape[0]
        
        # Get realized values from BI if available, otherwise use result_df's realizado values
        if result_bi is not None:
            realizado_sum = result_bi[(result_bi['FILIAL'] == filial) & 
                                     (result_bi['BENEFICIO'] == bi_benefit_name)]['VALOR'].sum()
        else:
            # Fallback to the original calculation if BI data isn't available
            filial_realizado_df = df[df[filial_real_col] == filial]
            realizado_sum = filial_realizado_df[real_col].sum()
        
        # Count collaborators with realized benefits in this filial
        filial_realizado_df = df[df[filial_real_col] == filial]
        realizado_count = filial_realizado_df[filial_realizado_df[real_col] > 0].shape[0]
        
        # Calculate difference and percentage
        diferenca = realizado_sum - previsto_sum
        variacao_pct = (realizado_sum / previsto_sum * 100) if previsto_sum != 0 else 0
        
        comparativo_filiais.append({
            'Filial': filial,
            'Orçado': previsto_sum,
            'Qtd. Orçado': previsto_count,
            'Realizado': realizado_sum,
            'Qtd. Realizado': realizado_count,
            'Variação (%)': variacao_pct,
            'Diferença': diferenca,
            'Justificativa': None
        })

    return pd.DataFrame(comparativo_filiais).sort_values(by='Filial')

def process_matriz_transferencia(result_df, beneficio):
    benefit_map = {
        "Vale Alimentação": ("previsto_va", "filial_realizada_va", "realizado_va"),
        "Assistência Médica": ("previsto_unimed", "filial_realizada_unimed", "realizado_unimed"),
        "Assistência Odontológica": ("previsto_clin", "filial_realizada_clin", "realizado_clin"),
        "Seguro de Vida": ("previsto_sv", "filial_realizada_sv", "realizado_sv")
    }
    
    previsto_col, frealizado_col, realizado_col = benefit_map[beneficio]
    
    df_valido = result_df.dropna(subset=['previsto_filial', frealizado_col]).copy()
    df_valido.loc[:, 'previsto_filial'] = df_valido['previsto_filial'].astype(str)
    df_valido.loc[:, frealizado_col] = df_valido[frealizado_col].astype(str)
    
    matriz_pivot = pd.pivot_table(
        df_valido,
        values=realizado_col,
        index='previsto_filial',
        columns=frealizado_col,
        aggfunc='sum',
        fill_value=0
    )
    
    matriz_pivot['Total Orçado'] = matriz_pivot.sum(axis=1)
    matriz_pivot.loc['Total Realizado'] = matriz_pivot.sum(axis=0)
    
    return matriz_pivot, df_valido, previsto_col, frealizado_col, realizado_col

def load_colaboradores_file(file):
    try:
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        df.columns = [col.upper() for col in df.columns]
        
        if 'CPF' in df.columns and 'NOME' in df.columns:
            # Proper way to handle CPF conversion to avoid dtype warning
            df['CPF'] = df['CPF'].astype(str)
            df['CPF'] = df['CPF'].str.replace('[^0-9]', '', regex=True).str.zfill(11)
            
            st.sidebar.success(f"Arquivo de colaboradores carregado com sucesso: {len(df)} registros.")
            return df
        else:
            required_cols = ['CPF', 'NOME']
            missing = [col for col in required_cols if col not in df.columns]
            st.sidebar.error(f"Colunas obrigatórias ausentes no arquivo de colaboradores: {', '.join(missing)}")
            return None
    except Exception as e:
        st.sidebar.error(f"Erro ao carregar arquivo de colaboradores: {str(e)}")
        return None
