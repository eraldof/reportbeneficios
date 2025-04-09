import streamlit as st
import pandas as pd
from datetime import datetime
import time

def init_session_state():
    """Inicializa variáveis do session_state se ainda não existirem"""
    if 'files_loaded' not in st.session_state:
        st.session_state['files_loaded'] = False
    
    # Estado dos arquivos
    for key in ['beneficios_file', 'recorrentes_file', 'bi_file', 'colaboradores_file']:
        if key not in st.session_state:
            st.session_state[key] = None
    
    # Configurações
    for key in ['selected_month', 'month_mapping', 'ednaldo_mode']:
        if key not in st.session_state:
            st.session_state[key] = None
    
    # Inicializa mapeamento de meses
    if st.session_state['month_mapping'] is None:
        st.session_state['month_mapping'] = {
            'Janeiro': '01', 'Fevereiro': '02', 'Março': '03', 'Abril': '04', 
            'Maio': '05', 'Junho': '06', 'Julho': '07', 'Agosto': '08', 
            'Setembro': '09', 'Outubro': '10', 'Novembro': '11', 'Dezembro': '12'
        }

def validate_excel_file(file, file_type):
    """Valida arquivos Excel e retorna um preview se forem válidos"""
    if file is None:
        return False, None, f"Arquivo {file_type} não foi carregado."
    
    try:
        # Verifica tamanho do arquivo (limite de 50MB)
        if file.size > 50 * 1024 * 1024:
            return False, None, f"Arquivo {file_type} muito grande (>50MB)."
        
        # Preview da primeira planilha do arquivo Excel
        preview_df = pd.read_excel(file, sheet_name=0, nrows=5)
        file.seek(0)  # Reinicia o ponteiro do arquivo após a leitura
        
        if preview_df.empty:
            return False, None, f"Arquivo {file_type} parece estar vazio."
            
        return True, preview_df, "Arquivo válido."
    except Exception as e:
        return False, None, f"Erro ao validar arquivo {file_type}: {str(e)}"

def load_colaboradores_file(file):
    """Carrega e valida o arquivo de colaboradores"""
    try:
        if file is None:
            return None
            
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        
        file.seek(0)  # Reinicia o ponteiro do arquivo
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

def render_shared_sidebar():
    """Renderiza o sidebar compartilhado para todas as páginas"""
    init_session_state()
    
    st.header("Upload de Arquivos")
    
    # Arquivo de benefícios
    st.subheader("Carregar arquivo de benefícios")
    beneficios_file = st.file_uploader(
        type=["xlsx"],
        help="Arquivo Excel contendo planilhas com dados de benefícios",
        label_visibility="collapsed",
        label="Carregar arquivo de benefícios",
        key="shared_beneficios_uploader"
    )
    
    if beneficios_file:
        is_valid, preview, message = validate_excel_file(beneficios_file, "de benefícios")
        if is_valid:
            st.session_state.beneficios_file = beneficios_file
            st.success("✅ Arquivo de benefícios carregado com sucesso")
        else:
            st.error(message)
            st.session_state.beneficios_file = None

    # Arquivo de orçamento
    st.subheader("Carregar arquivo com o orçamento")
    recorrentes_file = st.file_uploader(
        label="Carregar arquivo com o orçamento",
        label_visibility="collapsed",
        type=["xlsx"],
        help="Arquivo Excel contendo dados de recorrentes",
        key="shared_recorrentes_uploader"
    )
    
    if recorrentes_file:
        is_valid, preview, message = validate_excel_file(recorrentes_file, "de orçamento")
        if is_valid:
            st.session_state.recorrentes_file = recorrentes_file
            st.success("✅ Arquivo de orçamento carregado com sucesso")
        else:
            st.error(message)
            st.session_state.recorrentes_file = None
    
    # Arquivo de BI
    st.subheader("Carregar arquivo com o detalhado BI")
    bi_file = st.file_uploader(
        label="Carregar arquivo com o detalhado BI",
        label_visibility="collapsed",
        type=["xlsx"],
        help="Arquivo Excel contendo dados do BI",
        key="shared_bi_uploader"
    )
    
    if bi_file:
        is_valid, preview, message = validate_excel_file(bi_file, "de BI")
        if is_valid:
            st.session_state.bi_file = bi_file
            st.success("✅ Arquivo de BI carregado com sucesso")
        else:
            st.error(message)
            st.session_state.bi_file = None
    
    # Arquivo de colaboradores
    st.subheader("Carregar arquivo de colaboradores")
    colaboradores_file = st.file_uploader(
        label="Carregar arquivo com nomes dos colaboradores",
        label_visibility="collapsed",
        type=["xlsx", "csv"],
        help="Arquivo contendo CPF e NOME dos colaboradores (opcional)",
        key="shared_colaboradores_uploader"
    )
    
    if colaboradores_file:
        colaboradores_df = load_colaboradores_file(colaboradores_file)
        if colaboradores_df is not None:
            st.session_state.colaboradores_df = colaboradores_df
            st.session_state.colaboradores_file = colaboradores_file
    
    # Configurações de processamento
    st.subheader("Opções de Processamento")
    
    # Seleção de mês
    month_names = list(st.session_state.month_mapping.keys())
    mes_atual = int(datetime.now().strftime('%m'))
    mes_default = (mes_atual - 1) % 12 or 12
    
    selected_month = st.selectbox(
        "Selecione o mês de análise:",
        options=month_names,
        index=mes_default-1,
        key="shared_month_selector"
    )
    st.session_state.selected_month = selected_month
    
    # Modo Ednaldo
    ednaldo_mode = st.checkbox(
        "Usar modo Ednaldo", 
        value=False,
        help="Ativa o processamento com regras específicas do modo Ednaldo",
        key="shared_ednaldo_mode"
    )
    st.session_state.ednaldo_mode = ednaldo_mode
    
    return {
        'beneficios_file': st.session_state.get('beneficios_file'),
        'recorrentes_file': st.session_state.get('recorrentes_file'),
        'bi_file': st.session_state.get('bi_file'),
        'colaboradores_file': st.session_state.get('colaboradores_file'),
        'selected_month': st.session_state.selected_month,
        'month_mapping': st.session_state.month_mapping,
        'ednaldo_mode': st.session_state.ednaldo_mode
    }

def get_files_and_options():
    """Retorna os arquivos e opções armazenados no session_state"""
    init_session_state()
    
    return {
        'beneficios_file': st.session_state.get('beneficios_file'),
        'recorrentes_file': st.session_state.get('recorrentes_file'),
        'bi_file': st.session_state.get('bi_file'),
        'colaboradores_file': st.session_state.get('colaboradores_file'),
        'colaboradores_df': st.session_state.get('colaboradores_df'),
        'selected_month': st.session_state.selected_month,
        'month_mapping': st.session_state.month_mapping,
        'ednaldo_mode': st.session_state.ednaldo_mode
    }
