import pandas as pd
import unicodedata
import re
from datetime import datetime

def converter_para_float(valor):
    if pd.isna(valor) or valor == '':
        return 0.0
    try:
        return float(valor)
    except (ValueError, TypeError):
        try:
            return float(str(valor).replace(',', '.'))
        except (ValueError, TypeError):
            try:
                valor_limpo = re.sub(r'[^\d.,]', '', str(valor))
                return float(valor_limpo.replace(',', '.'))
            except:
                return None

def limpar_texto(texto, nome_coluna=False):
    texto = unicodedata.normalize('NFKD', str(texto))
    texto = ''.join([c for c in texto if not unicodedata.combining(c)])
    if nome_coluna:
        texto = re.sub(r'[^A-Za-z\s]', '', texto)
    else:        
        texto = re.sub(r'[^\w\s]', '', texto)
    return re.sub(r'\s+', '', texto)

def carregar_excel(caminho_arquivo, modo_ednaldo=False):
    tipos_planilhas = ["UNIMED", "CLIN", "VA", "SV"]
    if modo_ednaldo:
        tipos_planilhas.append("SV2")
    
    colunas_necessarias = {
        "UNIMED": ["CPFTITULAR", "CPFBENEFICIARIO", "NOMEBENEFICIARIO", "CCFORMATADO", "FILIAL", "VALOR", "406"],
        "CLIN": ["CPFTITULAR", "CCFORMATADO", "NOMEBENEFICIARIO", "FILIAL", "CPFBENEFICIARIO", "VALOR", "441", '442'],
        "VA": ["CPFTITULAR", "FILIAL", "CCFORMATADO", "NOMEBENEFICIARIO", "VALOR", "424"],
        "SV": ["CCFORMATADO", "CPFTITULAR", "NOMEBENEFICIARIO", "FILIAL", "VALOR"],
        "SV2": ["CPFTITULAR", "CCFORMATADO", "NOMEBENEFICIARIO", "VALOR", "FILIAL"]
    }

    log_carregamento = {}
    
    try:
        arquivo_excel = pd.ExcelFile(caminho_arquivo)
        dados_planilhas = {}

        for nome_aba in arquivo_excel.sheet_names:
            log_carregamento[nome_aba] = {'status': 'Não carregada'}
            aba_limpa = limpar_texto(nome_aba).upper()
            log_carregamento[nome_aba]['nome_padronizado'] = aba_limpa

            tipo_identificado = next((t for t in tipos_planilhas if limpar_texto(t).upper() == aba_limpa), None)

            if not tipo_identificado:
                log_carregamento[nome_aba]['motivo'] = f"Nome não reconhecido. Esperado: {', '.join(tipos_planilhas)}"
                continue

            log_carregamento[nome_aba]['tipo_planilha'] = tipo_identificado

            try:
                df_completo = pd.read_excel(arquivo_excel, sheet_name=nome_aba, dtype=str)
                colunas_encontradas = df_completo.columns.tolist()

                mapeamento = {}
                faltantes = []

                for col in colunas_necessarias[tipo_identificado]:
                    col_limpa = limpar_texto(col).upper()
                    encontrou = False
                    for col_existente in colunas_encontradas:
                        if col_limpa in limpar_texto(col_existente).upper():
                            mapeamento[col_existente] = col
                            encontrou = True
                            break
                    if not encontrou:
                        faltantes.append(col)

                if faltantes:
                    log_carregamento[nome_aba]['motivo'] = f"Colunas faltantes: {', '.join(faltantes)}"
                    continue

                colunas_para_usar = list(mapeamento.keys())
                df = pd.read_excel(arquivo_excel, sheet_name=nome_aba, usecols=colunas_para_usar, dtype=str)
                df = df.rename(columns=mapeamento)

                dados_planilhas[tipo_identificado] = df
                log_carregamento[nome_aba]['status'] = 'Carregada com sucesso'
                log_carregamento[nome_aba]['linhas'] = len(df)
                log_carregamento[nome_aba]['colunas'] = list(df.columns)
            except Exception as e:
                log_carregamento[nome_aba]['motivo'] = f"Erro: {str(e)}"

        planilhas_encontradas = [log_carregamento[p]['tipo_planilha'] for p in log_carregamento if 'tipo_planilha' in log_carregamento[p]]
        nao_encontradas = [p for p in tipos_planilhas if p not in planilhas_encontradas]

        if nao_encontradas:
            log_carregamento['resumo'] = f"Planilhas não encontradas: {', '.join(nao_encontradas)}"
            return log_carregamento

        todas_ok = all(log_carregamento[p].get('status') == 'Carregada com sucesso' for p in log_carregamento if p != 'resumo')

        return dados_planilhas if todas_ok else log_carregamento

    except Exception as e:
        log_carregamento['erro_geral'] = f"Erro: {e}"
        return log_carregamento

