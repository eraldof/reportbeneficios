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

# Sidebar
with st.sidebar:
    st.header("📁 Upload de Arquivos")
    
    # Campos de upload para 3 arquivos xlsx
    realizado = st.file_uploader(
        "Upload Arquivo Realizado", 
        type=['xlsx'], 
        key="realizado"
    )
    
    orcado = st.file_uploader(
        "Upload Arquivo com o orcado", 
        type=['xlsx'], 
        key="orcado"
    )
    
    bi_detalhado = st.file_uploader(
        "Upload Arquivo Detalhado BI", 
        type=['xlsx'], 
        key="bi_detalhado"
    )
    
    st.divider()
    
    # Dropdown com meses
    meses = {
            'Janeiro': '01', 'Fevereiro': '02', 'Março': '03', 'Abril': '04', 
            'Maio': '05', 'Junho': '06', 'Julho': '07', 'Agosto': '08', 
            'Setembro': '09', 'Outubro': '10', 'Novembro': '11', 'Dezembro': '12'
        }
    
    mes_selecionado = st.selectbox(
        "📅 Selecione o Mês",
        meses.keys(),
        index=0
    )
    
    
    # Checkbox Ednaldo
    ednaldo_check = st.checkbox("Ednaldo")
    
    st.divider()
    
    # Verificar se todos os 3 arquivos foram carregados
    todos_arquivos_carregados = realizado is not None and orcado is not None and bi_detalhado is not None

    # Inicializar session_state se não existir
    if 'relatorio_gerado' not in st.session_state:
        st.session_state.relatorio_gerado = None
    if 'dados_bi_gerados' not in st.session_state:
        st.session_state.dados_bi_gerados = None

    # Botão processar relatório (habilitado apenas quando todos os arquivos estão carregados)
    if st.button(
        "🔄 Processar Relatório", 
        disabled=not todos_arquivos_carregados,
        use_container_width=True
    ):
        # Gerar os relatórios e armazenar no session_state
        realizado_vs_orcado = main.gerar_relatorio(
            realizado, 
            orcado,
            ednaldo_check,
            meses.get(mes_selecionado)
        )
        
        tabela_realizado, tabela_bi = main.gerar_comparacao_bi(
            realizado,
            bi_detalhado,
            ednaldo_check
        )
        
        # Armazenar os dados no session_state para persistir após o recarregamento
        st.session_state.relatorio_gerado = realizado_vs_orcado
        st.session_state.dados_bi_gerados = (tabela_realizado, tabela_bi)
        
        st.success("✅ Relatório processado com sucesso!")

    # Exibir botão de download se o relatório foi gerado
    if st.session_state.relatorio_gerado is not None:
        # Preparar o arquivo Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            st.session_state.relatorio_gerado.to_excel(writer, sheet_name='Consolidado', index=False)
            
            # Se também quiser incluir os dados do BI no mesmo arquivo Excel
            if st.session_state.dados_bi_gerados is not None:
                tabela_realizado, tabela_bi = st.session_state.dados_bi_gerados
                if tabela_realizado is not None:
                    tabela_realizado.to_excel(writer, sheet_name='Realizado', index=False)
                if tabela_bi is not None:
                    tabela_bi.to_excel(writer, sheet_name='BI Detalhado', index=False)
        
        # Botão de download na sidebar (persistirá após o processamento)
        with st.sidebar.container():
            st.download_button(
                label="📥 Baixar Relatório Excel",
                data=output.getvalue(),
                file_name=f"relatorio_beneficios_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

    # Mostrar status dos uploads
    st.subheader("📋 Status dos Arquivos")
    st.write(f"Arquivo Realizado: {'✅' if realizado else '❌'}")
    st.write(f"Arquivo Orçado: {'✅' if orcado else '❌'}")
    st.write(f"Arquivo BI Detalhado: {'✅' if bi_detalhado else '❌'}")

if st.session_state.relatorio_gerado is not None and st.session_state.dados_bi_gerados is not None:
    
    # Recuperar os dados do session_state
    realizado_vs_orcado = st.session_state.relatorio_gerado
    tabela_realizado, tabela_bi = st.session_state.dados_bi_gerados
    
    # Criar as 3 abas
    tab1, tab2, tab3 = st.tabs([
        "📊 COMPARAÇÃO BI VS DETALHADO", 
        "📈 COMPARAÇÃO REALIZADO VS PREVISTO", 
        "📋 RESUMO RELATÓRIO DETALHADO"
    ])

    with tab1:
        st.header("📊 COMPARAÇÃO BI VS RATEIO")
        ut.exibir_painel_comparacao(tabela_realizado, tabela_bi)
        
    
    with tab2:
        st.header("📈 COMPARAÇÃO REALIZADO VS ORCADO")
        
        beneficio_selecionado = st.selectbox(
                    "Selecione o benefício para filtrar o comparativo:",
                    ["Vale Alimentação", "Assistência Médica", "Assistência Odontológica", "Seguro de Vida"],
                    key="comparativo_benefit_filter"
                )
        ut.exibir_comparativo_filial(realizado_vs_orcado, tabela_bi, beneficio_selecionado)

    
    with tab3:
        st.header("📋 RESUMO RELATÓRIO DETALHADO")
        ut.exibir_resumo_colaboradores(realizado_vs_orcado)
        
else:
    # Mensagem inicial quando nenhum arquivo foi carregado ou processamento não foi iniciado
    st.info("👈 Faça o upload dos 3 arquivos Excel no sidebar e clique em 'Processar Relatório' para visualizar os painéis.")
    
    if not todos_arquivos_carregados:
        st.warning("⚠️ É necessário carregar todos os 3 arquivos Excel para habilitar o processamento.")
    
    # Mostrar informações adicionais
    text = """
        ## 🔎 Guia de Colunas Necessárias
        > 🚀 **Nova funcionalidade:**  
        > Não é mais necessário enviar um arquivo separado com o nome dos colaboradores.  
        > **Agora, é obrigatório que a coluna** `NOMETITULAR` **esteja presente em todas as abas listadas abaixo.**
        

        | **Aba (CHAVE)** | **Colunas Obrigatórias**                                                                                                                                     |
        |-----------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|
        | **UNIMED**      | `CPFTITULAR`, `CPFBENEFICIARIO`, `NOMETITULAR`, `CCFORMATADO`, `FILIAL`, `VALOR`, `406`                                                               |
        | **CLIN**        | `CPFTITULAR`, `CCFORMATADO`, `NOMETITULAR`, `FILIAL`, `CPFBENEFICIARIO`, `VALOR`, `441`, `442`                                                         |
        | **VA**          | `CPFTITULAR`, `FILIAL`, `CCFORMATADO`, `NOMETITULAR`, `VALOR`, `424`                                                                                   |
        | **SV**          | `CCFORMATADO`, `CPFTITULAR`, `NOMETITULAR`, `FILIAL`, `VALOR`                                                                                           |
        | **SV2**         | `CPFTITULAR`, `CCFORMATADO`, `NOMETITULAR`, `VALOR`, `FILIAL`  
        
        *(SV2 obrigatório apenas quando **modo EDNALDO = DESMARCADO**)*

        ---

        **Como usar:**  
        1. Selecione o modo **EDNALDO** (marcado/desmarcado).  
        2. Faça upload da sua planilha contendo as abas acima.  
        3. Verifique no helper se todas as colunas necessárias estão presentes em cada aba.  
        4. Execute o processamento.

        """
    


    st.markdown(text)
