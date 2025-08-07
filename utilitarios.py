import pandas as pd
import streamlit as st
import numpy as np


mapeamento_beneficios = {
    'VA': 'va',
    'UNIMED': 'unimed',
    'CLIN': 'clin',
    'SV': 'sv'
}

nomes_beneficios = {
    "VA": "Vale Alimentação", 
    "UNIMED": "Unimed", 
    "CLIN": "Clínica", 
    "SV": "Seguro de Vida"
}

def format_currency(value):
    """
    Format a value as Brazilian currency (R$).
    Handles numeric values, strings, None and NaN.
    """
    if pd.isna(value) or value is None:
        return "R$ 0,00"
    
    try:
        # Try to convert to float if it's not already a number
        if not isinstance(value, (int, float)):
            value = float(value)
        
        # Format with Brazilian currency conventions
        return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (ValueError, TypeError):
        # If conversion fails, return the original value
        return str(value)


############################ ANNA TAB 1

def comparar_dados(df_resultado, bi_resultado):
    """
    Compara dados entre os dataframes df_resultado e bi_resultado
    Retorna um dicionário com comparações por filial e por centro de custo
    """
    resultados_comparacao = {}

    # Processar comparação por filial
    for beneficio_bi, beneficio_df in mapeamento_beneficios.items():
        bi_por_filial = (
            bi_resultado[bi_resultado['BENEFICIO'] == beneficio_bi]
            .groupby('FILIAL')['VALOR']
            .sum()
            .reset_index()
        )
        bi_por_filial.rename(
            columns={'VALOR': f'valor_bi_{beneficio_df}'},
            inplace=True
        )

        coluna_df_valor = f'realizado_{beneficio_df}'
        coluna_df_filial = f'filial_realizada_{beneficio_df}'
        df_por_filial = (
            df_resultado
            .groupby(coluna_df_filial)[coluna_df_valor]
            .sum()
            .reset_index()
        )
        df_por_filial.rename(
            columns={coluna_df_filial: 'FILIAL', coluna_df_valor: f'valor_df_{beneficio_df}'},
            inplace=True
        )

        comparacao_filial = pd.merge(
            bi_por_filial,
            df_por_filial,
            on='FILIAL',
            how='outer'
        ).fillna(0)

        comparacao_filial[f'diferenca_{beneficio_df}'] = (
            comparacao_filial[f'valor_bi_{beneficio_df}']
            - comparacao_filial[f'valor_df_{beneficio_df}']
        )

        resultados_comparacao[f'{beneficio_bi}_por_filial'] = comparacao_filial

    # Processar comparação por centro de custo
    for beneficio_bi, beneficio_df in mapeamento_beneficios.items():
        bi_por_cc = (
            bi_resultado[bi_resultado['BENEFICIO'] == beneficio_bi]
            .groupby('CC')['VALOR']
            .sum()
            .reset_index()
        )
        bi_por_cc.rename(
            columns={'VALOR': f'valor_bi_{beneficio_df}'},
            inplace=True
        )

        coluna_df_valor = f'realizado_{beneficio_df}'
        coluna_df_cc = f'CC_realizado_{beneficio_df}'
        df_por_cc = (
            df_resultado
            .groupby(coluna_df_cc)[coluna_df_valor]
            .sum()
            .reset_index()
        )
        df_por_cc.rename(
            columns={coluna_df_cc: 'CC', coluna_df_valor: f'valor_df_{beneficio_df}'},
            inplace=True
        )

        comparacao_cc = pd.merge(
            bi_por_cc,
            df_por_cc,
            on='CC',
            how='outer'
        ).fillna(0)

        comparacao_cc[f'(bi-realizado)_{beneficio_df}'] = (
            comparacao_cc[f'valor_bi_{beneficio_df}']
            - comparacao_cc[f'valor_df_{beneficio_df}']
        )

        resultados_comparacao[f'{beneficio_bi}_por_cc'] = comparacao_cc

    return resultados_comparacao