def extrair_cpfs_unicos(dados_planilhas):
    lista_cpfs = []
    for df in dados_planilhas.values():
        for coluna in df.columns:
            if 'CPFTITULAR' in coluna:
                cpfs = df[coluna].apply(lambda x: limpar_texto(str(x)) if pd.notna(x) else None)
                cpfs_validos = [cpf for cpf in cpfs.dropna().tolist() if cpf and len(cpf) >= 11]
                lista_cpfs.extend(cpfs_validos)
    return list(set(lista_cpfs))

def extrair_nomes_por_cpf(dados_planilhas):
    """
    Extrai os nomes dos beneficiários usando CPFTITULAR como chave
    """
    nomes_por_cpf = {}
    
    for df in dados_planilhas.values():
        if 'CPFTITULAR' in df.columns and 'NOMEBENEFICIARIO' in df.columns:
            for idx, row in df.iterrows():
                cpf_titular = limpar_texto(str(row['CPFTITULAR'])) if pd.notna(row['CPFTITULAR']) else None
                nome_beneficiario = str(row['NOMEBENEFICIARIO']).strip() if pd.notna(row['NOMEBENEFICIARIO']) else None
                
                if cpf_titular and nome_beneficiario and len(cpf_titular) >= 11:
                    # Se já existe um nome para este CPF, mantém o primeiro encontrado
                    if cpf_titular not in nomes_por_cpf:
                        nomes_por_cpf[cpf_titular] = nome_beneficiario
    
    return nomes_por_cpf

def processar_tabela(df):
    tabela = df.copy()
    if 'VALOR' not in tabela.columns:
        return tabela

    indice_valor = tabela.columns.get_loc('VALOR')
    colunas_numericas = tabela.columns[indice_valor:]

    for coluna in colunas_numericas:
        tabela[coluna] = tabela[coluna].apply(converter_para_float)

    tabela['FINAL'] = tabela['VALOR']
    for coluna in colunas_numericas[1:]:
        tabela['FINAL'] -= tabela[coluna]

    return tabela

def processar_completo(planilhas, modo_ednaldo=False):
    chaves = ['UNIMED', 'VA', 'CLIN', 'SV']
    if modo_ednaldo:
        chaves.append('SV2')
    return tuple(processar_tabela(planilhas.get(chave)) for chave in chaves)

