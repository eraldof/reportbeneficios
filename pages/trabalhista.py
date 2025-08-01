import streamlit as st
import pandas as pd
import main
import utilitarios as ut
import warnings
import io
from datetime import datetime


warnings.filterwarnings(
    "ignore", 
    message="Workbook contains no default style, apply openpyxl's default"
)

# Configuração da página
st.set_page_config(
    page_title="Processamento de Relatórios",
    page_icon="📊",
    layout="wide"
)

st.logo('logo_popup.png', size = "large")
# Título principal
st.title("📊 Sistema de Processamento de Relatórios")


with st.sidebar:
    st.header("📁 Upload de Arquivos")
    
    # Campos de upload para 3 arquivos xlsx
    data_folha = st.file_uploader(
        "Upload Arquivo com realizado e orcado", 
        type=['xlsx'], 
        key="realizado"
    )
    
    st.divider()
    
    # Verificar se todos os 3 arquivos foram carregados
    todos_arquivos_carregados = data_folha is not None

    # Inicializar session_state se não existir
    if 'data_folha' not in st.session_state:
        st.session_state.data_folha = None

    # Botão processar relatório (habilitado apenas quando todos os arquivos estão carregados)
    if st.button(
        "🔄 Processar Relatório", 
        disabled=not todos_arquivos_carregados,
        use_container_width=True
    ):
        orcamento, realizado = main.estruturar_dados(data_folha)
        
        relatorio = main.consolidar_orcado_realizado(orcamento, realizado)

        st.session_state.data_folha = relatorio
        
        st.success("✅ Relatório processado com sucesso!")

    if st.session_state.data_folha is not None:

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            st.session_state.data_folha.to_excel(writer, sheet_name='Consolidado', index=False)
                    
        with st.sidebar.container():
            st.download_button(
                label="📥 Baixar Relatório Excel",
                data=output.getvalue(),
                file_name=f"trabalhista_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    st.subheader("📋 Status dos Arquivos")
    st.write(f"Arquivo Realizado: {'✅' if data_folha else '❌'}")

if st.session_state.data_folha is not None:
    data_folha = st.session_state.data_folha

    tab1, tab2 = st.tabs([
        "📊 COMPARAÇÃO ORCADO VS REALIZADO", 
        "📋 RESUMO RELATÓRIO DETALHADO", 
    ])

    with tab1:
        ut.analise_folha_por_natureza(data_folha)
    
    with tab2:
        ut.exibir_analise_folha_pagamento(data_folha)


else:
    st.info("👈 Faça o upload do arquivo no sidebar e clique em 'Processar Relatório' para visualizar os painéis.")
    
    if not todos_arquivos_carregados:
        st.warning("⚠️ É necessário carregar o arquivo Excel para habilitar o processamento.")
    
    # Mostrar informações adicionais
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📝 Instruções:")
        st.write("1. Faça upload do arquivo que contém os dados de folha")
        st.write("4. Clique em 'Processar Relatório'")