def formatar_moeda_dataframe(df, colunas_moeda=None):
    """
    Formata colunas especificadas do dataframe como moeda brasileira (R$)
    Retorna uma cópia do dataframe com colunas formatadas
    """
    df_formatado = df.copy()

    if colunas_moeda is None:
        colunas_moeda = [
            col for col in df_formatado.columns
            if any(prefix in col for prefix in [
                'valor_bi_', 'valor_df_', 'diferenca_', '(bi-realizado)_'
            ])
        ]

    for coluna in colunas_moeda:
        if coluna in df_formatado.columns:
            df_formatado[coluna] = df_formatado[coluna].apply(
                lambda x: f"R$ {x:,.2f}".replace(',', '_')
                                          .replace('.', ',')
                                          .replace('_', '.')
            )

    return df_formatado

def exibir_painel_comparacao(df_resultado, bi_resultado):
    """
    Exibe painel de comparação entre dados de rateio e BI no Streamlit
    """
    st.header("Comparação entre Rateio e BI")

    resultados = comparar_dados(df_resultado, bi_resultado)

    # Seleção do benefício
    beneficio_selecionado = st.selectbox(
        "Selecione o benefício",
        options=list(nomes_beneficios.keys()),
        format_func=lambda x: nomes_beneficios[x]
    )

    # Exibir comparação por filial
    st.subheader(f"Comparação por Filial - {nomes_beneficios[beneficio_selecionado]}")
    df_filial = resultados[f"{beneficio_selecionado}_por_filial"]
    df_filial_formatado = formatar_moeda_dataframe(df_filial)
    st.dataframe(df_filial_formatado, use_container_width=True)

    # Expansível para seleção de filial e visualização de centro de custo
    with st.expander("Selecionar Filial para ver Centro de Custos"):
        filiais = resultados[f"{beneficio_selecionado}_por_filial"]["FILIAL"].unique().tolist()
        filial_escolhida = st.selectbox("Selecione a Filial", options=filiais)

        comparacao_cc = resultados[f"{beneficio_selecionado}_por_cc"]

        # Filtrar centros de custo existentes no BI
        ccs_bi = (
            bi_resultado
            [(bi_resultado['BENEFICIO'] == beneficio_selecionado)
             & (bi_resultado['FILIAL'] == filial_escolhida)]
            ['CC'].dropna().unique().tolist()
        )

        # Filtrar centros de custo no dataframe de resultado
        beneficio_df = mapeamento_beneficios[beneficio_selecionado]
        coluna_filial = f'filial_realizada_{beneficio_df}'
        coluna_cc = f'CC_realizado_{beneficio_df}'

        ccs_df = []
        if coluna_filial in df_resultado.columns and coluna_cc in df_resultado.columns:
            ccs_df = (
                df_resultado
                [(df_resultado[coluna_filial] == filial_escolhida)
                 & df_resultado[coluna_cc].notna()]
                [coluna_cc].unique().tolist()
            )

        todos_ccs = list(set(ccs_bi + ccs_df))
        filtragem_cc = comparacao_cc[comparacao_cc['CC'].isin(todos_ccs)]

        if not filtragem_cc.empty:
            st.subheader(f"Centros de Custo de {filial_escolhida} - {nomes_beneficios[beneficio_selecionado]}")
            df_cc_formatado = formatar_moeda_dataframe(filtragem_cc)
            st.dataframe(df_cc_formatado, use_container_width=True)
        else:
            st.info(
                f"Não há centros de custo para a filial {filial_escolhida} no benefício {nomes_beneficios[beneficio_selecionado]}"
            )

############################# ANNA TAB 2