def juntar_tabelas(cpfs, unimed, va, clin, sv, sv2=None, modo_ednaldo=False):
    tabela_mestre = pd.DataFrame({'CPF': cpfs})

    def formatar_filial(valor):
        if pd.isna(valor) or not isinstance(valor, str):
            return valor
        valor = valor.split(' - ')[0]
        numeros = re.findall(r'\d+', valor)
        return str(numeros[0].zfill(2)) if numeros else None

    def limpar_cpf(cpf):
        return limpar_texto(str(cpf)) if pd.notna(cpf) else None

    def preparar_tabela(tabela, coluna_chave, nome_df):
        if tabela is None or coluna_chave not in tabela.columns or 'FINAL' not in tabela.columns or 'FILIAL' not in tabela.columns:
            return pd.DataFrame()
        temp = tabela[[coluna_chave, 'FINAL', 'FILIAL', 'CCFORMATADO']].copy()
        temp[coluna_chave] = temp[coluna_chave].apply(limpar_cpf)
        temp = temp.rename(columns={
            coluna_chave: 'CPF',
            'FINAL': f'realizado_{nome_df}',
            'FILIAL': f'filial_realizada_{nome_df}',
            'CCFORMATADO': f'CC_realizado_{nome_df}'
        })
        temp[f'filial_realizada_{nome_df}'] = temp[f'filial_realizada_{nome_df}'].apply(formatar_filial)
        temp[f'realizado_{nome_df}'] = temp[f'realizado_{nome_df}'].round(2)
        return temp

    df_unimed = preparar_tabela(unimed, 'CPFBENEFICIARIO', 'unimed')
    df_va = preparar_tabela(va, 'CPFTITULAR', 'va')
    df_clin = preparar_tabela(clin, 'CPFBENEFICIARIO', 'clin')
    df_sv = preparar_tabela(sv, 'CPFTITULAR', 'sv')

    if modo_ednaldo and sv2 is not None:
        df_sv2 = preparar_tabela(sv2, 'CPFTITULAR', 'sv2')
        df_sv2 = df_sv2.rename(columns={
            'realizado_sv2': 'realizado_sv',
            'filial_realizada_sv2': 'filial_realizada_sv',
            'CC_realizado_sv2': 'CC_realizado_sv'
        })
        df_sv = pd.concat([df_sv, df_sv2], ignore_index=True)
        df_sv = df_sv.groupby('CPF', as_index=False).agg({
            'realizado_sv': 'sum',
            'filial_realizada_sv': lambda x: ", ".join(sorted(set(x.dropna()))),
            'CC_realizado_sv': lambda x: ", ".join(sorted(set(x.dropna())))
        })

        if not df_sv.empty:
            df_sv['filial_realizada_sv'] = df_sv['filial_realizada_sv'].apply(
                lambda x: ", ".join(formatar_filial(p) for p in x.split(", ")) if isinstance(x, str) else x)
            df_sv['CC_realizado_sv'] = df_sv['CC_realizado_sv'].apply(
                lambda x: ", ".join(formatar_filial(p) for p in x.split(", ")) if isinstance(x, str) else x)

    for df_individual in [df_unimed, df_va, df_clin, df_sv]:
        if not df_individual.empty:
            tabela_mestre = tabela_mestre.merge(df_individual, on='CPF', how='left')

    return tabela_mestre.sort_values('CPF').reset_index(drop=True)

def carregar_orcamento(caminho_orcamento, mes_analise):
    recorrentes = pd.read_excel(caminho_orcamento, 
        dtype={
            'CPF': str, 'ANOMES': str, 'FILIAL': str,
            'VALE ALIMENTACAO': float, 'ASSISTENCIA MEDICA': float,
            'SEGURO DE VIDA': float, 'ASSISTENCIA ODONTOLOGICA': float
        },
        usecols=['CPF', 'ANOMES', 'FILIAL', 'VALE ALIMENTACAO', 
                 'ASSISTENCIA MEDICA', 'SEGURO DE VIDA', 'ASSISTENCIA ODONTOLOGICA']
    )

    recorrentes['CPF'] = recorrentes['CPF'].fillna('').str.replace('.', '').str.replace('-', '').str.zfill(11)
    recorrentes['FILIAL'] = recorrentes['FILIAL'].str.zfill(2)
    ano_mes = f"{datetime.now().strftime('%Y')}{mes_analise}"
    recorrentes = recorrentes[recorrentes['ANOMES'] == ano_mes]
    recorrentes.drop(columns=['ANOMES'], inplace=True)

    return recorrentes

