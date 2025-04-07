import streamlit as st
import pandas as pd
from datetime import datetime
import io
import time
from streamlit.errors import NoSessionContext

from main import process_report, verificar_retorno
st.set_page_config(
    page_title="Processador de Relatórios de Benefícios",
    page_icon="📊",
    layout="centered"
)

# Utility functions
def format_currency(value):
    return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def highlight_values(val, thresholds, color_schemes):
    """Generic highlighting function for dataframe values"""
    if not isinstance(val, (int, float)):
        return ''
    
    for threshold_set, color_scheme in zip(thresholds, color_schemes):
        min_val, max_val = threshold_set
        if (min_val is None or val > min_val) and (max_val is None or val <= max_val):
            bg_color, text_color, font_weight = color_scheme
            return f'background-color: {bg_color}; color: {text_color}; font-weight: {font_weight}'
    return ''

def highlight_diff(val):
    thresholds = [(0, None), (None, 0)]
    color_schemes = [
        ('rgba(255, 0, 0, 0.1)', 'darkred', 'bold'),
        ('rgba(0, 128, 0, 0.1)', 'darkgreen', 'bold')
    ]
    return highlight_values(val, thresholds, color_schemes)

def highlight_percent(val):
    thresholds = [(10, None), (5, 10), (None, -10), (-10, -5)]
    color_schemes = [
        ('rgba(255, 0, 0, 0.2)', 'darkred', 'bold'),
        ('rgba(255, 165, 0, 0.2)', 'darkorange', 'normal'),
        ('rgba(0, 128, 0, 0.2)', 'darkgreen', 'bold'),
        ('rgba(144, 238, 144, 0.2)', 'green', 'normal')
    ]
    return highlight_values(val, thresholds, color_schemes)

def highlight_transfers(val):
    thresholds = [(1000, None), (100, 1000), (0.01, 100)]
    color_schemes = [
        ('rgba(65, 105, 225, 0.3)', 'darkblue', 'bold'),
        ('rgba(65, 105, 225, 0.2)', 'darkblue', 'normal'),
        ('rgba(65, 105, 225, 0.1)', 'darkblue', 'normal')
    ]
    return highlight_values(val, thresholds, color_schemes)

def create_styled_dataframe(df, format_dict, highlight_map=None):
    styled_df = df.style.format(format_dict)
    
    if highlight_map:
        for subset, highlight_func in highlight_map.items():
            styled_df = styled_df.map(highlight_func, subset=subset)
    
    return styled_df

# Data processing functions
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