def processar_comparativo_filial(df_resultado, df_bi=None, beneficio_selecionado=None):
    # copia o DataFrame de entrada
    df = df_resultado.copy()
    df.loc[:, 'previsto_filial'] = df['previsto_filial'].fillna('00')

    # mapeamento dos benefícios
    mapeamento_beneficio = {
        "Vale Alimentação": ('va', 'previsto_va', 'realizado_va', 'filial_realizada_va', 'VA'),
        "Assistência Médica": ('unimed', 'previsto_unimed', 'realizado_unimed', 'filial_realizada_unimed', 'UNIMED'),
        "Assistência Odontológica": ('clin', 'previsto_clin', 'realizado_clin', 'filial_realizada_clin', 'CLIN'),
        "Seguro de Vida": ('sv', 'previsto_sv', 'realizado_sv', 'filial_realizada_sv', 'SV')
    }

    # obtém as colunas a partir do benefício selecionado
    tipo_beneficio, coluna_prevista, coluna_realizado, coluna_filial_realizada, nome_bi_beneficio = \
        mapeamento_beneficio[beneficio_selecionado]

    lista_comparativo_filiais = []

    # coleta todas as filiais a partir dos dados de previsto e realizados
    todas_filiais = set(df['previsto_filial'].unique())
    todas_filiais.update(df[coluna_filial_realizada].unique())
    if df_bi is not None:
        filiais_bi = df_bi[df_bi['BENEFICIO'] == nome_bi_beneficio]['FILIAL'].unique()
        todas_filiais.update(filiais_bi)
    todas_filiais = sorted(todas_filiais)

    for filial in todas_filiais:
        # soma orçado
        df_previsto_filial = df[df['previsto_filial'] == filial]
        soma_previsto = df_previsto_filial[coluna_prevista].sum()
        qtd_previsto = df_previsto_filial[df_previsto_filial[coluna_prevista] > 0].shape[0]

        # soma realizado (prefere dados do BI, se existir)
        if df_bi is not None:
            soma_realizado = df_bi[
                (df_bi['FILIAL'] == filial) & (df_bi['BENEFICIO'] == nome_bi_beneficio)
            ]['VALOR'].sum()
        else:
            df_realizado_filial = df[df[coluna_filial_realizada] == filial]
            soma_realizado = df_realizado_filial[coluna_realizado].sum()

        # quantidade realizado
        df_realizado_filial = df[df[coluna_filial_realizada] == filial]
        qtd_realizado = df_realizado_filial[df_realizado_filial[coluna_realizado] > 0].shape[0]

        # diferença e variação percentual
        diferenca = soma_realizado - soma_previsto
        variacao_pct = (soma_realizado / soma_previsto * 100) if soma_previsto != 0 else 0

        lista_comparativo_filiais.append({
            'Filial': filial,
            'Orçado': soma_previsto,
            'Qtd. Orçado': qtd_previsto,
            'Realizado': soma_realizado,
            'Qtd. Realizado': qtd_realizado,
            'Variação (%)': variacao_pct,
            'Diferença': diferenca,
            'Justificativa': None
        })

    # monta DataFrame final e ordena por filial
    df_comparativo = pd.DataFrame(lista_comparativo_filiais).sort_values(by='Filial')

    # formata as colunas de valor como moeda brasileira
    colunas_monetarias = ['Orçado', 'Realizado', 'Diferença']
    for col in colunas_monetarias:
        df_comparativo[col] = df_comparativo[col].apply(
            lambda x: f"R$ {x:,.2f}"
                .replace(",", "X")  # temporário: vira milhar
                .replace(".", ",")  # ponto decimal → vírgula
                .replace("X", ".")  # milhar volta a ponto
        )

    # exibe no Streamlit
    return df_comparativo

def exibir_comparativo_filial(df_resultado, df_bi, beneficio_selecionado):
    
    st.dataframe(processar_comparativo_filial(df_resultado, df_bi, beneficio_selecionado))

############################# ANNA TAB 3

