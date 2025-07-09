import streamlit as st
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:

    markdown_help = """
    ### Colunas e Padrões Esperados

    Antes de qualquer processamento ou limpeza interna (que inclui a conversão para maiúsculas, remoção de acentuação, espaços e pontuação), os arquivos devem ter as seguintes colunas com os **nomes exatos**:

    ---

    #### 1. Arquivos de Benefícios (Planilhas)

    ##### **Modo Ednaldo**

    **Planilha UNIMED:**
    - `CPFBENEFICIARIO` (contém o CPF do beneficiário)  
    - `VALOR` (valor calculado VALOR)  
    - `FILIAL` (identificação da filial)

    **Planilha VA:**
    - `CPFTITULAR` (identificador do titular)  
    - `VALOR` (valor calculado)  
    - `FILIAL` (filial)

    **Planilha CLIN:**
    - `CPFTITULAR` (deve existir para validação do CPF, mesmo que os dados principais venham de outra coluna)  
    - `CPFDOBENEFICIARIO` (contém o CPF do colaborador principal, para essa planilha ela seria a "chave" que relaciona com as demais)  
    - `VALOR` (valor calculado)  
    - `FILIAL` (filial)

    **Planilha SURA:**
    - `CPFTITULAR` (CPF do titular)  
    - `VALOR` (valor a ser considerado)  
    - `FILIAL` (filial)

    **Planilha BEMMAIS:**
    - `CPFTITULAR` (CPF do titular)  
    - `SINTRACAP` (valor para controle do Seguro de Vida)  
    - `FILIAL` (filial)

    ---

    ##### **Modo Dimitri**

    **Planilha UNIMED:**
    - `CPFDOBENEFICIARIO` (identifica o beneficiário)  
    - `VALOR` (valor calculado)  
    - `FILIAL` (filial)

    **Planilha VA:**
    - `CPFTITULAR` (CPF do titular)  
    - `VALOR` (valor calculado)  
    - `FILIAL` (filial)

    **Planilha CLIN:**
    - `CPFDOBENEFICIARIO` (identificação do beneficiário)  
    - `VALOR` (valor calculado)  
    - `FILIAL` (filial)

    **Planilha SV:**
    - `CPFTITULAR` (CPF do titular)  
    - `VALOR` (valor a ser considerado)  
    - `FILIAL` (filial)

    ---

    **Observação:**  
    Em **ambos os modos**, o relatório VALOR é consolidado a partir dos **CPFs (na forma de `CPFTITULAR`)**.  
    Assim, **pelo menos uma das planilhas precisa conter esta coluna**.  
    No modo **Ednaldo**, a planilha **CLIN** deve conter também a coluna `CPFTITULAR` para validação.

    ---

    #### 2. Arquivo de Recorrentes (Orçamento)

    O arquivo de recorrentes deve possuir as seguintes colunas (**nomes exatos**):

    - `CPF`  
    - `ANOMES`  
    (formado pelo ano concatenado com o número do mês, exemplo: `"202501"` para janeiro de 2025)  
    - `VALE ALIMENTACAO`  
    - `ASSISTENCIA MEDICA`  
    - `SEGURO DE VIDA`  
    - `ASSISTENCIA ODONTOLOGICA`  
    - `FILIAL`
    """
except ImportError:
    # Fallback if import fails
    markdown_help = """
    ### Informação de Ajuda
    
    A informação detalhada sobre colunas e padrões esperados não está disponível no momento.
    Por favor, retorne à página principal para mais informações.
    """

st.set_page_config(
    page_title="Guia do Processador de Relatórios", 
    page_icon="❓",
    layout="centered"
)

st.title("Guia Processador de Relatórios de Benefícios")

st.markdown("""
Esta página contém informações detalhadas sobre as colunas e formatos esperados
para os arquivos de benefícios e orçamento.
""")

st.markdown(markdown_help)

st.divider()

st.button("Voltar para a página principal", on_click=lambda: st.switch_page("app.py"))
