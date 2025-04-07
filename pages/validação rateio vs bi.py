import streamlit as st
import pandas as pd
import sys
import os
import io
from datetime import datetime
import time
from streamlit.errors import NoSessionContext

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import process_report2, verificar_retorno
from app import (display_error_log)

# Dictionary to map benefit names between dataframes
benefit_mapping = {
    'VA': 'va',
    'UNIMED': 'unimed',
    'CLIN': 'clin',
    'SV': 'sv'
}

def validate_excel_file(file, file_type):
    """Validate uploaded Excel file and return preview if valid"""
    if file is None:
        return False, None, f"Arquivo {file_type} não foi carregado."
    
    try:
        # Check file size (limit to 50MB)
        if file.size > 50 * 1024 * 1024:
            return False, None, f"Arquivo {file_type} muito grande (>50MB)."
        
        # Preview first sheet of Excel file
        preview_df = pd.read_excel(file, sheet_name=0, nrows=5)
        file.seek(0)  # Reset file pointer after reading
        
        if preview_df.empty:
            return False, None, f"Arquivo {file_type} parece estar vazio."
            
        return True, preview_df, "Arquivo válido."
    except Exception as e:
        return False, None, f"Erro ao validar arquivo {file_type}: {str(e)}"

def process_data(beneficios_file, bi_file, ednaldo_mode, progress_callback):
    try:
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

def render_sidebar():
    st.header("Upload de Arquivos")
    
    # Arquivo de benefícios
    st.subheader("Carregar arquivo de benefícios")
    beneficios_help = "Arquivo Excel contendo planilhas com dados de benefícios"
    beneficios_file = st.file_uploader(
        type=["xlsx"],
        help=beneficios_help,
        label_visibility="collapsed",
        label="Carregar arquivo de beneficios",
        key="beneficios_uploader"
    )
    
    # Validação e preview do arquivo de benefícios
    if beneficios_file:
        is_valid, preview, message = validate_excel_file(beneficios_file, "de benefícios")
        if is_valid:
            st.success("✅ Arquivo de benefícios carregado com sucesso")

        else:
            st.error(message)
            beneficios_file = None
    
    # Arquivo de BI
    st.subheader("Carregar arquivo com o orçamento")
    bi_help = "Carregar arquivo com o detalhado BI"
    bi_file = st.file_uploader(
        label="Carregar arquivo com o detalhado BI",
        label_visibility="collapsed",
        type=["xlsx"],
        help=bi_help,
        key="bi_uploader"
    )
    
    # Validação e preview do arquivo de BI
    if bi_file:
        is_valid, preview, message = validate_excel_file(bi_file, "de BI")
        if is_valid:
            st.success("✅ Arquivo de BI carregado com sucesso")
        else:
            st.error(message)
            bi_file = None
    
    # Checkbox e botão de processamento
    ednaldo_mode = st.checkbox("Usar modo Ednaldo", value=False, 
                              help="Ativa o processamento com regras específicas do modo Ednaldo")
    
    # Adiciona dicas de uso
    if not beneficios_file or not bi_file:
        st.info("ℹ️ Carregue ambos os arquivos para habilitar o processamento")
    
    process_button = st.button(
        "Processar Dados", 
        type="primary", 
        use_container_width=True,
        disabled=(beneficios_file is None or bi_file is None)
    )
    
    return beneficios_file, bi_file, ednaldo_mode, process_button

def compare_data(result_df, result_bi):
    """Compare data between result_df and result_bi dataframes"""
    
    comparison_results = {}
    
    # Process comparison by filial (same as before)
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
    
    # Process comparison by center cost with improved handling
    for bi_benefit, df_benefit in benefit_mapping.items():
        # Get data from BI
        bi_by_cc = result_bi[result_bi['BENEFICIO'] == bi_benefit].groupby('CC')['VALOR'].sum().reset_index()
        bi_by_cc.rename(columns={'VALOR': f'valor_bi_{df_benefit}'}, inplace=True)
        
        # Get data from result_df
        df_col = f'realizado_{df_benefit}'
        cc_col = f'CC_realizado_{df_benefit}'
        df_by_cc = result_df.groupby(cc_col)[df_col].sum().reset_index()
        df_by_cc.rename(columns={cc_col: 'CC', df_col: f'valor_df_{df_benefit}'}, inplace=True)
        
        # Merge with outer join to include all CCs and handle missing values
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

def main():
    for key in ['processing_completed_time', 'processing_started', 'result_df', 'result_bi', 'is_error_log']:
        if key not in st.session_state:
            st.session_state[key] = None if key != 'processing_started' else False
    
    if st.session_state.processing_completed_time is not None:
        elapsed_time = time.time() - st.session_state.processing_completed_time
        if elapsed_time >= 5:
            st.session_state.processing_completed_time = None
            st.session_state.processing_started = False

    st.title("Validação Rateio vs BI")
    st.markdown("""
    Carregue os arquivos necessários e configure as opções para gerar o relatório final.
    """)
    
    # Sidebar for file upload and configuration
    with st.sidebar:
        beneficios_file, bi_file, ednaldo_mode, process_button = render_sidebar()
    
    result_df = st.session_state.result_df
    result_bi = st.session_state.result_bi
    is_error_log = st.session_state.is_error_log
    
    # UI elements for progress
    progress_container = st.empty()
    status_container = st.empty()
    success_container = st.empty()
    
    # Process data when button is clicked
    if process_button:
        if beneficios_file is None or bi_file is None:
            st.error("Por favor, carregue os dois arquivos necessários.")
        else:
            try:
                st.session_state.result_df = None
                st.session_state.result_bi = None
                st.session_state.is_error_log = None
                st.session_state.processing_started = True
                
                with st.spinner("Processando dados..."):
                    progress_bar = progress_container.progress(0)
                    status_text = status_container.empty()
                    
                    def update_progress(progress, message=""):
                        try:
                            progress_bar.progress(progress/100)
                            if message:
                                status_text.text(message)
                        except NoSessionContext:
                            pass
                    
                    result, result_bi, is_error_log = process_data(
                        beneficios_file, 
                        bi_file,
                        ednaldo_mode, 
                        update_progress
                    )
                
                st.session_state.result_df = result
                st.session_state.result_bi = result_bi
                st.session_state.is_error_log = is_error_log
                st.session_state.processing_completed_time = time.time()
                if not is_error_log:
                    success_container.success(f"Processamento concluído! {len(result)} registros processados.")
                st.rerun()
                
            except Exception as e:
                progress_container.empty()
                status_container.empty()
                success_container.empty()
                st.session_state.processing_started = False
                st.session_state.processing_completed_time = None
                st.error(f"Erro durante o processamento: {str(e)}")
                st.exception(e) 
    
    # Clear progress elements after processing
    if (st.session_state.processing_completed_time is not None and 
        time.time() - st.session_state.processing_completed_time >= 5):
        progress_container.empty()
        status_container.empty()
        success_container.empty()
    
    # Display results or error log if available
    if result_df is not None:
        if is_error_log:
            # Display error log in a user-friendly way
            display_error_log(result_df)
        else:
            # Display the regular report
            st.header("Resultados")

            # Compare data and display comparison results
            st.header("Comparação entre Rateio e BI")
            
            comparison_results = compare_data(result_df, result_bi)
            
            # Display comparison by benefit type
            benefit_names = {"VA": "Vale Alimentação", "UNIMED": "Unimed", "CLIN": "Clínica", "SV": "Seguro de Vida"}
            
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

if __name__ == "__main__":
    main()