def categorizar_colaboradores_por_filial(dados_resultado, filial_selecionada):
    df = dados_resultado.copy()
    for coluna in ['previsto_filial', 'filial_realizada_va', 'filial_realizada_unimed', 
                   'filial_realizada_clin', 'filial_realizada_sv']:
        if coluna in df.columns:
            df.loc[:, coluna] = df[coluna].astype(str).fillna('00')

    beneficios = [
        ('Vale Alimentação', 'previsto_va', 'realizado_va', 'filial_realizada_va'),
        ('Assistência Médica', 'previsto_unimed', 'realizado_unimed', 'filial_realizada_unimed'),
        ('Assistência Odontológica', 'previsto_clin', 'realizado_clin', 'filial_realizada_clin'),
        ('Seguro de Vida', 'previsto_sv', 'realizado_sv', 'filial_realizada_sv')
    ]

    desligados = {}
    contratados = {}
    transferidos = {}

    for nome_beneficio, col_previsto, col_realizado, col_filial_real in beneficios:
        if col_filial_real not in df.columns:
            continue

        df_desligados = df[
            (df['previsto_filial'] == filial_selecionada) &
            (df[col_filial_real] == '00') &
            (df[col_previsto] > 0)
        ]

        df_contratados = df[
            (df['previsto_filial'] == '00') &
            (df[col_filial_real] == filial_selecionada) &
            (df[col_realizado] > 0)
        ]

        df_transferidos_entrada = df[
            (df['previsto_filial'] != filial_selecionada) &
            (df[col_filial_real] == filial_selecionada) &
            (df['previsto_filial'] != '00') &
            (df[col_realizado] > 0)
        ]
        if not df_transferidos_entrada.empty:
            df_transferidos_entrada = df_transferidos_entrada.copy()
            df_transferidos_entrada[col_previsto] = 0
            df_transferidos_entrada['filial_orcada'] = df_transferidos_entrada['previsto_filial']
            df_transferidos_entrada['filial_transferida'] = filial_selecionada

        df_transferidos_saida = df[
            (df['previsto_filial'] == filial_selecionada) &
            (df[col_filial_real] != filial_selecionada) &
            (df[col_filial_real] != '00') &
            (df[col_previsto] > 0)
        ]
        if not df_transferidos_saida.empty:
            df_transferidos_saida = df_transferidos_saida.copy()
            df_transferidos_saida[col_realizado] = 0
            df_transferidos_saida['filial_orcada'] = filial_selecionada
            df_transferidos_saida['filial_transferida'] = df_transferidos_saida[col_filial_real]

        df_transferidos = pd.concat([df_transferidos_entrada, df_transferidos_saida], ignore_index=True)

        desligados[nome_beneficio] = df_desligados
        contratados[nome_beneficio] = df_contratados
        transferidos[nome_beneficio] = df_transferidos

    return desligados, contratados, transferidos

def exibir_tabela_colaboradores(df, col_previsto, col_realizado, col_filial_destino=None):
    if df.empty:
        st.info("Não há dados para exibir.")
        return

    coluna_cpf = next((col for col in ['CPF', 'CPFTITULAR'] if col in df.columns), None)
    if not coluna_cpf:
        st.warning("Dados de CPF não disponíveis.")
        return

    colunas_exibicao = [coluna_cpf]
    if 'NOMETITULAR' in df.columns:
        colunas_exibicao.append('NOMETITULAR')
    colunas_exibicao.extend([col_previsto, col_realizado])
    if col_filial_destino:
        colunas_exibicao.append(col_filial_destino)

    df_exibicao = df[colunas_exibicao].copy()
    renomear = {
        coluna_cpf: 'CPF',
        col_previsto: 'Valor Orçado',
        col_realizado: 'Valor Realizado'
    }
    if 'NOMETITULAR' in df_exibicao.columns:
        renomear['NOMETITULAR'] = 'Nome Colaborador'
    if col_filial_destino:
        renomear[col_filial_destino] = 'Filial Realizada'

    df_exibicao = df_exibicao.rename(columns=renomear)
    df_exibicao['Valor Orçado'] = df_exibicao['Valor Orçado'].apply(format_currency)
    df_exibicao['Valor Realizado'] = df_exibicao['Valor Realizado'].apply(format_currency)

    st.dataframe(df_exibicao, use_container_width=True, hide_index=True)

    total_orcado = df[col_previsto].sum()
    total_realizado = df[col_realizado].sum()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Orçado", format_currency(total_orcado))
    with col2:
        st.metric("Total Realizado", format_currency(total_realizado))

def exibir_categoria_colaboradores(dados_categoria, mapa_beneficios, titulo_categoria, descricao_categoria):
    st.subheader(titulo_categoria)
    st.markdown(descricao_categoria)

    abas = st.tabs(list(mapa_beneficios.keys()))
    for i, (nome_beneficio, colunas) in enumerate(mapa_beneficios.items()):
        with abas[i]:
            col_previsto, col_realizado, col_filial = colunas
            if 'Transferidos' in titulo_categoria:
                exibir_tabela_colaboradores(dados_categoria[nome_beneficio], col_previsto, col_realizado, col_filial)
            else:
                exibir_tabela_colaboradores(dados_categoria[nome_beneficio], col_previsto, col_realizado)