def juntar_recorrentes(tabela_mestre, recorrentes):
    recorrentes = recorrentes.rename(columns={
        'VALE ALIMENTACAO': 'previsto_va',
        'ASSISTENCIA MEDICA': 'previsto_unimed',
        'SEGURO DE VIDA': 'previsto_sv',
        'ASSISTENCIA ODONTOLOGICA': 'previsto_clin',
        'FILIAL': 'previsto_filial'
    })

    resultado = pd.merge(tabela_mestre, recorrentes, on='CPF', how='outer')

    colunas_ordenadas = [
        'CPF', 'NOMEBENEFICIARIO', 'previsto_filial', 
        'previsto_va', 'CC_realizado_va', 'filial_realizada_va', 'realizado_va',
        'previsto_unimed', 'filial_realizada_unimed', 'CC_realizado_unimed', 'realizado_unimed',
        'previsto_clin', 'filial_realizada_clin', 'CC_realizado_clin', 'realizado_clin',
        'previsto_sv', 'filial_realizada_sv', 'CC_realizado_sv', 'realizado_sv'
    ]

    resultado = resultado[colunas_ordenadas]

    resultado.fillna({
        'filial_realizada_va': '00',
        'filial_realizada_unimed': '00',
        'filial_realizada_clin': '00',
        'filial_realizada_sv': '00',
        'previsto_filial': '00'
    }, inplace=True)

    return resultado

def verificar_resultado(retorno):
    if not retorno:
        return False
    if 'resumo' in retorno or 'erro_geral' in retorno:
        return False

    primeira_chave = next(iter(retorno))
    primeiro_valor = retorno[primeira_chave]
    return hasattr(primeiro_valor, 'iloc') and hasattr(primeiro_valor, 'columns')

def gerar_relatorio(caminho_beneficios: str, caminho_orcamento: str, modo_ednaldo=False, mes_analise: str = None, progresso=None):
    def atualizar_progresso(porc, mensagem=""):
        if progresso:
            progresso(porc, mensagem)

    atualizar_progresso(0, "Carregando arquivos...")
    planilhas = carregar_excel(caminho_beneficios, modo_ednaldo)
    atualizar_progresso(20, "Arquivos carregados")

    if verificar_resultado(planilhas):
        cpfs = extrair_cpfs_unicos(planilhas)
        nomes_por_cpf = extrair_nomes_por_cpf(planilhas)  # Nova função para extrair nomes
        atualizar_progresso(40, "CPFs e nomes extraídos")

        recorrentes = carregar_orcamento(caminho_orcamento, mes_analise)
        atualizar_progresso(60, "Recorrentes carregados")

        if modo_ednaldo:
            unimed, va, clin, sv, sv2 = processar_completo(planilhas, modo_ednaldo=True)
        else:
            unimed, va, clin, sv = processar_completo(planilhas)
            sv2 = None

        atualizar_progresso(80, "Dados processados")

        tabela_final = juntar_tabelas(cpfs, unimed, va, clin, sv, sv2, modo_ednaldo)
        
        # Adicionar os nomes dos beneficiários na tabela final
        tabela_final['NOMEBENEFICIARIO'] = tabela_final['CPF'].map(nomes_por_cpf)
        
        tabela_final = juntar_recorrentes(tabela_final, recorrentes)
        
        tabela_final[['CC_realizado_va', 'CC_realizado_unimed', 'CC_realizado_sv', 'CC_realizado_clin']] = tabela_final[['CC_realizado_va', 'CC_realizado_unimed', 'CC_realizado_sv', 'CC_realizado_clin']].fillna('00000000')
        tabela_final[['filial_realizada_va', 'filial_realizada_unimed', 'filial_realizada_sv', 'filial_realizada_clin']] = tabela_final[['filial_realizada_va', 'filial_realizada_unimed', 'filial_realizada_sv', 'filial_realizada_clin']].fillna('00')
        tabela_final['NOMEBENEFICIARIO'] = tabela_final['NOMEBENEFICIARIO'].fillna('')
        tabela_final = tabela_final.fillna(0)
        atualizar_progresso(100, "Relatório finalizado")
        return tabela_final
        
    else:
        return planilhas

