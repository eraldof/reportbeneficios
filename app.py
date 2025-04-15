import streamlit as st
import pandas as pd
from datetime import datetime
import io
import time
from streamlit.errors import NoSessionContext
import tabulate
from main import process_report, process_report2

from posprocessing import (calculate_totals, process_matriz_transferencia, 
                            process_filial_comparativo)

from utils import (format_currency, highlight_diff, highlight_percent, 
                   highlight_transfers, display_comparison_panel, 
                   create_styled_dataframe)

from shared_components import render_shared_sidebar


st.set_page_config(
    page_title="Processador de Relatórios de Benefícios",
    page_icon="📊",
    layout="centered"
)

def render_benefit_summary(result_df):
    st.subheader("Resumo dos Benefícios")
    
    # Criar uma cópia para evitar warnings
    df = result_df.copy()
    
    numeric_columns = [
        'previsto_va', 'realizado_va', 'previsto_unimed', 'realizado_unimed', 
        'previsto_clin', 'realizado_clin', 'previsto_sv', 'realizado_sv'
    ]
    
    for col in numeric_columns:
        df.loc[:, col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    totais = calculate_totals(df)
    
    totais_df = pd.DataFrame(totais).T
    totais_df['% Variação'] = (totais_df['Diferença'] / totais_df['Previsto'] * 100).fillna(0)
    
    format_dict = {
        'Previsto': format_currency, 
        'Realizado': format_currency, 
        'Diferença': format_currency,
        '% Variação': '{:.2f}%'.format
    }
    
    highlight_map = {
        'Diferença': highlight_diff,
        '% Variação': highlight_percent
    }
    
    styled_df = create_styled_dataframe(totais_df, format_dict, highlight_map)
    
    st.write("Resumo por tipo de benefício:")
    st.dataframe(styled_df, use_container_width=True, height=240)

def render_transfer_matrix(result_df, beneficio):
    matriz_pivot, df_valido, previsto_col, frealizado_col, realizado_col = process_matriz_transferencia(
        result_df, beneficio
    )
    
    styled_matriz = create_styled_dataframe(
        matriz_pivot, 
        {col: format_currency for col in matriz_pivot.columns},
        {None: highlight_transfers}
    )
    
    st.write(f"Matriz de transferências - {beneficio}")
    st.write("Linhas: Filial onde foi orçado | Colunas: Filial onde foi realizado")
    st.dataframe(styled_matriz, use_container_width=True)
    
    st.write("Interpretação: 00 são pessoas que não foram orçadas ou não foram realizadas.")
    
    return df_valido, previsto_col, frealizado_col, realizado_col

def render_cpf_detail(df_valido, filial_origem, filial_destino, previsto_col, frealizado_col, realizado_col):
    if filial_origem == filial_destino:
        st.info("Selecione filiais diferentes para visualizar as transferências.")
        return
    
    cpfs_transferidos = df_valido[
        (df_valido['previsto_filial'] == filial_origem) & 
        (df_valido[frealizado_col] == filial_destino)
    ]
    
    if cpfs_transferidos.empty:
        st.info(f"Não foram encontrados CPFs orçados em {filial_origem} e realizados em {filial_destino}.")
        return
    
    cpf_col = next((col for col in ['CPF', 'CPFTITULAR'] if col in cpfs_transferidos.columns), None)
    
    if not cpf_col:
        st.warning("Dados de CPF não disponíveis no relatório. Verifique se existe uma coluna 'CPF' ou 'CPFTITULAR'.")
        return
    
    if 'NOME' in cpfs_transferidos.columns:
        colunas_display = [cpf_col, 'NOME', previsto_col, realizado_col]
        colunas_rename = {
            cpf_col: 'CPF',
            'NOME': 'Nome Colaborador',
            previsto_col: 'Valor Orçado',
            realizado_col: 'Valor Realizado'
        }
    else:
        colunas_display = [cpf_col, previsto_col, realizado_col]
        colunas_rename = {
            cpf_col: 'CPF',
            previsto_col: 'Valor Orçado',
            realizado_col: 'Valor Realizado'
        }
    
    display_df = cpfs_transferidos[colunas_display].copy()
    display_df = display_df.rename(columns=colunas_rename)
    
    display_df['Valor Orçado'] = display_df['Valor Orçado'].apply(format_currency)
    display_df['Valor Realizado'] = display_df['Valor Realizado'].apply(format_currency)
    
    st.write(f"CPFs orçados em **{filial_origem}** e realizados em **{filial_destino}**:")
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    total_orcado = cpfs_transferidos[previsto_col].sum()
    total_realizado = cpfs_transferidos[realizado_col].sum()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Orçado", format_currency(total_orcado))
    with col2:
        st.metric("Total Realizado", format_currency(total_realizado))

def render_benefit_details(result_df, benefit_name, prev_col, real_col, filial_col):
    if filial_col not in result_df.columns:
        return
        
    st.subheader(f"Detalhamento - {benefit_name}")
    
    # Criar uma cópia para evitar warnings
    df = result_df.copy()
    df.loc[:, filial_col] = df[filial_col].fillna('00')
    df.loc[:, 'previsto_filial'] = df['previsto_filial'].fillna('00')
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("Por filial onde foi Orçado:")
        prev_group = df.groupby('previsto_filial')[prev_col].sum().reset_index()
        prev_group = prev_group.rename(columns={
            'previsto_filial': 'Filial',
            prev_col: 'Valor Orçado'
        })
        prev_group = prev_group.sort_values(by='Filial')
        
        prev_group['Valor Orçado'] = prev_group['Valor Orçado'].apply(format_currency)
        st.dataframe(prev_group, use_container_width=True, hide_index=True)
    
    with col2:
        st.write("Por filial onde foi Realizado:")
        all_filials = df['previsto_filial'].dropna().unique()

        real_group = df.groupby(filial_col)[real_col].sum().reset_index()
        real_group = real_group.rename(columns={
            filial_col: 'Filial',
            real_col: 'Valor Realizado'
        })

        if len(all_filials) > 0:
            default_df = pd.DataFrame({'Filial': all_filials})
            real_group = pd.merge(default_df, real_group, on='Filial', how='left')
            real_group['Valor Realizado'] = real_group['Valor Realizado'].fillna(0)

        if real_group.empty:
            real_group = pd.DataFrame({'Filial': ['00'], 'Valor Realizado': [0]})

        real_group = real_group.sort_values(by='Filial')
        real_group['Valor Realizado'] = real_group['Valor Realizado'].apply(format_currency)
        st.dataframe(real_group, use_container_width=True, hide_index=True)

def display_error_log(error_log):
    """
    Displays error log information in a user-friendly way.
    
    Args:
        error_log (dict): Dictionary containing error information for each sheet
    """
    st.error("Não foi possível processar os dados. Foram encontradas inconsistências nos arquivos.")
    
    if 'resumo' in error_log:
        st.warning(f"**Resumo do problema:** {error_log['resumo']}")
    
    if 'erro_geral' in error_log:
        st.error(f"**Erro geral:** {error_log['erro_geral']}")
    
    # Display information about each sheet
    st.subheader("Detalhes por Planilha")
    
    # Prepare the data for a nice display
    error_details = []
    for sheet_name, details in error_log.items():
        if sheet_name not in ['resumo', 'erro_geral']:
            status = details.get('status', 'Desconhecido')
            nome_padronizado = details.get('nome_padronizado', '-')
            motivo = details.get('motivo', '-')
            
            error_details.append({
                "Planilha": sheet_name,
                "Status": status,
                "Nome Padronizado": nome_padronizado,
                "Motivo": motivo
            })
    
    if error_details:
        error_df = pd.DataFrame(error_details)
        st.dataframe(error_df, use_container_width=True, hide_index=True)
    
    st.markdown("""
    Baseado nos erros encontrados, você pode tentar:

    1. **Verificar os nomes das planilhas** - Certifique-se de que as planilhas estão nomeadas conforme esperado (UNIMED, CLIN, VA, SV, SV2)
    2. **Verificar as colunas obrigatórias** - Cada planilha deve conter suas colunas obrigatórias:
    - **UNIMED**: `CPFTITULAR`, `CPFBENEFICIARIO`, `CCFORMATADO`, `FILIAL`, `VALOR`, `406`
    - **CLIN**: `CPFTITULAR`, `CCFORMATADO`, `FILIAL`, `CPFBENEFICIARIO`, `VALOR`, `441`, `442`
    - **VA**: `CPFTITULAR`, `FILIAL`, `CCFORMATADO`, `VALOR`, `424`
    - **SV**: `CCFORMATADO`, `CPFTITULAR`, `FILIAL`, `VALOR`
    - **SV2**: `CPFTITULAR`, `CCFORMATADO`, `VALOR`, `FILIAL`
    3. **Verificar o formato do arquivo** - O arquivo deve estar no formato Excel (.xlsx)
    """)

def process_data(beneficios_file, recorrentes_file, selected_month, month_mapping, ednaldo_mode, progress_callback):
    try:
        result = process_report(
            beneficios_file,
            recorrentes_file,
            ednaldo=ednaldo_mode,
            mes_analise=month_mapping[selected_month],
            progress_callback=progress_callback
        )
        
        # Check if the result is a dictionary (error log) instead of a DataFrame
        is_error_log = isinstance(result, dict)
        
        if not is_error_log:
            # Only proceed with DataFrame operations if result is not an error log
            colaboradores_df = st.session_state.get('colaboradores_df')
            if colaboradores_df is not None:
                progress_callback(95, "Adicionando nomes dos colaboradores...")
                
                # Clean and standardize the colaboradores dataframe
                colaboradores_clean = colaboradores_df.copy()
                
                # Check for duplicates in CPF and handle them
                duplicated_cpfs = colaboradores_clean['CPF'].duplicated()
                if duplicated_cpfs.any():
                    num_duplicates = duplicated_cpfs.sum()
                    colaboradores_clean = colaboradores_clean.drop_duplicates(subset=['CPF'], keep='first')
                
                colaboradores_clean['CPF'] = colaboradores_clean['CPF'].astype(str)
                colaboradores_clean['CPF'] = colaboradores_clean['CPF'].str.replace('[^0-9]', '', regex=True).str.zfill(11)
                
                result = pd.merge(
                    result,
                    colaboradores_clean[['CPF', 'NOME']],
                    left_on='CPF',
                    right_on='CPF',
                    how='left'
                )
        
        return result, is_error_log
    
    except Exception as e:
        raise e

def render_analysis_tab(result_df):
    detail_tab1, detail_tab2 = st.tabs([
        "Comparativo Orçado vs Realizado", 
        "Transferências Entre Filiais"
    ])
    
    with detail_tab1:
        st.write("Comparativo de valores orçados vs realizados por filial:")
        
        # Add dropdown for benefit selection
        selected_benefit = st.selectbox(
            "Selecione o benefício para filtrar o comparativo:",
            ["Vale Alimentação", "Assistência Médica", "Assistência Odontológica", "Seguro de Vida"],
            key="comparativo_benefit_filter"
        )
        
        # Use result_bi from session state if available
        result_bi = st.session_state.get('result_bi')
        comparativo_df = process_filial_comparativo(result_df, result_bi, selected_benefit)
        
        format_dict = {
            'Orçado': format_currency, 
            'Realizado': format_currency, 
            'Diferença': format_currency,
            'Variação (%)': '{:.2f}%'.format,
            'Qtd. Orçado': '{:d}'.format,
            'Qtd. Realizado': '{:d}'.format
        }
        
        highlight_map = {
            'Diferença': highlight_diff,
            'Variação (%)': highlight_percent
        }
        
        styled_comparativo = create_styled_dataframe(comparativo_df, format_dict, highlight_map)
        
        # Configure columns for the data_editor with currency formatting
        column_config = {
            "Orçado": st.column_config.NumberColumn(
                "Orçado",
                format="R$ %.2f"
            ),
            "Realizado": st.column_config.NumberColumn(
                "Realizado",
                format="R$ %.2f"
            ),
            "Diferença": st.column_config.NumberColumn(
                "Diferença",
                format="R$ %.2f"
            ),
            "Variação (%)": st.column_config.NumberColumn(
                "Variação (%)",
                format="%.2f%%"
            ),
            "Justificativa": st.column_config.TextColumn(
                "Justificativa",
                help="Adicione uma justificativa para variações significativas",
                width="large"
            )
        }
        
        # Use data_editor with the column configuration
        st.data_editor(
            comparativo_df,
            column_config=column_config,
            use_container_width=True
        )
        
    with detail_tab2:
        st.write("Análise de transferências entre filiais (Orçado vs Realizado):")
        
        beneficio_matriz = st.selectbox(
            "Selecione o benefício para análise da matriz de transferências:",
            ["Vale Alimentação", "Assistência Médica", "Assistência Odontológica", "Seguro de Vida"],
            key="matriz_transferencia"
        )
        
        df_valido, previsto_col, frealizado_col, realizado_col = render_transfer_matrix(
            result_df, beneficio_matriz
        )
        
        st.markdown("---")
        st.subheader("Detalhamento de CPFs Transferidos")
        st.write("Visualize os CPFs que foram orçados em uma filial e realizados em outra:")
        
        beneficio_cpf = st.selectbox(
            "Selecione o benefício para detalhamento de CPFs transferidos:",
            ["Vale Alimentação", "Assistência Médica", "Assistência Odontológica", "Seguro de Vida"],
            key="detalhe_cpf"
        )
        
        _, df_valido, previsto_col, frealizado_col, realizado_col = process_matriz_transferencia(
            result_df, beneficio_cpf
        )
        
        filiais_orcamento = sorted(['não orçado' if filial == '00' else filial for filial in df_valido['previsto_filial'].unique()])
        filiais_realizacao = sorted(['não realizado' if filial == '00' else filial for filial in df_valido['previsto_filial'].unique()])
        
        col1, col2 = st.columns(2)
        with col1:
            filial_origem = st.selectbox(
                "Filial onde foi orçado:",
                options=filiais_orcamento,
                key=f"origem_{beneficio_cpf}"
            )
            if filial_origem == 'não orçado':
                filial_origem = '00'
        
        with col2:
            filial_destino = st.selectbox(
                "Filial onde foi realizado:",
                options=filiais_realizacao,
                key=f"destino_{beneficio_cpf}"
            )
            if filial_destino == 'não orçado':
                filial_destino = '00'
        
        render_cpf_detail(
            df_valido, filial_origem, filial_destino, 
            previsto_col, frealizado_col, realizado_col
        )

def categorize_employees_by_branch(result_df, selected_filial):
    """
    Categorize employees as terminated, new hires, or transferred for a specific branch.
    Now, 'transferred' includes all transfers:
    - Orçado em outra filial ≠ selecionada e realizado na filial selecionada (valor orçado = 0, valor realizado > 0, mostrar filial orçada)
    - Orçado na filial selecionada e realizado em outra filial ≠ selecionada (valor orçado > 0, valor realizado = 0, mostrar filial realizada)
    """
    df = result_df.copy()
    for col in ['previsto_filial', 'filial_realizada_va', 'filial_realizada_unimed', 
               'filial_realizada_clin', 'filial_realizada_sv']:
        if col in df.columns:
            df.loc[:, col] = df[col].astype(str).fillna('00')

    benefit_cols = [
        ('Vale Alimentação', 'previsto_va', 'realizado_va', 'filial_realizada_va'),
        ('Assistência Médica', 'previsto_unimed', 'realizado_unimed', 'filial_realizada_unimed'),
        ('Assistência Odontológica', 'previsto_clin', 'realizado_clin', 'filial_realizada_clin'),
        ('Seguro de Vida', 'previsto_sv', 'realizado_sv', 'filial_realizada_sv')
    ]

    terminated = {}
    new_hires = {}
    transferred = {}

    for benefit_name, prev_col, real_col, real_filial_col in benefit_cols:
        if real_filial_col not in df.columns:
            continue
        # Desligados
        term_df = df[(df['previsto_filial'] == selected_filial) & 
                      (df[real_filial_col] == '00') & 
                      (df[prev_col] > 0)]
        # Contratados
        new_df = df[(df['previsto_filial'] == '00') & 
                     (df[real_filial_col] == selected_filial) & 
                     (df[real_col] > 0)]
        # Transferidos:
        # Caso 1: Orçado em outra filial, realizado na selecionada
        trans_in = df[(df['previsto_filial'] != selected_filial) &
                      (df[real_filial_col] == selected_filial) &
                      (df['previsto_filial'] != '00') &
                      (df[real_col] > 0)]
        if not trans_in.empty:
            trans_in = trans_in.copy()
            trans_in[prev_col] = 0  # Valor orçado = 0
            trans_in['filial_orcada'] = trans_in['previsto_filial']
            trans_in['filial_transferida'] = selected_filial
        # Caso 2: Orçado na selecionada, realizado em outra filial
        trans_out = df[(df['previsto_filial'] == selected_filial) &
                       (df[real_filial_col] != selected_filial) &
                       (df[real_filial_col] != '00') &
                       (df[prev_col] > 0)]
        if not trans_out.empty:
            trans_out = trans_out.copy()
            trans_out[real_col] = 0  # Valor realizado = 0
            trans_out['filial_orcada'] = selected_filial
            trans_out['filial_transferida'] = trans_out[real_filial_col]
        # Junta ambos os casos
        trans_df = pd.concat([trans_in, trans_out], ignore_index=True)
        transferred[benefit_name] = trans_df
        terminated[benefit_name] = term_df
        new_hires[benefit_name] = new_df
    return terminated, new_hires, transferred

def render_employee_table(df, prev_col, real_col, dest_filial_col=None):
    """
    Render a table of employees with CPF, NAME, BUDGET and ACTUAL values.
    
    Args:
        df (DataFrame): Dataframe with employee data
        prev_col (str): Column name for budget value
        real_col (str): Column name for actual value
        dest_filial_col (str, optional): Column for destination branch (for transfers)
    """
    if df.empty:
        st.info("Não há dados para exibir.")
        return
        
    cpf_col = next((col for col in ['CPF', 'CPFTITULAR'] if col in df.columns), None)
    
    if not cpf_col:
        st.warning("Dados de CPF não disponíveis.")
        return
    
    # Prepare columns for display
    display_cols = [cpf_col]
    
    if 'NOME' in df.columns:
        display_cols.append('NOME')
        
    display_cols.extend([prev_col, real_col])
    
    if dest_filial_col:
        display_cols.append(dest_filial_col)
    
    # Create the display dataframe
    display_df = df[display_cols].copy()
    
    # Rename columns for better readability
    rename_dict = {
        cpf_col: 'CPF',
        prev_col: 'Valor Orçado',
        real_col: 'Valor Realizado'
    }
    
    if 'NOME' in display_df.columns:
        rename_dict['NOME'] = 'Nome Colaborador'
        
    if dest_filial_col:
        rename_dict[dest_filial_col] = 'Filial Realizada'
    
    display_df = display_df.rename(columns=rename_dict)
    
    # Format currency columns
    display_df['Valor Orçado'] = display_df['Valor Orçado'].apply(format_currency)
    display_df['Valor Realizado'] = display_df['Valor Realizado'].apply(format_currency)
    
    # Display the table
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # Show totals
    total_orcado = df[prev_col].sum()
    total_realizado = df[real_col].sum()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Orçado", format_currency(total_orcado))
    with col2:
        st.metric("Total Realizado", format_currency(total_realizado))

def render_employee_category(category_data, benefit_map, category_title, category_description):
    """
    Renders a set of tabs for a specific employee category with data for each benefit type.
    
    Args:
        category_data (dict): Dictionary with benefit names as keys and dataframes as values
        benefit_map (dict): Mapping of benefit names to column names
        category_title (str): Title to display for this category
        category_description (str): Description text explaining this category
    """
    st.subheader(category_title)
    st.markdown(category_description)
    
    tabs = st.tabs(list(benefit_map.keys()))
    for i, (benefit_name, cols) in enumerate(benefit_map.items()):
        with tabs[i]:
            prev_col, real_col, filial_col = cols
            
            # Last parameter is only needed for transfers
            if 'Transferidos' in category_title:
                render_employee_table(category_data[benefit_name], prev_col, real_col, filial_col)
            else:
                render_employee_table(category_data[benefit_name], prev_col, real_col)

def render_summary_tab(result_df):
    """
    Render the Summary Report tab with branch selection and employee categories.
    
    Args:
        result_df (DataFrame): The processed dataframe with employee data
    """
    st.write("Selecione uma filial para visualizar o resumo do relatório:")
    
    # Get unique branches, excluding '00'
    filiais = sorted([f for f in result_df['previsto_filial'].unique() if f != '00' and pd.notna(f)])
    
    if not filiais:
        st.warning("Não foram encontradas filiais válidas no relatório.")
        return
    
    # Branch selection dropdown
    selected_filial = st.selectbox(
        "Filial:",
        options=filiais,
        key="summary_filial_selector"
    )
    
    if not selected_filial:
        st.info("Selecione uma filial para visualizar os dados.")
        return
    
    # Process data for selected branch
    terminated, new_hires, transferred = categorize_employees_by_branch(result_df, selected_filial)
    
    # Display results in expandable sections
    benefit_map = {
        'Vale Alimentação': ('previsto_va', 'realizado_va', 'filial_realizada_va'),
        'Assistência Médica': ('previsto_unimed', 'realizado_unimed', 'filial_realizada_unimed'),
        'Assistência Odontológica': ('previsto_clin', 'realizado_clin', 'filial_realizada_clin'),
        'Seguro de Vida': ('previsto_sv', 'realizado_sv', 'filial_realizada_sv')
    }
    
    # Render each category using the new function
    render_employee_category(
        terminated, 
        benefit_map, 
        f"1. Colaboradores Desligados - Filial {selected_filial}",
        "Colaboradores que foram orçados na filial selecionada mas não realizados (filial realizada = 00)"
    )
    
    render_employee_category(
        new_hires, 
        benefit_map, 
        f"2. Colaboradores Contratados - Filial {selected_filial}",
        "Colaboradores que não foram orçados (filial orçada = 00) mas foram realizados na filial selecionada"
    )
    
    render_employee_category(
        transferred, 
        benefit_map, 
        f"3. Colaboradores Transferidos - Filial {selected_filial}",
        "Colaboradores que foram orçados na filial selecionada mas realizados em outra filial"
    )

def display_comparison_results(result_df, result_bi):
    # This is a wrapper around the utility function
    display_comparison_panel(result_df, result_bi)


def main():
    # Initialize session state variables
    for key in ['processing_completed_time', 'processing_started', 'result_df', 'is_error_log', 'detalhado_df', 'result_bi']:
        if key not in st.session_state:
            st.session_state[key] = None if key != 'processing_started' else False
    
    # Auto-reset the processing state after 5 seconds
    if st.session_state.processing_completed_time is not None:
        elapsed_time = time.time() - st.session_state.processing_completed_time
        if elapsed_time >= 5:
            st.session_state.processing_completed_time = None
            st.session_state.processing_started = False

    st.title("Processador de Relatórios de Benefícios")
    st.markdown("""
    Esta aplicação processa relatórios de benefícios, consolidando dados de diferentes fontes.
    Carregue os arquivos necessários e configure as opções para gerar o relatório final.
    """)
    
    # Usar o sidebar compartilhado
    with st.sidebar:
        files_and_options = render_shared_sidebar()
        
        beneficios_file = files_and_options['beneficios_file']
        recorrentes_file = files_and_options['recorrentes_file']
        selected_month = files_and_options['selected_month']
        month_mapping = files_and_options['month_mapping']
        ednaldo_mode = files_and_options['ednaldo_mode']
        bi_file = files_and_options['bi_file']


        
        # Botão de processamento
        process_button = st.button(
            "Processar Relatório de Benefícios", 
            type="primary", 
            use_container_width=True,
            disabled=(beneficios_file is None or recorrentes_file is None)
        )
    
    result_df = st.session_state.result_df
    is_error_log = st.session_state.is_error_log
    
    # UI elements for progress
    progress_container = st.empty()
    status_container = st.empty()
    success_container = st.empty()
    
    # Process data when button is clicked
    if process_button:
        if beneficios_file is None or recorrentes_file is None:
            st.error("Por favor, carregue os arquivos de benefícios e orçamento.")
        else:
            try:
                # Reset all relevant session state variables
                st.session_state.result_df = None
                st.session_state.is_error_log = None
                st.session_state.detalhado_df = None
                st.session_state.result_bi = None
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
                    
                    # Process main report data
                    result, is_error_log = process_data(
                        beneficios_file, 
                        recorrentes_file, 
                        selected_month, 
                        month_mapping, 
                        ednaldo_mode, 
                        update_progress
                    )
                    
                    # Store in session state right after processing
                    st.session_state.result_df = result
                    st.session_state.is_error_log = is_error_log
                    
                    # Only process BI data if main report was successful and BI file is provided
                    if not is_error_log and bi_file is not None:
                        try:
                            update_progress(90, "Processando dados para comparação com BI...")
                            detalhado_df, result_bi = process_report2(
                                beneficios_file,
                                bi_file,
                                ednaldo_mode
                            )
                            st.session_state.detalhado_df = detalhado_df
                            st.session_state.result_bi = result_bi
                        except Exception as bi_error:
                            st.warning(f"Não foi possível processar a comparação com BI: {str(bi_error)}")
                
                st.session_state.processing_completed_time = time.time()
                if not is_error_log:
                    success_container.success(f"Processamento concluído! {len(result)} registros processados.")
                
                # Use rerun outside the spinner to avoid UI conflicts
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
            
            tab1, tab2, tab3, tab4 = st.tabs(["Visão Geral", "Análise Detalhada", "Resumo relatório", "Comparação BI vs Relatório"])
            
            with tab1:
                render_benefit_summary(result_df)
                
                st.subheader("Prévia do relatório")
                st.dataframe(result_df, use_container_width=True, hide_index=True)
                relatorio = f"# Relatório de Benefícios\n\n{result_df.to_markdown(index=False)}"

                st.download_button(
                    label="📥 Baixar Relatório Markdown",
                    data=relatorio.encode("utf-8"),
                    file_name=f"relatorio_beneficios_{datetime.now().strftime('%Y%m%d')}.md",
                    mime="text/markdown",
                    use_container_width=True
                )
            with tab2:
                st.subheader("Análise por Filial")
                render_analysis_tab(result_df)
                
            with tab3:
                st.subheader("Resumo por Filial")
                render_summary_tab(result_df)
            
            with tab4:
                if st.session_state.detalhado_df is not None and st.session_state.result_bi is not None:
                    display_comparison_panel(st.session_state.detalhado_df, st.session_state.result_bi)
                else:
                    st.info("Dados para comparação com BI não disponíveis. Certifique-se de carregar o arquivo de BI e processar os dados.")

            # Add download button
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                result_df.to_excel(writer, index=False)
            
            with st.sidebar.container():
                st.download_button(
                    label="📥 Baixar Relatório Excel",
                    data=output.getvalue(),
                    file_name=f"relatorio_beneficios_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )

if __name__ == "__main__":
    main()