def exibir_resumo_colaboradores(dados_resultado):
    st.write("Selecione uma filial para visualizar o resumo do relatório:")

    filiais = sorted([f for f in dados_resultado['previsto_filial'].unique() if f != '00' and pd.notna(f)])

    if not filiais:
        st.warning("Não foram encontradas filiais válidas no relatório.")
        return

    filial_selecionada = st.selectbox(
        "Filial:",
        options=filiais,
        key="seletor_resumo_filial"
    )

    if not filial_selecionada:
        st.info("Selecione uma filial para visualizar os dados.")
        return

    desligados, contratados, transferidos = categorizar_colaboradores_por_filial(dados_resultado, filial_selecionada)

    mapa_beneficios = {
        'Vale Alimentação': ('previsto_va', 'realizado_va', 'filial_realizada_va'),
        'Assistência Médica': ('previsto_unimed', 'realizado_unimed', 'filial_realizada_unimed'),
        'Assistência Odontológica': ('previsto_clin', 'realizado_clin', 'filial_realizada_clin'),
        'Seguro de Vida': ('previsto_sv', 'realizado_sv', 'filial_realizada_sv')
    }

    exibir_categoria_colaboradores(
        desligados,
        mapa_beneficios,
        f"1. Colaboradores Desligados - Filial {filial_selecionada}",
        "Colaboradores que foram orçados na filial selecionada mas não realizados (filial realizada = 00)"
    )

    exibir_categoria_colaboradores(
        contratados,
        mapa_beneficios,
        f"2. Colaboradores Contratados - Filial {filial_selecionada}",
        "Colaboradores que não foram orçados (filial orçada = 00) mas foram realizados na filial selecionada"
    )

    exibir_categoria_colaboradores(
        transferidos,
        mapa_beneficios,
        f"3. Colaboradores Transferidos - Filial {filial_selecionada}",
        "Colaboradores que foram orçados na filial selecionada mas realizados em outra filial"
    )



############################# lucas aqui 


def analise_folha_por_natureza(data_folha):
    """
    Função para análise da folha de pagamento por natureza
    
    Args:
        data_folha (pd.DataFrame): DataFrame com os dados da folha
    """
    
    # Lista das naturezas disponíveis
    naturezas = ['13º SALARIO', 'FERIAS', 'FGTS', 'INSS',
                'ADICIONAL TEMPO DE SERVICO', 'GRATIFICACOES', 'SALARIOS',
                'HORAS EXTRAS', 'ADCIONAL NOTURNO', 'JOVEM APRENDIZ',
                'SERVICO DE AUTONOMOS']
    
    st.title("Análise da Folha de Pagamento por Natureza")
    
    # Dropdown para seleção da natureza
    natureza_selecionada = st.selectbox(
        "Selecione a natureza para análise:",
        naturezas,
        index=0
    )
    
    if natureza_selecionada:
        # Filtrar o dataframe pela natureza selecionada usando a coluna CONTA unificada
        df_filtrado = data_folha[
            (data_folha['CONTA'] == natureza_selecionada)
        ].copy()
        
        if not df_filtrado.empty:
            # Preparar dados orçados
            orcado = df_filtrado.groupby('FILIAL_orcado').agg({
                'VALOR_orcado': lambda x: x[x.notna() & (x != 0)].sum(),
                'MATRICULA': lambda x: x[df_filtrado.loc[x.index, 'VALOR_orcado'].notna() & 
                                      (df_filtrado.loc[x.index, 'VALOR_orcado'] != 0)].nunique()
            }).reset_index()
            orcado.columns = ['FILIAL', 'VALOR_ORCADO', 'QT_ORCADO']
            
            # Preparar dados realizados
            realizado = df_filtrado.groupby('FILIAL_realizado').agg({
                'VALOR_realizado': lambda x: x[x.notna() & (x != 0)].sum(),
                'MATRICULA': lambda x: x[df_filtrado.loc[x.index, 'VALOR_realizado'].notna() & 
                                       (df_filtrado.loc[x.index, 'VALOR_realizado'] != 0)].nunique()
            }).reset_index()
            realizado.columns = ['FILIAL', 'VALOR_REALIZADO', 'QT_REALIZADO']
            
            # Merge dos dados
            resultado = pd.merge(orcado, realizado, on='FILIAL', how='outer')
            
            # Preencher valores NaN com 0
            resultado = resultado.fillna(0)
            
            # Calcular % de variação
            resultado['% VARIACAO'] = np.where(
                resultado['VALOR_ORCADO'] != 0,
                ((resultado['VALOR_REALIZADO'] - resultado['VALOR_ORCADO']) / resultado['VALOR_ORCADO'] * 100).round(2),
                np.where(resultado['VALOR_REALIZADO'] != 0, 100.0, 0.0)
            )
            
            # Reordenar colunas conforme solicitado
            resultado = resultado[['FILIAL', 'VALOR_ORCADO', 'QT_ORCADO', 'VALOR_REALIZADO', 'QT_REALIZADO', '% VARIACAO']]
            
            # Calcular totais
            tot_orcado = format_currency(resultado['VALOR_ORCADO'].sum())
            tot_realizado = format_currency(resultado['VALOR_REALIZADO'].sum())
            
            # Exibir métricas
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Orçado", f"{tot_orcado}")
            with col2:
                st.metric("Total Realizado", f"{tot_realizado}")
            
            # Formatizar valores para exibição
            resultado['VALOR_ORCADO'] = resultado['VALOR_ORCADO'].apply(format_currency)
            resultado['VALOR_REALIZADO'] = resultado['VALOR_REALIZADO'].apply(format_currency)
            
            # Exibir tabela
            st.subheader(f"Análise por Filial - {natureza_selecionada}")
            st.dataframe(
                resultado[resultado['FILIAL'] != '00'],
                use_container_width=True,
                hide_index=True
            )
                
        else:
            st.warning(f"Nenhum dado encontrado para a natureza: {natureza_selecionada}")


