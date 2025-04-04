import streamlit as st
import pandas as pd
import unicodedata
import re
from datetime import datetime
import io
import os
import numpy as np
import time
from streamlit.errors import NoSessionContext

from main import ( process_report
)

st.set_page_config(
    page_title="Processador de Relatórios de Benefícios",
    page_icon="📊",
    layout="centered"
)



def main():
    if 'processing_completed_time' not in st.session_state:
        st.session_state.processing_completed_time = None
    
    if 'processing_started' not in st.session_state:
        st.session_state.processing_started = False
        
    if 'result_df' not in st.session_state:
        st.session_state.result_df = None
        
    if 'colaboradores_df' not in st.session_state:
        st.session_state.colaboradores_df = None

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
    
    with st.sidebar:

        upload_container = st.container()
        
        with upload_container:
            st.header("Upload de Arquivos")
            st.subheader("Carregar arquivo de benefícios")
            beneficios_file = st.file_uploader(
                type=["xlsx"],
                help="Arquivo Excel contendo planilhas com dados de benefícios",
                label_visibility="collapsed",
                label="Carregar arquivo de beneficios"
                )

            st.subheader("Carregar arquivo com o orçamento")
            recorrentes_file = st.file_uploader(
                label= "Carregar arquivo com o orçamento",
                label_visibility="collapsed",
                type=["xlsx"],
                help="Arquivo Excel contendo dados de recorrentes"
            )
            
            st.subheader("Carregar arquivo de colaboradores (opcional)")
            colaboradores_file = st.file_uploader(
                label="Carregar arquivo com nomes dos colaboradores",
                label_visibility="collapsed",
                type=["xlsx", "csv"],
                help="Arquivo contendo CPF e NOME dos colaboradores (opcional)"
            )
        
            st.subheader("Opções de Processamento")

            month_mapping = {
                'Janeiro': '01', 
                'Fevereiro': '02', 
                'Março': '03', 
                'Abril': '04', 
                'Maio': '05', 
                'Junho': '06',
                'Julho': '07', 
                'Agosto': '08', 
                'Setembro': '09', 
                'Outubro': '10', 
                'Novembro': '11', 
                'Dezembro': '12'
            }
            
            mes_atual = int(datetime.now().strftime('%m'))
            mes_default = (mes_atual - 1) % 12
            if mes_default == 0:
                mes_default = 12
            
            month_names = list(month_mapping.keys())
            default_month = month_names[mes_default-1]
            
            selected_month = st.selectbox(
                "Selecione o mês de análise:",
                options=month_names,
                index=month_names.index(default_month)
            )
     
            ednaldo_mode = st.checkbox("Usar modo Ednaldo", value=False, 
                                    help="Ativa o processamento com regras específicas do modo Ednaldo")
        
        process_button = st.button("Processar Dados", type="primary", use_container_width=True)
    
    result_df = None
    
    progress_container = st.empty()
    status_container = st.empty()
    success_container = st.empty()
    
    result_df = st.session_state.result_df
    
    if colaboradores_file is not None and st.session_state.colaboradores_df is None:
        try:
            if colaboradores_file.name.endswith('.csv'):
                colaboradores_df = pd.read_csv(colaboradores_file)
            else:
                colaboradores_df = pd.read_excel(colaboradores_file)
            
            colaboradores_df.columns = [col.upper() for col in colaboradores_df.columns]
            
            if 'CPF' in colaboradores_df.columns and 'NOME' in colaboradores_df.columns:
                colaboradores_df['CPF'] = colaboradores_df['CPF'].astype(str).str.replace('[^0-9]', '', regex=True).str.zfill(11)
                st.session_state.colaboradores_df = colaboradores_df
                st.sidebar.success(f"Arquivo de colaboradores carregado com sucesso: {len(colaboradores_df)} registros.")
            else:
                required_cols = ['CPF', 'NOME']
                missing = [col for col in required_cols if col not in colaboradores_df.columns]
                st.sidebar.error(f"Colunas obrigatórias ausentes no arquivo de colaboradores: {', '.join(missing)}")
        except Exception as e:
            st.sidebar.error(f"Erro ao carregar arquivo de colaboradores: {str(e)}")
    
    if process_button:
        if beneficios_file is None or recorrentes_file is None:
            st.error("Por favor, carregue os dois arquivos necessários.")
        else:
            try:
                st.session_state.result_df = None
                
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
                    
                    result_df = process_report(
                        beneficios_file,
                        recorrentes_file,
                        ednaldo=ednaldo_mode,
                        mes_analise=month_mapping[selected_month],
                        progress_callback=update_progress
                    )
                    
                    if st.session_state.colaboradores_df is not None:
                        update_progress(95, "Adicionando nomes dos colaboradores...")
                        result_df = result_df.merge(
                            st.session_state.colaboradores_df[['CPF', 'NOME']],
                            left_on='CPFTITULAR',
                            right_on='CPF',
                            how='left'
                        )
                        if 'CPF' in result_df.columns:
                            result_df.drop(columns=['CPF'], inplace=True)
                
                st.session_state.result_df = result_df
                
                st.session_state.processing_completed_time = time.time()
                
                success_container.success(f"Processamento concluído! {len(result_df)} registros processados.")
                
                st.rerun()
                
            except Exception as e:
                progress_container.empty()
                status_container.empty()
                success_container.empty()
                st.session_state.processing_started = False
                st.session_state.processing_completed_time = None
                st.error(f"Erro durante o processamento: {str(e)}")
                st.exception(e) 
    
    if (st.session_state.processing_completed_time is not None and 
        time.time() - st.session_state.processing_completed_time >= 5):
        progress_container.empty()
        status_container.empty()
        success_container.empty()
    
    if result_df is not None:
        st.header("Resultados")
        
        tab1, tab2 = st.tabs(["Visão Geral", "Análise Detalhada"])
        
        with tab1:
            st.subheader("Resumo dos Benefícios")
            
            col1, col2 = st.columns(2)
            
            def format_currency(value):
                return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            
            numeric_columns = ['previsto_va', 'realizado_va', 'previsto_unimed', 'realizado_unimed', 
                               'previsto_clin', 'realizado_clin', 'previsto_sv', 'realizado_sv']
            
            for col in numeric_columns:
                result_df[col] = pd.to_numeric(result_df[col], errors='coerce').fillna(0)
            
            totais = {
                'Vale Alimentação': {
                    'Previsto': result_df['previsto_va'].sum(),
                    'Realizado': result_df['realizado_va'].sum(),
                    'Diferença': result_df['realizado_va'].sum() - result_df['previsto_va'].sum()
                },
                'Assistência Médica': {
                    'Previsto': result_df['previsto_unimed'].sum(),
                    'Realizado': result_df['realizado_unimed'].sum(),
                    'Diferença': result_df['realizado_unimed'].sum() - result_df['previsto_unimed'].sum()
                },
                'Assistência Odontológica': {
                    'Previsto': result_df['previsto_clin'].sum(),
                    'Realizado': result_df['realizado_clin'].sum(),
                    'Diferença': result_df['realizado_clin'].sum() - result_df['previsto_clin'].sum()
                },
                'Seguro de Vida': {
                    'Previsto': result_df['previsto_sv'].sum(),
                    'Realizado': result_df['realizado_sv'].sum(),
                    'Diferença': result_df['realizado_sv'].sum() - result_df['previsto_sv'].sum()
                },
                'Total Geral': {
                    'Previsto': result_df[['previsto_va', 'previsto_unimed', 'previsto_clin', 'previsto_sv']].sum().sum(),
                    'Realizado': result_df[['realizado_va', 'realizado_unimed', 'realizado_clin', 'realizado_sv']].sum().sum(),
                    'Diferença': result_df[['realizado_va', 'realizado_unimed', 'realizado_clin', 'realizado_sv']].sum().sum() - 
                                 result_df[['previsto_va', 'previsto_unimed', 'previsto_clin', 'previsto_sv']].sum().sum()
                }
            }
            
            totais_df = pd.DataFrame(totais).T
            totais_df['% Variação'] = (totais_df['Diferença'] / totais_df['Previsto'] * 100).fillna(0)
            
            def highlight_diff(val):
                if isinstance(val, (int, float)):
                    if val > 0:
                        return 'background-color: rgba(255, 0, 0, 0.1); color: darkred; font-weight: bold'
                    elif val < 0:
                        return 'background-color: rgba(0, 128, 0, 0.1); color: darkgreen; font-weight: bold'
                return ''
            
            def highlight_percent(val):
                if isinstance(val, (int, float)):
                    if val > 10:
                        return 'background-color: rgba(255, 0, 0, 0.2); color: darkred; font-weight: bold'
                    elif val > 5:
                        return 'background-color: rgba(255, 165, 0, 0.2); color: darkorange'
                    elif val < -10:
                        return 'background-color: rgba(0, 128, 0, 0.2); color: darkgreen; font-weight: bold'
                    elif val < -5:
                        return 'background-color: rgba(144, 238, 144, 0.2); color: green'
                return ''
            
            formatted_df = totais_df.copy()
            for col in ['Previsto', 'Realizado', 'Diferença']:
                formatted_df[col] = formatted_df[col].apply(format_currency)
            formatted_df['% Variação'] = formatted_df['% Variação'].apply(lambda x: f"{x:.2f}%")
            
            styled_df = totais_df.style\
                .format({'Previsto': format_currency, 
                         'Realizado': format_currency, 
                         'Diferença': format_currency,
                         '% Variação': '{:.2f}%'.format})\
                .applymap(highlight_diff, subset=['Diferença'])\
                .applymap(highlight_percent, subset=['% Variação'])
            
            st.write("Resumo por tipo de benefício:")
            st.dataframe(
                styled_df,
                use_container_width=True,
                height=240
            )
            
            st.subheader("Prévia do relatório")
            st.dataframe(result_df, use_container_width=True, hide_index= True)
        
        with tab2:
            st.subheader("Análise por Filial")
            
            detail_tab1, detail_tab2, detail_tab3 = st.tabs(["Comparativo Orçado vs Realizado", "Transferências Entre Filiais", "Detalhes por Benefício"])
            
            with detail_tab1:
                st.write("Comparativo de valores orçados vs realizados por filial:")
                
                result_df['previsto_filial'] = result_df['previsto_filial'].fillna('Não Informado')
                
                comparativo_filiais = []
                
                filiais_previstas = result_df['previsto_filial'].unique()
                
                for filial in filiais_previstas:
                    filial_df = result_df[result_df['previsto_filial'] == filial]
                    
                    previsto_va = filial_df['previsto_va'].sum()
                    previsto_unimed = filial_df['previsto_unimed'].sum()
                    previsto_clin = filial_df['previsto_clin'].sum()
                    previsto_sv = filial_df['previsto_sv'].sum()
                    total_previsto = previsto_va + previsto_unimed + previsto_clin + previsto_sv
                    
                    realizado_va = filial_df['realizado_va'].sum()
                    realizado_unimed = filial_df['realizado_unimed'].sum()
                    realizado_clin = filial_df['realizado_clin'].sum()
                    realizado_sv = filial_df['realizado_sv'].sum()
                    total_realizado = realizado_va + realizado_unimed + realizado_clin + realizado_sv
                    
                    diferenca = total_realizado - total_previsto
                    variacao_pct = (diferenca / total_previsto * 100) if total_previsto != 0 else 0
                    
                    comparativo_filiais.append({
                        'Filial': filial,
                        'Previsto': total_previsto,
                        'Realizado': total_realizado,
                        'Diferença': diferenca,
                        'Variação (%)': variacao_pct
                    })
                
                comparativo_df = pd.DataFrame(comparativo_filiais)
                comparativo_df = comparativo_df.sort_values(by='Filial')
                
                comparativo_display = comparativo_df.copy()
                comparativo_display['Previsto'] = comparativo_display['Previsto'].apply(format_currency)
                comparativo_display['Realizado'] = comparativo_display['Realizado'].apply(format_currency)
                comparativo_display['Diferença'] = comparativo_display['Diferença'].apply(format_currency)
                comparativo_display['Variação (%)'] = comparativo_display['Variação (%)'].apply(lambda x: f"{x:.2f}%")
                
                styled_comparativo = comparativo_df.style\
                    .format({'Previsto': format_currency, 
                             'Realizado': format_currency, 
                             'Diferença': format_currency,
                             'Variação (%)': '{:.2f}%'.format})\
                    .applymap(highlight_diff, subset=['Diferença'])\
                    .applymap(highlight_percent, subset=['Variação (%)'])
                
                st.dataframe(styled_comparativo, use_container_width=True)
                
            with detail_tab2:
                st.write("Análise de transferências entre filiais (Orçado vs Realizado):")
                
                beneficio_matriz = st.selectbox(
                    "Selecione o benefício para análise da matriz de transferências:",
                    ["Vale Alimentação", "Assistência Médica", "Assistência Odontológica", "Seguro de Vida"],
                    key="matriz_transferencia"
                )
                
                beneficio_map = {
                    "Vale Alimentação": ("previsto_va", "frealizado_va", "realizado_va"),
                    "Assistência Médica": ("previsto_unimed", "frealizado_un", "realizado_unimed"),
                    "Assistência Odontológica": ("previsto_clin", "frealizado_cl", "realizado_clin"),
                    "Seguro de Vida": ("previsto_sv", "frealizado_sv", "realizado_sv")
                }
                
                previsto_col, frealizado_col, realizado_col = beneficio_map[beneficio_matriz]
                
                df_valido = result_df.dropna(subset=['previsto_filial', frealizado_col])
                df_valido['previsto_filial'] = df_valido['previsto_filial'].astype(str)
                df_valido[frealizado_col] = df_valido[frealizado_col].astype(str)
                
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
                
                matriz_formatted = matriz_pivot.applymap(format_currency)
                
                def highlight_transfers(val):
                    if isinstance(val, (int, float)):
                        if val > 0.01:
                            if val > 1000:
                                return 'background-color: rgba(65, 105, 225, 0.3); color: darkblue; font-weight: bold'
                            elif val > 100:
                                return 'background-color: rgba(65, 105, 225, 0.2); color: darkblue'
                            else:
                                return 'background-color: rgba(65, 105, 225, 0.1); color: darkblue'
                    return ''
                
                styled_matriz = matriz_pivot.style\
                    .format(format_currency)\
                    .applymap(highlight_transfers)
                
                st.write(f"Matriz de transferências - {beneficio_matriz}")
                st.write("Linhas: Filial onde foi orçado | Colunas: Filial onde foi realizado")
                st.dataframe(styled_matriz, use_container_width=True)
                
                st.write("Interpretação: 00 são pessoas que não foram orçadas ou não foram realizadas.")
                
                st.markdown("---")
                st.subheader("Detalhamento de CPFs Transferidos")
                st.write("Visualize os CPFs que foram orçados em uma filial e realizados em outra:")
                
                beneficio_cpf = st.selectbox(
                    "Selecione o benefício para detalhamento de CPFs transferidos:",
                    ["Vale Alimentação", "Assistência Médica", "Assistência Odontológica", "Seguro de Vida"],
                    key="detalhe_cpf"
                )
                
                previsto_col_cpf, frealizado_col_cpf, realizado_col_cpf = beneficio_map[beneficio_cpf]
                
                df_valido_cpf = result_df.dropna(subset=['previsto_filial', frealizado_col_cpf])
                df_valido_cpf['previsto_filial'] = df_valido_cpf['previsto_filial'].astype(str)
                df_valido_cpf[frealizado_col_cpf] = df_valido_cpf[frealizado_col_cpf].astype(str)
                
                filiais_orcamento = sorted(df_valido_cpf['previsto_filial'].unique())
                filiais_realizacao = sorted(df_valido_cpf[frealizado_col_cpf].unique())
                
                col1, col2 = st.columns(2)
                with col1:
                    filial_origem = st.selectbox(
                        "Filial onde foi orçado:",
                        options=filiais_orcamento,
                        key=f"origem_{beneficio_cpf}"
                    )
                
                with col2:
                    filial_destino = st.selectbox(
                        "Filial onde foi realizado:",
                        options=filiais_realizacao,
                        key=f"destino_{beneficio_cpf}"
                    )
                
                if filial_origem != filial_destino:
                    cpfs_transferidos = df_valido_cpf[
                        (df_valido_cpf['previsto_filial'] == filial_origem) & 
                        (df_valido_cpf[frealizado_col_cpf] == filial_destino)
                    ]
                    
                    if not cpfs_transferidos.empty:
                        if 'cpf' in cpfs_transferidos.columns:
                            cpf_col = 'cpf'
                        elif 'CPFTITULAR' in cpfs_transferidos.columns:
                            cpf_col = 'CPFTITULAR'
                        else:
                            cpf_col = None
                            
                        if cpf_col:
                            if 'NOME' in cpfs_transferidos.columns:
                                colunas_display = [cpf_col, 'NOME', previsto_col_cpf, realizado_col_cpf]
                                colunas_rename = {
                                    cpf_col: 'CPF',
                                    'NOME': 'Nome Colaborador',
                                    previsto_col_cpf: 'Valor Orçado',
                                    realizado_col_cpf: 'Valor Realizado'
                                }
                            else:
                                colunas_display = [cpf_col, previsto_col_cpf, realizado_col_cpf]
                                colunas_rename = {
                                    cpf_col: 'CPF',
                                    previsto_col_cpf: 'Valor Orçado',
                                    realizado_col_cpf: 'Valor Realizado'
                                }
                            
                            display_df = cpfs_transferidos[colunas_display].copy()
                            display_df = display_df.rename(columns=colunas_rename)
                            
                            display_df['Valor Orçado'] = display_df['Valor Orçado'].apply(format_currency)
                            display_df['Valor Realizado'] = display_df['Valor Realizado'].apply(format_currency)
                            
                            st.write(f"CPFs orçados em **{filial_origem}** e realizados em **{filial_destino}**:")
                            st.dataframe(display_df, use_container_width=True, hide_index=True)
                            
                            total_orcado = cpfs_transferidos[previsto_col_cpf].sum()
                            total_realizado = cpfs_transferidos[realizado_col_cpf].sum()
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Total Orçado", format_currency(total_orcado))
                            with col2:
                                st.metric("Total Realizado", format_currency(total_realizado))
                        else:
                            st.warning("Dados de CPF não disponíveis no relatório. Verifique se existe uma coluna 'cpf' ou 'CPFTITULAR'.")
                    else:
                        st.info(f"Não foram encontrados CPFs orçados em {filial_origem} e realizados em {filial_destino}.")
                else:
                    st.info("Selecione filiais diferentes para visualizar as transferências.")
                
            with detail_tab3:
                st.write("Detalhes por tipo de benefício:")
                
                benefit_tabs = st.tabs(["Vale Alimentação", "Assistência Médica", "Assistência Odontológica", "Seguro de Vida"])
                
                with benefit_tabs[0]:
                    if 'frealizado_va' in result_df.columns:
                        st.subheader("Detalhamento - Vale Alimentação")
                        
                        result_df['frealizado_va'] = result_df['frealizado_va'].fillna('Não Informado')
                        result_df['previsto_filial'] = result_df['previsto_filial'].fillna('Não Informado')
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("Por filial onde foi Orçado:")
                            va_prev_group = result_df.groupby('previsto_filial')['previsto_va'].sum().reset_index()
                            va_prev_group = va_prev_group.rename(columns={
                                'previsto_filial': 'Filial',
                                'previsto_va': 'Valor Orçado'
                            })
                            va_prev_group = va_prev_group.sort_values(by='Filial')
                            
                            styled_va_prev = va_prev_group.style\
                                .format({'Valor Orçado': format_currency})
                            
                            st.dataframe(styled_va_prev, use_container_width=True, hide_index=True)
                        
                        with col2:
                            st.write("Por filial onde foi Realizado:")
                            va_real_group = result_df.groupby('frealizado_va')['realizado_va'].sum().reset_index()
                            va_real_group = va_real_group.rename(columns={
                                'frealizado_va': 'Filial',
                                'realizado_va': 'Valor Realizado'
                            })
                            va_real_group = va_real_group.sort_values(by='Filial')
                            
                            styled_va_real = va_real_group.style\
                                .format({'Valor Realizado': format_currency})
                            
                            st.dataframe(styled_va_real, use_container_width=True, hide_index=True)
                
                with benefit_tabs[1]:
                    if 'frealizado_un' in result_df.columns:
                        st.subheader("Detalhamento - Assistência Médica")
                        
                        result_df['frealizado_un'] = result_df['frealizado_un'].fillna('Não Informado')
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("Por filial onde foi Orçado:")
                            un_prev_group = result_df.groupby('previsto_filial')['previsto_unimed'].sum().reset_index()
                            un_prev_group = un_prev_group.rename(columns={
                                'previsto_filial': 'Filial',
                                'previsto_unimed': 'Valor Orçado'
                            })
                            un_prev_group = un_prev_group.sort_values(by='Filial')
                            un_prev_group['Valor Orçado'] = un_prev_group['Valor Orçado'].apply(format_currency)
                            st.dataframe(un_prev_group, use_container_width=True, hide_index=True)
                        
                        with col2:
                            st.write("Por filial onde foi Realizado:")
                            un_real_group = result_df.groupby('frealizado_un')['realizado_unimed'].sum().reset_index()
                            un_real_group = un_real_group.rename(columns={
                                'frealizado_un': 'Filial',
                                'realizado_unimed': 'Valor Realizado'
                            })
                            un_real_group = un_real_group.sort_values(by='Filial')
                            un_real_group['Valor Realizado'] = un_real_group['Valor Realizado'].apply(format_currency)
                            st.dataframe(un_real_group, use_container_width=True, hide_index=True)
                
                with benefit_tabs[2]:
                    if 'frealizado_cl' in result_df.columns:
                        st.subheader("Detalhamento - Assistência Odontológica")
                        
                        result_df['frealizado_cl'] = result_df['frealizado_cl'].fillna('Não Informado')
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("Por filial onde foi Orçado:")
                            cl_prev_group = result_df.groupby('previsto_filial')['previsto_clin'].sum().reset_index()
                            cl_prev_group = cl_prev_group.rename(columns={
                                'previsto_filial': 'Filial',
                                'previsto_clin': 'Valor Orçado'
                            })
                            cl_prev_group = cl_prev_group.sort_values(by='Filial')
                            cl_prev_group['Valor Orçado'] = cl_prev_group['Valor Orçado'].apply(format_currency)
                            st.dataframe(cl_prev_group, use_container_width=True, hide_index=True)
                        
                        with col2:
                            st.write("Por filial onde foi Realizado:")
                            cl_real_group = result_df.groupby('frealizado_cl')['realizado_clin'].sum().reset_index()
                            cl_real_group = cl_real_group.rename(columns={
                                'frealizado_cl': 'Filial',
                                'realizado_clin': 'Valor Realizado'
                            })
                            cl_real_group = cl_real_group.sort_values(by='Filial')
                            cl_real_group['Valor Realizado'] = cl_real_group['Valor Realizado'].apply(format_currency)
                            st.dataframe(cl_real_group, use_container_width=True, hide_index=True)
                
                with benefit_tabs[3]:
                    if 'frealizado_sv' in result_df.columns:
                        st.subheader("Detalhamento - Seguro de Vida")
                        
                        result_df['frealizado_sv'] = result_df['frealizado_sv'].fillna('Não Informado')
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("Por filial onde foi Orçado:")
                            sv_prev_group = result_df.groupby('previsto_filial')['previsto_sv'].sum().reset_index()
                            sv_prev_group = sv_prev_group.rename(columns={
                                'previsto_filial': 'Filial',
                                'previsto_sv': 'Valor Orçado'
                            })
                            sv_prev_group = sv_prev_group.sort_values(by='Filial')
                            sv_prev_group['Valor Orçado'] = sv_prev_group['Valor Orçado'].apply(format_currency)
                            st.dataframe(sv_prev_group, use_container_width=True, hide_index=True)
                        
                        with col2:
                            st.write("Por filial onde foi Realizado:")
                            sv_real_group = result_df.groupby('frealizado_sv')['realizado_sv'].sum().reset_index()
                            sv_real_group = sv_real_group.rename(columns={
                                'frealizado_sv': 'Filial',
                                'realizado_sv': 'Valor Realizado'
                            })
                            sv_real_group = sv_real_group.sort_values(by='Filial')
                            sv_real_group['Valor Realizado'] = sv_real_group['Valor Realizado'].apply(format_currency)
                            st.dataframe(sv_real_group, use_container_width=True, hide_index=True)
        
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
    
    if not st.session_state.processing_started and st.session_state.processing_completed_time is None:
        progress_container.empty()
        status_container.empty()
        success_container.empty()

if __name__ == "__main__":
    main()