def process_filial_comparativo(result_df):
    # Criar uma cópia explícita para evitar warnings
    df = result_df.copy()
    df.loc[:, 'previsto_filial'] = df['previsto_filial'].fillna('Não Informado')
    
    benefit_cols = [
        ('va', 'previsto_va', 'realizado_va'),
        ('unimed', 'previsto_unimed', 'realizado_unimed'),
        ('clin', 'previsto_clin', 'realizado_clin'),
        ('sv', 'previsto_sv', 'realizado_sv')
    ]
    
    comparativo_filiais = []
    
    for filial in df['previsto_filial'].unique():
        filial_df = df[df['previsto_filial'] == filial]
        
        total_previsto = sum(filial_df[prev_col].sum() for _, prev_col, _ in benefit_cols)
        total_realizado = sum(filial_df[real_col].sum() for _, _, real_col in benefit_cols)
        
        diferenca = total_realizado - total_previsto
        variacao_pct = (diferenca / total_previsto * 100) if total_previsto != 0 else 0
        
        comparativo_filiais.append({
            'Filial': filial,
            'Previsto': total_previsto,
            'Realizado': total_realizado,
            'Diferença': diferenca,
            'Variação (%)': variacao_pct
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


# UI components
def render_sidebar():
    st.header("Upload de Arquivos")
    
    # Inicialize session state para armazenar nomes de arquivos anteriores
    if 'prev_beneficios_file' not in st.session_state:
        st.session_state.prev_beneficios_file = None
    if 'prev_recorrentes_file' not in st.session_state:
        st.session_state.prev_recorrentes_file = None
    if 'prev_colaboradores_file' not in st.session_state:
        st.session_state.prev_colaboradores_file = None
    
    # Botão para limpar todos os arquivos carregados
    if st.button("Limpar todos os arquivos", key="clear_all_files"):
        st.session_state.prev_beneficios_file = None
        st.session_state.prev_recorrentes_file = None
        st.session_state.prev_colaboradores_file = None
        st.session_state.result_df = None
        st.session_state.is_error_log = None
        st.session_state.colaboradores_df = None
        st.rerun()
    
    st.subheader("Carregar arquivo de benefícios")
    beneficios_file = st.file_uploader(
        type=["xlsx"],
        help="Arquivo Excel contendo planilhas com dados de benefícios",
        label_visibility="collapsed",
        label="Carregar arquivo de beneficios",
        key="beneficios_file_uploader"
    )

    # Verificar se o arquivo de benefícios mudou
    if beneficios_file is not None and (st.session_state.prev_beneficios_file is None or 
                                       beneficios_file.name != st.session_state.prev_beneficios_file):
        st.session_state.prev_beneficios_file = beneficios_file.name
        # Limpar os resultados anteriores quando um novo arquivo for carregado
        st.session_state.result_df = None
        st.session_state.is_error_log = None

    st.subheader("Carregar arquivo com o orçamento")
    recorrentes_file = st.file_uploader(
        label="Carregar arquivo com o orçamento",
        label_visibility="collapsed",
        type=["xlsx"],
        help="Arquivo Excel contendo dados de recorrentes",
        key="recorrentes_file_uploader"
    )
    
    # Verificar se o arquivo de orçamento mudou
    if recorrentes_file is not None and (st.session_state.prev_recorrentes_file is None or 
                                        recorrentes_file.name != st.session_state.prev_recorrentes_file):
        st.session_state.prev_recorrentes_file = recorrentes_file.name
        # Limpar os resultados anteriores quando um novo arquivo for carregado
        st.session_state.result_df = None
        st.session_state.is_error_log = None
    
    st.subheader("Carregar arquivo de colaboradores (opcional)")
    colaboradores_file = st.file_uploader(
        label="Carregar arquivo com nomes dos colaboradores",
        label_visibility="collapsed",
        type=["xlsx", "csv"],
        help="Arquivo contendo CPF e NOME dos colaboradores (opcional)",
        key="colaboradores_file_uploader"
    )
    
    # Verificar se o arquivo de colaboradores mudou
    if colaboradores_file is not None and (st.session_state.prev_colaboradores_file is None or 
                                          colaboradores_file.name != st.session_state.prev_colaboradores_file):
        st.session_state.prev_colaboradores_file = colaboradores_file.name
        # Limpar apenas os dados de colaboradores quando um novo arquivo for carregado
        st.session_state.colaboradores_df = None

    st.subheader("Opções de Processamento")

    month_mapping = {
        'Janeiro': '01', 'Fevereiro': '02', 'Março': '03', 'Abril': '04', 
        'Maio': '05', 'Junho': '06', 'Julho': '07', 'Agosto': '08', 
        'Setembro': '09', 'Outubro': '10', 'Novembro': '11', 'Dezembro': '12'
    }
    
    mes_atual = int(datetime.now().strftime('%m'))
    mes_default = (mes_atual - 1) % 12 or 12
    month_names = list(month_mapping.keys())
    
    selected_month = st.selectbox(
        "Selecione o mês de análise:",
        options=month_names,
        index=mes_default-1
    )

    ednaldo_mode = st.checkbox("Usar modo Ednaldo", value=False, 
                              help="Ativa o processamento com regras específicas do modo Ednaldo")

    process_button = st.button("Processar Dados", type="primary", use_container_width=True)
    
    return beneficios_file, recorrentes_file, colaboradores_file, selected_month, month_mapping, ednaldo_mode, process_button

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
            if st.session_state.colaboradores_df is not None:
                progress_callback(95, "Adicionando nomes dos colaboradores...")
                
                # Clean and standardize the colaboradores dataframe
                colaboradores_clean = st.session_state.colaboradores_df.copy()
                
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
    detail_tab1, detail_tab2, detail_tab3 = st.tabs([
        "Comparativo Orçado vs Realizado", 
        "Transferências Entre Filiais", 
        "Detalhes por Benefício"
    ])
    
    with detail_tab1:
        st.write("Comparativo de valores orçados vs realizados por filial:")
        
        comparativo_df = process_filial_comparativo(result_df)
        
        format_dict = {
            'Previsto': format_currency, 
            'Realizado': format_currency, 
            'Diferença': format_currency,
            'Variação (%)': '{:.2f}%'.format
        }
        
        highlight_map = {
            'Diferença': highlight_diff,
            'Variação (%)': highlight_percent
        }
        
        styled_comparativo = create_styled_dataframe(comparativo_df, format_dict, highlight_map)
        st.dataframe(styled_comparativo, use_container_width=True)
        
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
        
    with detail_tab3:
        st.write("Detalhes por tipo de benefício:")
        
        benefit_tabs = st.tabs(["Vale Alimentação", "Assistência Médica", "Assistência Odontológica", "Seguro de Vida"])
        
        benefit_details = [
            ("Vale Alimentação", "previsto_va", "realizado_va", "filial_realizada_va"),
            ("Assistência Médica", "previsto_unimed", "realizado_unimed", "filial_realizada_unimed"),
            ("Assistência Odontológica", "previsto_clin", "realizado_clin", "filial_realizada_clin"),
            ("Seguro de Vida", "previsto_sv", "realizado_sv", "filial_realizada_sv")
        ]
        
        for i, (name, prev, real, filial) in enumerate(benefit_details):
            with benefit_tabs[i]:
                render_benefit_details(result_df, name, prev, real, filial)

def categorize_employees_by_branch(result_df, selected_filial):
    """
    Categorize employees as terminated, new hires, or transferred for a specific branch.
    
    Args:
        result_df (DataFrame): The processed dataframe with employee data
        selected_filial (str): The selected branch to analyze
    
    Returns:
        tuple: Three dataframes for terminated, new hires, and transferred employees
    """
    # Create a copy to avoid warnings
    df = result_df.copy()
    
    # Make sure we're working with strings for branch fields
    for col in ['previsto_filial', 'filial_realizada_va', 'filial_realizada_unimed', 
               'filial_realizada_clin', 'filial_realizada_sv']:
        if col in df.columns:
            df.loc[:, col] = df[col].astype(str).fillna('00')
    
    # Define benefit columns for analysis
    benefit_cols = [
        ('Vale Alimentação', 'previsto_va', 'realizado_va', 'filial_realizada_va'),
        ('Assistência Médica', 'previsto_unimed', 'realizado_unimed', 'filial_realizada_unimed'),
        ('Assistência Odontológica', 'previsto_clin', 'realizado_clin', 'filial_realizada_clin'),
        ('Seguro de Vida', 'previsto_sv', 'realizado_sv', 'filial_realizada_sv')
    ]
    
    # Initialize dictionaries to store results
    terminated = {}
    new_hires = {}
    transferred = {}
    
    # Process each benefit type
    for benefit_name, prev_col, real_col, real_filial_col in benefit_cols:
        if real_filial_col not in df.columns:
            continue
            
        # Terminated employees: budgeted in selected branch but not actually allocated (filial realizada = 00)
        term_df = df[(df['previsto_filial'] == selected_filial) & 
                      (df[real_filial_col] == '00') & 
                      (df[prev_col] > 0)]
        
        # New hires: not budgeted (filial orçada = 00) but allocated to selected branch
        new_df = df[(df['previsto_filial'] == '00') & 
                     (df[real_filial_col] == selected_filial) & 
                     (df[real_col] > 0)]
        
        # Transferred: budgeted in selected branch but allocated to a different branch (not 00)
        trans_df = df[(df['previsto_filial'] == selected_filial) & 
                       (df[real_filial_col] != '00') & 
                       (df[real_filial_col] != selected_filial) & 
                       (df[prev_col] > 0)]
        
        terminated[benefit_name] = term_df
        new_hires[benefit_name] = new_df
        transferred[benefit_name] = trans_df
    
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

def render_summary_tab(result_df):
    """
    Render the Summary Report tab with branch selection and employee categories.
    
    Args:
        result_df (DataFrame): The processed dataframe with employee data
    """
    st.write("Selecione uma filial para visualizar o resumo do relatório:")
    
    # Create a copy and convert NaN values to 0 for budget and actual columns
    df = result_df.copy()
    budget_actual_cols = [
        'previsto_va', 'realizado_va', 
        'previsto_unimed', 'realizado_unimed', 
        'previsto_clin', 'realizado_clin', 
        'previsto_sv', 'realizado_sv'
    ]
    
    for col in budget_actual_cols:
        if col in df.columns:
            df[col] = df[col].fillna(0)
    
    # Get unique branches, excluding '00'
    filiais = sorted([f for f in df['previsto_filial'].unique() if f != '00' and pd.notna(f)])
    
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
    terminated, new_hires, transferred = categorize_employees_by_branch(df, selected_filial)
    
    # Define benefit columns for display
    benefit_map = {
        'Vale Alimentação': ('previsto_va', 'realizado_va', 'filial_realizada_va'),
        'Assistência Médica': ('previsto_unimed', 'realizado_unimed', 'filial_realizada_unimed'),
        'Assistência Odontológica': ('previsto_clin', 'realizado_clin', 'filial_realizada_clin'),
        'Seguro de Vida': ('previsto_sv', 'realizado_sv', 'filial_realizada_sv')
    }
    
    # Consolidated view of all categories
    st.subheader(f"Resumo para Filial: {selected_filial}")
    
    # 1. Terminated Employees
    st.markdown("### 1. Colaboradores Desligados")
    st.markdown("Colaboradores que foram orçados na filial selecionada mas não realizados (filial realizada = 00)")
    
    # Combine all benefit types for terminated employees
    all_terminated = pd.DataFrame()
    for benefit_name, (prev_col, real_col, _) in benefit_map.items():
        if not terminated[benefit_name].empty:
            temp_df = terminated[benefit_name].copy()
            temp_df['Tipo de Benefício'] = benefit_name
            temp_df['Prev_Col'] = prev_col
            temp_df['Real_Col'] = real_col
            all_terminated = pd.concat([all_terminated, temp_df])
    
    if not all_terminated.empty:
        cpf_col = next((col for col in ['CPF', 'CPFTITULAR'] if col in all_terminated.columns), None)
        display_cols = [cpf_col, 'Tipo de Benefício']
        
        if 'NOME' in all_terminated.columns:
            display_cols.append('NOME')
        
        display_df = all_terminated[display_cols + ['Prev_Col', 'Real_Col']].copy()
        
        # Add values from the appropriate columns
        display_df['Valor Orçado'] = display_df.apply(
            lambda row: row[row['Prev_Col']], axis=1
        )
        display_df['Valor Realizado'] = display_df.apply(
            lambda row: row[row['Real_Col']], axis=1
        )
        
        # Drop utility columns
        display_df = display_df.drop(['Prev_Col', 'Real_Col'], axis=1)
        
        # Rename columns
        rename_dict = {cpf_col: 'CPF'}
        if 'NOME' in display_df.columns:
            rename_dict['NOME'] = 'Nome Colaborador'
        
        display_df = display_df.rename(columns=rename_dict)
        
        # Format currency columns
        display_df['Valor Orçado'] = display_df['Valor Orçado'].apply(format_currency)
        display_df['Valor Realizado'] = display_df['Valor Realizado'].apply(format_currency)
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # Show totals
        total_orcado = all_terminated.apply(lambda row: row[row['Prev_Col']], axis=1).sum()
        total_realizado = all_terminated.apply(lambda row: row[row['Real_Col']], axis=1).sum()
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Orçado", format_currency(total_orcado))
        with col2:
            st.metric("Total Realizado", format_currency(total_realizado))
    else:
        st.info("Não há colaboradores desligados para exibir.")
    
    # 2. New Hires
    st.markdown("### 2. Colaboradores Contratados")
    st.markdown("Colaboradores que não foram orçados (filial orçada = 00) mas foram realizados na filial selecionada")
    
    # Similar approach for new hires
    all_new_hires = pd.DataFrame()
    for benefit_name, (prev_col, real_col, _) in benefit_map.items():
        if not new_hires[benefit_name].empty:
            temp_df = new_hires[benefit_name].copy()
            temp_df['Tipo de Benefício'] = benefit_name
            temp_df['Prev_Col'] = prev_col
            temp_df['Real_Col'] = real_col
            all_new_hires = pd.concat([all_new_hires, temp_df])
    
    if not all_new_hires.empty:
        cpf_col = next((col for col in ['CPF', 'CPFTITULAR'] if col in all_new_hires.columns), None)
        display_cols = [cpf_col, 'Tipo de Benefício']
        
        if 'NOME' in all_new_hires.columns:
            display_cols.append('NOME')
        
        display_df = all_new_hires[display_cols + ['Prev_Col', 'Real_Col']].copy()
        
        display_df['Valor Orçado'] = display_df.apply(
            lambda row: row[row['Prev_Col']], axis=1
        )
        display_df['Valor Realizado'] = display_df.apply(
            lambda row: row[row['Real_Col']], axis=1
        )
        
        display_df = display_df.drop(['Prev_Col', 'Real_Col'], axis=1)
        
        rename_dict = {cpf_col: 'CPF'}
        if 'NOME' in display_df.columns:
            rename_dict['NOME'] = 'Nome Colaborador'
        
        display_df = display_df.rename(columns=rename_dict)
        
        display_df['Valor Orçado'] = display_df['Valor Orçado'].apply(format_currency)
        display_df['Valor Realizado'] = display_df['Valor Realizado'].apply(format_currency)
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        total_orcado = all_new_hires.apply(lambda row: row[row['Prev_Col']], axis=1).sum()
        total_realizado = all_new_hires.apply(lambda row: row[row['Real_Col']], axis=1).sum()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Orçado", format_currency(total_orcado))
        with col2:
            st.metric("Total Realizado", format_currency(total_realizado))
    else:
        st.info("Não há novos colaboradores para exibir.")
    
    # 3. Transferred Employees
    st.markdown("### 3. Colaboradores Transferidos")
    st.markdown("Colaboradores que foram orçados na filial selecionada mas realizados em outra filial")
    
    all_transferred = pd.DataFrame()
    for benefit_name, (prev_col, real_col, filial_col) in benefit_map.items():
        if not transferred[benefit_name].empty:
            temp_df = transferred[benefit_name].copy()
            temp_df['Tipo de Benefício'] = benefit_name
            temp_df['Prev_Col'] = prev_col
            temp_df['Real_Col'] = real_col
            temp_df['Filial_Col'] = filial_col
            all_transferred = pd.concat([all_transferred, temp_df])
    
    if not all_transferred.empty:
        cpf_col = next((col for col in ['CPF', 'CPFTITULAR'] if col in all_transferred.columns), None)
        display_cols = [cpf_col, 'Tipo de Benefício']
        
        if 'NOME' in all_transferred.columns:
            display_cols.append('NOME')
        
        display_df = all_transferred[display_cols + ['Prev_Col', 'Real_Col', 'Filial_Col']].copy()
        
        display_df['Valor Orçado'] = display_df.apply(
            lambda row: row[row['Prev_Col']], axis=1
        )
        display_df['Valor Realizado'] = display_df.apply(
            lambda row: row[row['Real_Col']], axis=1
        )
        display_df['Filial Realizada'] = display_df.apply(
            lambda row: row[row['Filial_Col']], axis=1
        )
        
        display_df = display_df.drop(['Prev_Col', 'Real_Col', 'Filial_Col'], axis=1)
        
        rename_dict = {cpf_col: 'CPF'}
        if 'NOME' in display_df.columns:
            rename_dict['NOME'] = 'Nome Colaborador'
        
        display_df = display_df.rename(columns=rename_dict)
        
        display_df['Valor Orçado'] = display_df['Valor Orçado'].apply(format_currency)
        display_df['Valor Realizado'] = display_df['Valor Realizado'].apply(format_currency)
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        total_orcado = all_transferred.apply(lambda row: row[row['Prev_Col']], axis=1).sum()
        total_realizado = all_transferred.apply(lambda row: row[row['Real_Col']], axis=1).sum()
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Orçado", format_currency(total_orcado))
        with col2:
            st.metric("Total Realizado", format_currency(total_realizado))
    else:
        st.info("Não há colaboradores transferidos para exibir.")

def main():
    # Initialize session state variables
    for key in ['processing_completed_time', 'processing_started', 'result_df', 'colaboradores_df', 'is_error_log']:
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
    Carregue os arquivos necessários e configure as opções para gerar o relatório final.
    """)
    
    # Sidebar for file upload and configuration
    with st.sidebar:
        beneficios_file, recorrentes_file, colaboradores_file, selected_month, month_mapping, ednaldo_mode, process_button = render_sidebar()
    
    result_df = st.session_state.result_df
    is_error_log = st.session_state.is_error_log
    
    # UI elements for progress
    progress_container = st.empty()
    status_container = st.empty()
    success_container = st.empty()
    
    # Load colaboradores file if provided
    if colaboradores_file is not None and st.session_state.colaboradores_df is None:
        st.session_state.colaboradores_df = load_colaboradores_file(colaboradores_file)
    
    # Process data when button is clicked
    if process_button:
        if beneficios_file is None or recorrentes_file is None:
            st.error("Por favor, carregue os dois arquivos necessários.")
        else:
            try:
                st.session_state.result_df = None
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
                    
                    result, is_error_log = process_data(
                        beneficios_file, 
                        recorrentes_file, 
                        selected_month, 
                        month_mapping, 
                        ednaldo_mode, 
                        update_progress
                    )
                
                st.session_state.result_df = result
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
            
            tab1, tab2, tab3 = st.tabs(["Visão Geral", "Análise Detalhada", "Resumo relatório"])
            
            with tab1:
                render_benefit_summary(result_df)
                
                st.subheader("Prévia do relatório")
                st.dataframe(result_df, use_container_width=True, hide_index=True)
            
            with tab2:
                st.subheader("Análise por Filial")
                render_analysis_tab(result_df)
                
            with tab3:
                st.subheader("Resumo por Filial")
                render_summary_tab(result_df)
            
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