################################################################
import streamlit as st
import pandas as pd

def format_currency(value):
    """Formata valores monetários"""
    if pd.isna(value) or value == 0:
        return "R$ 0,00"
    return f"R$ {value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def categorizar_colaboradores_folha_por_filial(data_folha, filial_selecionada, natureza_selecionada):
    """
    Categoriza colaboradores da folha de pagamento por filial em:
    1. Orçados na filial e não realizados (demitidos)
    2. Realizados na filial e não orçados (contratados) 
    3. Transferências envolvendo a filial (entrada e saída)
    """
    df = data_folha[data_folha['CONTA'] == natureza_selecionada].copy()
    
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    # Garantir que colunas de filial sejam strings
    for coluna in ['FILIAL_orcado', 'FILIAL_realizado']:
        if coluna in df.columns:
            df.loc[:, coluna] = df[coluna].astype(str).fillna('00')
    
    # 1. ORÇADO E NÃO REALIZADO: Orçados na filial selecionada mas não realizados
    df_desligados = df[
        (df['FILIAL_orcado'] == filial_selecionada) &
        (df['FILIAL_realizado'] == '00') &
        (df['VALOR_orcado'] > 0)
    ].copy()
    
    # 2. REALIZADO E NÃO ORÇADO: Realizados na filial selecionada mas não orçados
    df_contratados = df[
        (df['FILIAL_orcado'] == '00') &
        (df['FILIAL_realizado'] == filial_selecionada) &
        (df['VALOR_realizado'] > 0)
    ].copy()
    
    # 3. TRANSFERÊNCIAS: Entrada e saída da filial selecionada
    # Transferência de ENTRADA: Orçado em outra filial, realizado na filial selecionada
    df_transferidos_entrada = df[
        (df['FILIAL_orcado'] != filial_selecionada) &
        (df['FILIAL_realizado'] == filial_selecionada) &
        (df['FILIAL_orcado'] != '00') &
        (df['VALOR_realizado'] > 0)
    ].copy()
    
    # Transferência de SAÍDA: Orçado na filial selecionada, realizado em outra filial
    df_transferidos_saida = df[
        (df['FILIAL_orcado'] == filial_selecionada) &
        (df['FILIAL_realizado'] != filial_selecionada) &
        (df['FILIAL_realizado'] != '00') &
        (df['VALOR_orcado'] > 0)
    ].copy()
    
    # Combinar transferências de entrada e saída
    df_transferidos = pd.concat([df_transferidos_entrada, df_transferidos_saida], ignore_index=True)
    
    # Agrupar por matrícula para evitar duplicatas
    def agrupar_por_matricula(df_input):
        if df_input.empty:
            return pd.DataFrame()
        
        return df_input.groupby('MATRICULA').agg({
            'FILIAL_orcado': 'first',
            'CENTROCUSTO_orcado': 'first',
            'VALOR_orcado': 'sum',
            'NOME_orcado': 'first',
            'FILIAL_realizado': 'first',
            'CENTROCUSTO_realizado': 'first',
            'VALOR_realizado': 'sum',
            'NOME_realizado': 'first'
        }).reset_index()
    
    desligados_agrupados = agrupar_por_matricula(df_desligados)
    contratados_agrupados = agrupar_por_matricula(df_contratados)
    transferidos_agrupados = agrupar_por_matricula(df_transferidos)
    
    return desligados_agrupados, contratados_agrupados, transferidos_agrupados