def gerar_comparacao_bi(caminho_beneficios: str, caminho_bi: str, modo_ednaldo=False, progresso=None):
    def atualizar_progresso(porc, mensagem=""):
        if progresso:
            progresso(porc, mensagem)

    atualizar_progresso(0, "Carregando arquivos...")
    planilhas = carregar_excel(caminho_beneficios, modo_ednaldo)
    atualizar_progresso(20, "Arquivos carregados")

    resultado_bi = None

    if verificar_resultado(planilhas):
        cpfs = extrair_cpfs_unicos(planilhas)
        nomes_por_cpf = extrair_nomes_por_cpf(planilhas)  # Adicionar nomes também aqui
        atualizar_progresso(40, "CPFs e nomes extraídos")

        if modo_ednaldo:
            unimed, va, clin, sv, sv2 = processar_completo(planilhas, modo_ednaldo=True)
        else:
            unimed, va, clin, sv = processar_completo(planilhas)
            sv2 = None

        atualizar_progresso(80, "Dados processados")

        tabela_final = juntar_tabelas(cpfs, unimed, va, clin, sv, sv2, modo_ednaldo)
        
        # Adicionar os nomes dos beneficiários na tabela final
        tabela_final['NOMEBENEFICIARIO'] = tabela_final['CPF'].map(nomes_por_cpf)
        
        atualizar_progresso(100, "Dados consolidados")

        # Leitura do arquivo BI (Business Intelligence)
        resultado_bi = pd.read_excel(
            caminho_bi,
            dtype={
                'COD CENTRO CUSTO': str,
                'SINTETICO': str,
                'CONTA': str,
                'VALOR': float
            },
            usecols=['COD CENTRO CUSTO', 'SINTETICO', 'CONTA', 'VALOR']
        )

        resultado_bi = resultado_bi.rename(columns={
            'COD CENTRO CUSTO': 'CC',
            'SINTETICO': 'FILIAL',
            'CONTA': 'BENEFICIO'
        })

        beneficios_excluidos = ['SUBSIDIO EDUCACAO', 'CURSOS E TREINAMENTOS', 'VALE TRANSPORTE']
        resultado_bi = resultado_bi[~resultado_bi['BENEFICIO'].isin(beneficios_excluidos)]

        mapeamento_filiais = {
            'CD3 - CABEDELO': '31',
            'CD7 - CABEDELO 2': '59',
            'CD1 - SANTA CECILIA': '02',
            'AST': '67',
            'CD4 - CAMPINA GRANDE': '41',
            'CD6 - IRECE': '58'
        }
        resultado_bi['FILIAL'] = resultado_bi['FILIAL'].replace(mapeamento_filiais)

        mapeamento_beneficios = {
            'VALE ALIMENTACAO - PAT': 'VA',
            'ASSISTENCIA MEDICA': 'UNIMED',
            'ASSISTENCIA ODONTOLOGICA': 'CLIN',
            'SEGURO DE VIDA': 'SV'
        }
        resultado_bi['BENEFICIO'] = resultado_bi['BENEFICIO'].replace(mapeamento_beneficios)

        resultado_bi['VALOR'] = resultado_bi['VALOR'] * -1

        return tabela_final, resultado_bi
    else:
        return planilhas, None
    

