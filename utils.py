import pandas as pd
from streamlit.errors import NoSessionContext

# Dictionary to map benefit names between dataframes
benefit_mapping = {
    'VA': 'va',
    'UNIMED': 'unimed',
    'CLIN': 'clin',
    'SV': 'sv'
}

benefit_names = {
    "VA": "Vale Alimentação", 
    "UNIMED": "Unimed", 
    "CLIN": "Clínica", 
    "SV": "Seguro de Vida"
}

def process_data(beneficios_file, bi_file, ednaldo_mode, progress_callback):
    try:
        from main import process_report2
        result, result_bi = process_report2(
            beneficios_file,
            bi_file,
            ednaldo=ednaldo_mode,
            progress_callback=progress_callback
        )
        
        # Check if the result is a dictionary (error log) instead of a DataFrame
        is_error_log = isinstance(result, dict)
        
        return result, result_bi, is_error_log
    
    except Exception as e:
        raise e

def compare_data(result_df, result_bi):
    """Compare data between result_df and result_bi dataframes"""
    
    comparison_results = {}
    
    # Process comparison by filial
    for bi_benefit, df_benefit in benefit_mapping.items():
        bi_by_filial = result_bi[result_bi['BENEFICIO'] == bi_benefit].groupby('FILIAL')['VALOR'].sum().reset_index()
        bi_by_filial.rename(columns={'VALOR': f'valor_bi_{df_benefit}'}, inplace=True)
        
        df_col = f'realizado_{df_benefit}'
        filial_col = f'filial_realizada_{df_benefit}'
        df_by_filial = result_df.groupby(filial_col)[df_col].sum().reset_index()
        df_by_filial.rename(columns={filial_col: 'FILIAL', df_col: f'valor_df_{df_benefit}'}, inplace=True)
        
        filial_comparison = pd.merge(bi_by_filial, df_by_filial, on='FILIAL', how='outer').fillna(0)
        
        filial_comparison[f'diferença_{df_benefit}'] = filial_comparison[f'valor_bi_{df_benefit}'] - filial_comparison[f'valor_df_{df_benefit}']

        comparison_results[f'{bi_benefit}_por_filial'] = filial_comparison
    
    # Process comparison by center cost
    for bi_benefit, df_benefit in benefit_mapping.items():
        # Get data from BI
        bi_by_cc = result_bi[result_bi['BENEFICIO'] == bi_benefit].groupby('CC')['VALOR'].sum().reset_index()
        bi_by_cc.rename(columns={'VALOR': f'valor_bi_{df_benefit}'}, inplace=True)
        
        # Get data from result_df
        df_col = f'realizado_{df_benefit}'
        cc_col = f'CC_realizado_{df_benefit}'
        df_by_cc = result_df.groupby(cc_col)[df_col].sum().reset_index()
        df_by_cc.rename(columns={cc_col: 'CC', df_col: f'valor_df_{df_benefit}'}, inplace=True)
        
        # Merge with outer join to include all CCs
        cc_comparison = pd.merge(bi_by_cc, df_by_cc, on='CC', how='outer').fillna(0)
        
        cc_comparison[f'(bi-realizado)_{df_benefit} '] = cc_comparison[f'valor_bi_{df_benefit}'] - cc_comparison[f'valor_df_{df_benefit}']
        
        comparison_results[f'{bi_benefit}_por_cc'] = cc_comparison
    
    return comparison_results

def format_currency_dataframe(df, currency_columns=None):
    """
    Format specified columns in a dataframe as Brazilian currency (R$)
    Returns a copy of the dataframe with formatted columns
    """
    formatted_df = df.copy()
    
    if currency_columns is None:
        # Automatically find columns that should be currency
        currency_columns = [col for col in df.columns if 
                           any(prefix in col for prefix in ['valor_bi_', 'valor_df_', 'diferença_', '(bi-realizado)_'])]
    
    for col in currency_columns:
        if col in formatted_df.columns:
            formatted_df[col] = formatted_df[col].apply(
                lambda x: f"R$ {x:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
            )
    
    return formatted_df

def display_comparison_panel(result_df, result_bi):
    """Display the comparison panel between rateio and BI data"""
    import streamlit as st
    
    # Compare data and display comparison results
    st.header("Comparação entre Rateio e BI")
    
    comparison_results = compare_data(result_df, result_bi)
    
    # Dropdown para selecionar o benefício
    selected_benefit = st.selectbox(
        "Selecione o benefício",
        options=list(benefit_names.keys()),
        format_func=lambda x: benefit_names[x]
    )
    
    # Mostrar o dataframe por filial quando um benefício for selecionado
    st.subheader(f"Comparação por Filial - {benefit_names[selected_benefit]}")
    filial_df = comparison_results[f"{selected_benefit}_por_filial"]
    formatted_filial_df = format_currency_dataframe(filial_df)
    st.dataframe(formatted_filial_df, use_container_width=True)
    
    # Expander para selecionar a filial
    with st.expander("Selecionar Filial para ver Centro de Custos"):
        # Obter lista de filiais do benefício selecionado
        filiais = comparison_results[f"{selected_benefit}_por_filial"]["FILIAL"].unique().tolist()
        
        # Dropdown para selecionar a filial
        selected_filial = st.selectbox("Selecione a Filial", options=filiais)
        
        cc_comparison = comparison_results[f"{selected_benefit}_por_cc"]
        
        bi_filial_ccs = result_bi[
            (result_bi['BENEFICIO'] == selected_benefit) & 
            (result_bi['FILIAL'] == selected_filial)
        ]['CC'].dropna().unique().tolist()
        
        df_benefit = benefit_mapping[selected_benefit]
        filial_col = f'filial_realizada_{df_benefit}'
        cc_col = f'CC_realizado_{df_benefit}'
        
        df_filial_ccs = []
        if filial_col in result_df.columns and cc_col in result_df.columns:
            df_filial_ccs = result_df[
                (result_df[filial_col] == selected_filial) & 
                (result_df[cc_col].notna())
            ][cc_col].unique().tolist()
        
        all_filial_ccs = list(set(bi_filial_ccs + df_filial_ccs))
        
        filial_cc_comparison = cc_comparison[cc_comparison['CC'].isin(all_filial_ccs)]
        
        if not filial_cc_comparison.empty:
            st.subheader(f"Centros de Custo de {selected_filial} - {benefit_names[selected_benefit]}")
            formatted_cc_df = format_currency_dataframe(filial_cc_comparison)
            st.dataframe(formatted_cc_df, use_container_width=True)
        else:
            st.info(f"Não há centros de custo para a filial {selected_filial} no benefício {benefit_names[selected_benefit]}")