def exibir_tabela_folha(df, tipo_analise):
    """Exibe tabela formatada dos colaboradores"""
    if isinstance(df, dict) and not df:
        st.info("Não há dados para exibir.")
        return
    elif isinstance(df, pd.DataFrame) and df.empty:
        st.info("Não há dados para exibir.")
        return
    
    # Definir colunas para exibição baseado no tipo de análise
    if tipo_analise == "desligados":
        colunas_exibicao = ['MATRICULA', 'NOME_orcado', 'FILIAL_orcado', 'CENTROCUSTO_orcado', 'VALOR_orcado']
        renomear = {
            'MATRICULA': 'Matrícula',
            'NOME_orcado': 'Nome Colaborador',
            'FILIAL_orcado': 'Filial Orçada',
            'CENTROCUSTO_orcado': 'Centro de Custo',
            'VALOR_orcado': 'Valor Orçado'
        }
        valor_coluna = 'VALOR_orcado'
        
    elif tipo_analise == "contratados":
        colunas_exibicao = ['MATRICULA', 'NOME_realizado', 'FILIAL_realizado', 'CENTROCUSTO_realizado', 'VALOR_realizado']
        renomear = {
            'MATRICULA': 'Matrícula',
            'NOME_realizado': 'Nome Colaborador',
            'FILIAL_realizado': 'Filial Realizada',
            'CENTROCUSTO_realizado': 'Centro de Custo',
            'VALOR_realizado': 'Valor Realizado'
        }
        valor_coluna = 'VALOR_realizado'
        
    else:  # transferidos
        colunas_exibicao = ['MATRICULA', 'NOME_orcado', 'FILIAL_orcado', 'FILIAL_realizado', 'VALOR_orcado', 'VALOR_realizado']
        renomear = {
            'MATRICULA': 'Matrícula',
            'NOME_orcado': 'Nome Colaborador',
            'FILIAL_orcado': 'Filial Origem',
            'FILIAL_realizado': 'Filial Destino',
            'VALOR_orcado': 'Valor Orçado',
            'VALOR_realizado': 'Valor Realizado'
        }
        valor_coluna = ['VALOR_orcado', 'VALOR_realizado']
    
    # Filtrar apenas colunas que existem no DataFrame
    colunas_existentes = [col for col in colunas_exibicao if col in df.columns]
    df_exibicao = df[colunas_existentes].copy()
    
    # Renomear colunas
    df_exibicao = df_exibicao.rename(columns={k: v for k, v in renomear.items() if k in df_exibicao.columns})
    
    # Formatar valores monetários
    if isinstance(valor_coluna, list):
        for col in valor_coluna:
            if renomear.get(col) in df_exibicao.columns:
                df_exibicao[renomear[col]] = df_exibicao[renomear[col]].apply(format_currency)
    else:
        if renomear.get(valor_coluna) in df_exibicao.columns:
            df_exibicao[renomear[valor_coluna]] = df_exibicao[renomear[valor_coluna]].apply(format_currency)
    
    st.dataframe(df_exibicao, use_container_width=True, hide_index=True)
    
    # Exibir métricas
    if tipo_analise == "transferidos":
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Transferências", len(df))
        with col2:
            total_orcado = df['VALOR_orcado'].sum() if 'VALOR_orcado' in df.columns else 0
            st.metric("Total Orçado", format_currency(total_orcado))
        with col3:
            total_realizado = df['VALOR_realizado'].sum() if 'VALOR_realizado' in df.columns else 0
            st.metric("Total Realizado", format_currency(total_realizado))
    else:
        col1, col2 = st.columns(2)
        with col1:
            qtd_colaboradores = len(df)
            st.metric("Quantidade de Colaboradores", qtd_colaboradores)
        with col2:
            if tipo_analise == "desligados":
                total_valor = df['VALOR_orcado'].sum() if 'VALOR_orcado' in df.columns else 0
                st.metric("Total Orçado", format_currency(total_valor))
            else:  # contratados
                total_valor = df['VALOR_realizado'].sum() if 'VALOR_realizado' in df.columns else 0
                st.metric("Total Realizado", format_currency(total_valor))