def estruturar_dados(caminho_arquivo, nomes_abas = ['REALIZADO', 'ORCADO']):
    def padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
        def remover_acentos(texto: str) -> str:
            texto = unicodedata.normalize('NFKD', texto)
            texto = texto.encode('ASCII', 'ignore').decode('ASCII')
            return texto

        colunas_padronizadas = [
            re.sub(r'\s+', '', remover_acentos(col)).upper()
            for col in df.columns
        ]

        df.columns = colunas_padronizadas
        return df

    realizado = pd.read_excel(caminho_arquivo, sheet_name= nomes_abas[0], dtype= str)
    orcamento = pd.read_excel(caminho_arquivo, sheet_name= nomes_abas[1], dtype=str)
    realizado = padronizar_colunas(realizado)
    orcamento = padronizar_colunas(orcamento)
    realizado['VALOR'] = realizado['VALOR'].apply(float) * -1
    orcamento['VALOR'] = orcamento['VALOR'].apply(float) * -1
    realizado['FILIAL'] = realizado['CODCENTROCUSTO'].apply(lambda x: x.removeprefix('0')[0:2])
    orcamento['FILIAL'] = orcamento['CODCENTROCUSTO'].apply(lambda x: x.removeprefix('0')[0:2])
    orcamento['TIPO_CONTA']
    folha = ['FERIAS', '13º SALARIO', 'INSS', 'FGTS', 'SALARIOS', 'ADICIONAL TEMPO DE SERVICO', 'GRATIFICACOES', 'HORAS EXTRAS', 'ADCIONAL NOTURNO', 'JOVEM APRENDIZ', 'SERVICO DE AUTONOMOS']
    realizado['CONTA'] = realizado['CONTA'].apply(lambda x: x.strip())
    orcamento['CONTA'] = orcamento['CONTA'].apply(lambda x: x.strip())          
    realizado = realizado[realizado['CONTA'].isin(folha)]
    orcamento = orcamento[orcamento['CONTA'].isin(folha)]

    return orcamento, realizado


def consolidar_orcado_realizado(df_orcado: pd.DataFrame,
                                 df_realizado: pd.DataFrame) -> pd.DataFrame:
    """
    Consolida os dataframes de orçado e realizado em um único,
    com sufixos _orcado e _realizado e preenchimento '00' onde não houver dados.
    
    Parâmetros
    ----------
    df_orcado : pd.DataFrame
        DataFrame com os valores orçados. Colunas esperadas:
        ['MÊS', 'COD CENTRO CUSTO', 'CENTRO CUSTO', 'COD CONTA', 'CONTA',
         'VALOR', 'MATRICULA', 'NOME', 'TIPO_CONTA', 'FILIAL']
    
    df_realizado : pd.DataFrame
        DataFrame com os valores realizados. Mesmas colunas de df_orcado.
    
    Retorna
    -------
    pd.DataFrame
        DataFrame com colunas:
        ['MATRICULA', 'CONTA',
         'FILIAL_orcado',  'CENTRO CUSTO_orcado',  'VALOR_orcado',  'NOME_orcado',
         'FILIAL_realizado','CENTRO CUSTO_realizado','VALOR_realizado','NOME_realizado']
        Preenchido com '00' onde não havia dado correspondente.
    """

    core_cols = ['FILIAL', 'CENTROCUSTO', 'VALOR', 'NOME']
    
    base_orcado = df_orcado[['MATRICULA', 'CONTA'] + core_cols].copy()
    base_real = df_realizado[['MATRICULA', 'CONTA'] + core_cols].copy()
    
    base_orcado.rename(columns={c: c + '_orcado' for c in core_cols},
                       inplace=True)
    base_real.rename(columns={c: c + '_realizado' for c in core_cols},
                     inplace=True)
    
    df_merge = pd.merge(base_orcado,
                        base_real,
                        on=['MATRICULA', 'CONTA'],
                        how='outer')
    
    for c in core_cols:
        df_merge[c + '_orcado'] = df_merge[c + '_orcado'].fillna('00')
        df_merge[c + '_realizado'] = df_merge[c + '_realizado'].fillna('00')

    df_merge['VALOR_orcado'] = df_merge['VALOR_orcado'].apply(
        lambda x: 0.0 if x == '00' else float(x)
    )
    df_merge['VALOR_realizado'] = df_merge['VALOR_realizado'].apply(
        lambda x: 0.0 if x == '00' else float(x)
    )

    cols_ordenadas = (
        ['MATRICULA', 'CONTA'] +
        [f'{c}_orcado' for c in core_cols] +
        [f'{c}_realizado' for c in core_cols]
    )
    return df_merge[cols_ordenadas]