def exibir_analise_folha_pagamento(data_folha):
    """Função principal para exibir a análise de colaboradores da folha"""
    st.title("📊 Análise de Colaboradores - Folha de Pagamento")
    
    # 1ª Opção: Seletor de Filial
    filiais_disponiveis = sorted([f for f in data_folha['FILIAL_orcado'].unique() if f != '00' and pd.notna(f)])
    
    if not filiais_disponiveis:
        st.warning("Não foram encontradas filiais válidas no relatório.")
        return
    
    filial_selecionada = st.selectbox(
        "1º - Selecione a filial para análise:",
        options=filiais_disponiveis,
        key="seletor_filial_folha"
    )
    
    if not filial_selecionada:
        st.info("Selecione uma filial para continuar.")
        return
    
    # 2ª Opção: Seletor de Natureza
    naturezas_disponiveis = ['13º SALARIO', 'FERIAS', 'FGTS', 'INSS',
                            'ADICIONAL TEMPO DE SERVICO', 'GRATIFICACOES', 'SALARIOS',
                            'HORAS EXTRAS', 'ADCIONAL NOTURNO', 'JOVEM APRENDIZ',
                            'SERVICO DE AUTONOMOS']
    
    # Filtrar apenas naturezas que existem nos dados
    naturezas_existentes = [nat for nat in naturezas_disponiveis if nat in data_folha['CONTA'].values]
    
    if not naturezas_existentes:
        st.warning("Nenhuma das naturezas esperadas foi encontrada nos dados.")
        return
    
    natureza_selecionada = st.selectbox(
        "2º - Selecione a natureza para análise:",
        options=naturezas_existentes,
        key="seletor_natureza_folha"
    )
    
    if not natureza_selecionada:
        st.info("Selecione uma natureza para visualizar a análise.")
        return
    
    # Realizar categorização
    desligados, contratados, transferidos = categorizar_colaboradores_folha_por_filial(data_folha, filial_selecionada, natureza_selecionada)
    
    # 3ª Exibir as 3 visões em abas
    tab1, tab2, tab3 = st.tabs([
        "📉 ORÇADO E NÃO REALIZADO", 
        "📈 REALIZADO E NÃO ORÇADO", 
        "🔄 TRANSFERÊNCIAS"
    ])
    
    with tab1:
        st.subheader(f"ORÇADO E NÃO REALIZADO - {natureza_selecionada}")
        st.markdown(f"*Colaboradores orçados na filial **{filial_selecionada}** mas não realizados (prováveis demissões)*")
        exibir_tabela_folha(desligados, "desligados")
    
    with tab2:
        st.subheader(f"REALIZADO E NÃO ORÇADO - {natureza_selecionada}")
        st.markdown(f"*Colaboradores realizados na filial **{filial_selecionada}** mas não orçados (prováveis contratações)*")
        exibir_tabela_folha(contratados, "contratados")
    
    with tab3:
        st.subheader(f"TRANSFERÊNCIAS - {natureza_selecionada}")
        st.markdown(f"*Colaboradores com transferências envolvendo a filial **{filial_selecionada}***")
        exibir_tabela_folha(transferidos, "transferidos")

# Exemplo de uso:

# exibir_analise_folha_pagamento(data_folha)
