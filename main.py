import pandas as pd
import unicodedata
import re
from datetime import datetime

def convert_to_float(value):
    """
    Converte uma representação de número para float.

    A função trata os seguintes casos:
    - Valores vazios ou NaN (retorna 0.0)
    - Vírgula como separador decimal
    - Tentativas de conversão com diferentes formatos

    Parâmetros:
    ------------
    value : str, int, float, etc.
        O valor que será convertido para float.

    Retorno:
    ---------
    float
        O valor convertido como float ou None se a conversão falhar.

    Exemplo:
    --------
    >>> convert_to_float("1.234,56")
    1234.56

    >>> convert_to_float("R$ 89,90")
    89.9

    >>> convert_to_float("")
    0.0

    >>> convert_to_float("abc")
    None
    """
    if pd.isna(value) or value == '':
        return 0.0

    try:
        return float(value)
    except (ValueError, TypeError):
        try:
            return float(str(value).replace(',', '.'))
        except (ValueError, TypeError):
            try:
                cleaned = re.sub(r'[^\d.,]', '', str(value))
                cleaned = cleaned.replace(',', '.')
                return float(cleaned)
            except:
                return None

def clean_text(text, column_name: bool = False):
    """
    Normaliza e limpa uma string removendo acentos, pontuações e espaços em branco.

    Etapas do processamento:
    - Converte caracteres acentuados para suas formas não acentuadas (ex: 'á' → 'a')
    - Remove marcas de acento (combining characters)
    - Remove pontuações e caracteres especiais
    - Remove todos os espaços (inclusive quebras de linha, tabulações, etc.)

    Parâmetros:
    ----------
    text : str
        Texto de entrada a ser limpo.

    Retorna:
    -------
    str
        Texto limpo, sem acentos, pontuações ou espaços.

    Exemplo:
    --------
    >>> clean_text("Olá, mundo! Tudo bem?")
    'OlamundoTudobem'
    """
    text = unicodedata.normalize('NFKD', str(text))
    text = ''.join([c for c in text if not unicodedata.combining(c)])
    if column_name:
        text = re.sub(r'[^A-Za-z\s]', '', text)  # Remove números e pontuação
    else:        
        text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', '', text)
    return text

def load_excel(caminho_entrada: str, Ednaldo: bool = None):
    """
    Carrega planilhas Excel que seguem um determinado padrão de nome.
    
    Args:
        caminho_entrada (string): Caminho para o arquivo Excel.
        Ednaldo (bool): Parâmetro que determina quais planilhas serão carregadas.
    
    Returns:
        Se todas as planilhas forem carregadas com sucesso:
        - Dicionário com os dataframes das planilhas válidas.
        
        Se houver qualquer problema:
        - Dicionário com logs explicando por que cada planilha foi ou não carregada.
    """
    import pandas as pd
    
    planilhas_validas = ["UNIMED", "CLIN", "VA", "SV"]
    if Ednaldo is True:
        planilhas_validas.append("SV2")
    
    colunas_obrigatorias = {
        "UNIMED": ["CPFTITULAR", "CPFBENEFICIARIO", "CCFORMATADO", "FILIAL", "VALOR", "406"],
        "CLIN": ["CPFTITULAR", "CCFORMATADO", "FILIAL", "CPFBENEFICIARIO", "VALOR", "442"],
        "VA": ["CPFTITULAR", "FILIAL", "CCFORMATADO", "VALOR", "424"],
        "SV": ["CCFORMATADO", "CPFTITULAR", "FILIAL", "VALOR"],
        "SV2": ["CPFTITULAR", "CCFORMATADO", "VALOR", "FILIAL"]
    }
    
    logs_carregamento = {}
    
    try:
        excel_file = pd.ExcelFile(caminho_entrada)
        
        dataframes_processados = {}
        for nome_planilha in excel_file.sheet_names:
            logs_carregamento[nome_planilha] = {}
            logs_carregamento[nome_planilha]['status'] = 'Não carregada'
            
            nome_padronizado = clean_text(nome_planilha).upper()
            logs_carregamento[nome_planilha]['nome_padronizado'] = nome_padronizado
            
            tipo_planilha_encontrado = None
            for planilha_valida in planilhas_validas:
                if nome_padronizado == clean_text(planilha_valida).upper():
                    tipo_planilha_encontrado = planilha_valida
                    break
            
            if tipo_planilha_encontrado is None:
                logs_carregamento[nome_planilha]['motivo'] = f"Nome não reconhecido. Esperado um dos seguintes: {', '.join(planilhas_validas)}"
                continue
                
            logs_carregamento[nome_planilha]['tipo_planilha'] = tipo_planilha_encontrado
            
            try:
                # Lê todas as colunas inicialmente para identificação
                df_completo = pd.read_excel(excel_file, sheet_name=nome_planilha, dtype=str)
                
                colunas_necessarias = colunas_obrigatorias[tipo_planilha_encontrado]
                colunas_existentes = df_completo.columns.tolist()
                
                # Mapeia as colunas obrigatórias para os nomes reais no arquivo
                mapeamento_colunas = {}
                colunas_faltantes = []
                
                for col_req in colunas_necessarias:
                    col_req_clean = clean_text(col_req).upper()
                    encontrada = False
                    for col_exist in colunas_existentes:
                        if col_req_clean in clean_text(col_exist).upper():
                            mapeamento_colunas[col_exist] = col_req
                            encontrada = True
                            break
                    if not encontrada:
                        colunas_faltantes.append(col_req)
                
                if colunas_faltantes:
                    logs_carregamento[nome_planilha]['motivo'] = f"Colunas obrigatórias faltantes: {', '.join(colunas_faltantes)}"
                    continue
                
                # Carrega apenas as colunas obrigatórias mapeadas
                colunas_para_carregar = list(mapeamento_colunas.keys())
                df = pd.read_excel(excel_file, sheet_name=nome_planilha, usecols=colunas_para_carregar, dtype=str)
                
                # Renomeia para os nomes padronizados
                df = df.rename(columns=mapeamento_colunas)
                
                dataframes_processados[tipo_planilha_encontrado] = df
                logs_carregamento[nome_planilha]['status'] = 'Carregada com sucesso'
                logs_carregamento[nome_planilha]['linhas'] = len(df)
                logs_carregamento[nome_planilha]['colunas'] = list(df.columns)
            except Exception as e:
                logs_carregamento[nome_planilha]['motivo'] = f"Erro ao processar: {str(e)}"
        
        planilhas_encontradas = [logs_carregamento[p]['tipo_planilha'] for p in logs_carregamento 
                               if 'tipo_planilha' in logs_carregamento[p]]
        planilhas_nao_encontradas = [p for p in planilhas_validas if p not in planilhas_encontradas]
        
        if planilhas_nao_encontradas:
            logs_carregamento['resumo'] = f"Planilhas esperadas não encontradas: {', '.join(planilhas_nao_encontradas)}"
            return logs_carregamento  # Retorna apenas os logs se alguma planilha estiver faltando
        
        # Verifica se todas as planilhas carregadas foram processadas com sucesso
        todas_carregadas_com_sucesso = True
        for nome_planilha in logs_carregamento:
            if nome_planilha != 'resumo' and logs_carregamento[nome_planilha].get('status') != 'Carregada com sucesso':
                todas_carregadas_com_sucesso = False
                break
        
        if todas_carregadas_com_sucesso and len(dataframes_processados) == len(planilhas_encontradas):
            return dataframes_processados  # Retorna apenas os dataframes se tudo foi bem sucedido
        else:
            return logs_carregamento  # Retorna apenas os logs se houve problemas no carregamento
        
    except Exception as e:
        error_msg = f"Erro ao carregar a planilha: {e}"
        print(error_msg)
        logs_carregamento['erro_geral'] = error_msg
        return logs_carregamento  # Retorna apenas os logs em caso de erro geral
    

def extract_unique_cpfs(dataframes):
    """
    Extrai e retorna uma lista de CPFs únicos a partir de múltiplos DataFrames.

    A função percorre um dicionário de DataFrames, procura por colunas cujo nome contenha termos relacionados a CPF,
    aplica uma função de limpeza (clean_text) para padronizar os valores e retorna apenas os CPFs válidos (com pelo menos 11 caracteres).

    Parâmetros:
    -----------
    dataframes : dict
        Um dicionário onde as chaves são nomes (strings) e os valores são objetos pandas.DataFrame.

    Retorno:
    --------
    list
        Lista de CPFs únicos encontrados nos DataFrames, já limpos e filtrados.

    Exemplo:
    --------
    >>> def clean_text(text):
    ...     return ''.join(filter(str.isdigit, text))
    
    >>> import pandas as pd
    >>> dfs = {
    ...     "planilha1": pd.DataFrame({"CPFTITULAR": ["123.456.789-00", "111.222.333-44"]}),
    ...     "planilha2": pd.DataFrame({"OUTRA_COLUNA": ["teste"], "CPFTITULAR": ["12345678900"]}),
    ... }
    >>> extract_unique_cpfs(dfs)
    ['11122233344', '12345678900']
    """
    
    all_cpfs = []
    cpf_terms = ['CPFTITULAR']
    
    for name, df in dataframes.items():
        cpf_columns = []
        for col in df.columns:
            if any(term in col for term in cpf_terms):
                cpf_columns.append(col)
        
        for col in cpf_columns:
            cpfs = df[col].apply(lambda x: clean_text(str(x)) if pd.notna(x) else None)
            valid_cpfs = [cpf for cpf in cpfs.dropna().tolist() if cpf and len(cpf) >= 11]
            all_cpfs.extend(valid_cpfs)

    unique_cpfs = list(set(all_cpfs))
    return unique_cpfs



def process_dataframe(df):
    """
    Processa um DataFrame convertendo colunas numéricas a partir de 'VALOR' para float
    e calcula a coluna 'FINAL' como a diferença entre 'VALOR' e as colunas seguintes.

    A função:
    - Converte colunas a partir de 'VALOR' para float, tratando vírgulas como separador decimal.
    - Cria a coluna 'FINAL' como: VALOR - coluna1 - coluna2 - ...

    Parâmetros:
    -----------
    df : pandas.DataFrame
        DataFrame contendo a coluna 'VALOR' e outras colunas numéricas a serem subtraídas.

    Retorno:
    --------
    pandas.DataFrame
        DataFrame com colunas numéricas tratadas e a coluna 'FINAL' adicionada.

    Exemplo:
    --------
    >>> import pandas as pd
    >>> df = pd.DataFrame({
    ...     'VALOR': ['1000', '2000'],
    ...     'DESCONTO': ['200', '300'],
    ...     'EXTRA': ['100', '200']
    ... })
    >>> process_dataframe(df)
       VALOR  DESCONTO  EXTRA  FINAL
    0  1000.0     200.0  100.0  700.0
    1  2000.0     300.0  200.0  1500.0
    """
    processed_df = df.copy()

    if 'VALOR' not in processed_df.columns:
        return processed_df

    valor_index = processed_df.columns.get_loc('VALOR')
    numeric_columns = processed_df.columns[valor_index:]

    for col in numeric_columns:
        processed_df[col] = processed_df[col].apply(convert_to_float)

    processed_df['FINAL'] = processed_df['VALOR']
    for col in numeric_columns[1:]:
        processed_df['FINAL'] -= processed_df[col]

    return processed_df

def process_full(dataframes: dict[str, pd.DataFrame], ednaldo: bool = None):
    """
    Processa múltiplos DataFrames aplicando a função process_dataframe em cada um.

    A função espera um dicionário com chaves específicas como 'UNIMED', 'VA', 'CLIN', 'SV' e opcionalmente 'SV2'.
    Se `ednaldo` for fornecido, também processa a aba 'SV2'.

    Parâmetros:
    ------------
    dataframes : dict[str, pd.DataFrame]
        Dicionário onde as chaves são nomes das planilhas e os valores são DataFrames.
    ednaldo : bool, opcional
        Se fornecido (True ou False), também processa a planilha 'SV2'.

    Retorno:
    ---------
    tuple
        Tupla contendo os DataFrames processados na seguinte ordem:
        - Se `ednaldo` for fornecido: (unimed, va, clin, sv, sv2)
        - Caso contrário: (unimed, va, clin, sv)

    Exemplo:
    --------
    >>> dfs = {
    ...     'UNIMED': pd.DataFrame(...),
    ...     'VA': pd.DataFrame(...),
    ...     'CLIN': pd.DataFrame(...),
    ...     'SV': pd.DataFrame(...),
    ...     'SV2': pd.DataFrame(...)
    ... }
    >>> process_full(dfs, ednaldo=True)
    """
    keys = ['UNIMED', 'VA', 'CLIN', 'SV']
    if ednaldo:
        keys.append('SV2')

    processed = [process_dataframe(dataframes.get(key)) for key in keys]

    return tuple(processed)



def merge_dataframes(consolidated: list[str], unimed, va, clin, sv, sv2=None, ednaldo=False):
    """
    Realiza a união (merge) de múltiplos DataFrames baseados em CPFs únicos, padronizando as chaves
    e renomeando as colunas de resultado para indicar a origem dos dados.
    
    Detalhes:
      - Para VA, SV e SV2, a chave utilizada é a coluna "CPFTITULAR" (após limpeza).
      - Para UNIMED e CLIN, a chave utilizada é a coluna "CPFBENEFICIARIO" (após limpeza).
      - Em cada DataFrame, são extraídas as colunas "FINAL" e "FILIAL", que serão renomeadas para:
            realizado_<fonte> e filial_realizada_<fonte>
      - Se o parâmetro ednaldo for True e SV2 for fornecido, os dataframes SV e SV2 serão combinados para
        formar os dados referentes à fonte SV. Para cada CPF, se SV2 apresentar valor, esse valor é utilizado;
        caso contrário, utiliza-se o valor de SV.
      - O dataframe consolidated serve como base para a união e deve conter a coluna de CPF (pode ser 
        CPFTITULAR ou CPFBENEFICIARIO). O resultado final conterá os CPFs únicos e as colunas:
            CPF,
            realizado_va, filial_realizada_va,
            realizado_unimed, filial_realizada_unimed,
            realizado_clin, filial_realizada_clin,
            realizado_sv, filial_realizada_sv
    
    Parâmetros:
    -----------
    consolidated : list[str]
        Lista com cpfs unicos a serem utilizados como base para o merge.
    unimed : pandas.DataFrame
        DataFrame da UNIMED. Deve conter as colunas "CPFBENEFICIARIO", "FINAL" e "FILIAL".
    va : pandas.DataFrame
        DataFrame da VA. Deve conter as colunas "CPFTITULAR", "FINAL" e "FILIAL".
    clin : pandas.DataFrame
        DataFrame da CLIN. Deve conter as colunas "CPFBENEFICIARIO", "FINAL" e "FILIAL".
    sv : pandas.DataFrame
        DataFrame da SV. Deve conter as colunas "CPFTITULAR", "FINAL" e "FILIAL".
    sv2 : pandas.DataFrame, opcional
        DataFrame da SV2. Deve conter as colunas "CPFTITULAR", "FINAL" e "FILIAL".
    ednaldo : bool, opcional
        Se True, indica que os dados de SV2 devem ser combinados com os de SV para a formação dos dados da fonte SV.
    
    Retorno:
    --------
    pandas.DataFrame
        DataFrame resultante com as colunas:
            CPF,
            realizado_va, filial_realizada_va,
            realizado_unimed, filial_realizada_unimed,
            realizado_clin, filial_realizada_clin,
            realizado_sv, filial_realizada_sv
    
    Exemplo:
    --------
    >>> # Suponha que os DataFrames consolidated_df, unimed, va, clin, sv e sv2 já estejam carregados e processados.
    >>> resultado = merge_dataframes(consolidated_df, unimed, va, clin, sv, sv2, ednaldo=True)
    >>> resultado.head()
    """

    master_df = pd.DataFrame({'CPF': consolidated})

    def format_filial(value):
        if pd.isna(value) or not isinstance(value, str):
            return value
        value = value.split(' - ')[0]
        numeros = re.findall(r'\d+', value)
        return str(numeros[0].zfill(2)) if numeros else None



    def clean_cpf(x):
        return clean_text(str(x)) if pd.notna(x) else None

    def prepare_df(df, key_col, df_name):
        """
        Extrai as colunas de interesse e renomeia:
          - key_col -> CPF (após limpeza)
          - FINAL -> realizado_<df_name>
          - FILIAL -> filial_realizada_<df_name>
        """
        if df is None or key_col not in df.columns or 'FINAL' not in df.columns or 'FILIAL' not in df.columns:
            return pd.DataFrame()
        temp = df[[key_col, 'FINAL', 'FILIAL', 'CCFORMATADO']].copy()
        temp[key_col] = temp[key_col].apply(clean_cpf)
        temp = temp.rename(columns={
            key_col: 'CPF',
            'FINAL': f'realizado_{df_name}',
            'FILIAL': f'filial_realizada_{df_name}',
            'CCFORMATADO': f'CC_realizado_{df_name}'
        })

        temp[f'filial_realizada_{df_name}'] = temp[f'filial_realizada_{df_name}'].apply(format_filial)
        temp[f'realizado_{df_name}'] = temp[f'realizado_{df_name}'].round(2)
        return temp

    # Preparar os DataFrames individuais
    unimed_df = prepare_df(unimed, 'CPFBENEFICIARIO', 'unimed')
    va_df     = prepare_df(va, 'CPFTITULAR', 'va')
    clin_df   = prepare_df(clin, 'CPFBENEFICIARIO', 'clin')
    sv_df     = prepare_df(sv, 'CPFTITULAR', 'sv')

    if ednaldo and sv2 is not None:
        sv2_df = prepare_df(sv2, 'CPFTITULAR', 'sv2')
        # Renomeia as colunas de sv2_df para manter a mesma nomenclatura de sv_df
        sv2_df = sv2_df.rename(columns={
            'realizado_sv2': 'realizado_sv',
            'filial_realizada_sv2': 'filial_realizada_sv',
            'CC_realizado_sv2': 'CC_realizado_sv'
        })
        # Concatena verticalmente os DataFrames sv_df e sv2_df
        sv_concat = pd.concat([sv_df, sv2_df], ignore_index=True)
        # Agrega por CPF:
        # - Soma os valores de realizado_sv
        # - Concatena as filiais únicas separadas por vírgula
        sv_agg = sv_concat.groupby('CPF', as_index=False).agg({
            'realizado_sv': 'sum',
            'filial_realizada_sv': lambda x: ", ".join(sorted(set(x.dropna()))),
            'CC_realizado_sv': lambda x: ", ".join(sorted(set(x.dropna())))
        })
        sv_df = sv_agg
        
        if not sv_df.empty and 'filial_realizada_sv' in sv_df.columns:
            sv_df['filial_realizada_sv'] = sv_df['filial_realizada_sv'].apply(lambda x: 
                               ", ".join(format_filial(part) for part in x.split(", ")) if isinstance(x, str) else x)

        if not sv_df.empty and 'CC_realizado_sv' in sv_df.columns:
            sv_df['CC_realizado_sv'] = sv_df['CC_realizado_sv'].apply(lambda x: 
                               ", ".join(format_filial(part) for part in x.split(", ")) if isinstance(x, str) else x)


    # Mescla cada DataFrame preparado no master_df
    for df_indiv in [unimed_df, va_df, clin_df, sv_df]:
        if not df_indiv.empty:
            master_df = master_df.merge(df_indiv, on='CPF', how='left')


    master_df = master_df.sort_values('CPF').reset_index(drop=True)
    return master_df


def load_recorrentes(recorrentes_file, mes_analise):
    recorrente = pd.read_excel(recorrentes_file, dtype= {'CPF': str, 'ANOMES': str, 'FILIAL': str, 
                                                         'VALE ALIMENTACAO': float, 'ASSISTENCIA MEDICA': float,
                                                         'SEGURO DE VIDA': float, 'ASSISTENCIA ODONTOLOGICA': float}, 
                               usecols= ['CPF', 'ANOMES', 'FILIAL', 'VALE ALIMENTACAO', 
                                        'ASSISTENCIA MEDICA', 'SEGURO DE VIDA', 'ASSISTENCIA ODONTOLOGICA']
        )
    recorrente['CPF'] = recorrente['CPF'].fillna('').str.replace('.', '').str.replace('-', '').str.zfill(11)
    recorrente['FILIAL'] = recorrente['FILIAL'].str.zfill(2)    
    atual_ano = datetime.now().strftime('%Y')
    anomes = f"{atual_ano}{mes_analise}"
    recorrente = recorrente[recorrente['ANOMES'] == anomes]
    recorrente.drop(columns=['ANOMES'], inplace=True)
    return recorrente


def merge_recorrentes(df_main, df_sec):
    df_sec = df_sec.rename(columns={
        'VALE ALIMENTACAO': 'previsto_va',
        'ASSISTENCIA MEDICA': 'previsto_unimed',
        'SEGURO DE VIDA': 'previsto_sv',
        'ASSISTENCIA ODONTOLOGICA': 'previsto_clin',
        'FILIAL': 'previsto_filial'
    })
    
    df_merged = pd.merge(df_main, df_sec, left_on='CPF', right_on='CPF' , how='outer')
    df_merged = df_merged[['CPF', 'previsto_filial', 
                             'previsto_va', 'CC_realizado_va', 'filial_realizada_va',  'realizado_va',
                             'previsto_unimed', 'filial_realizada_unimed', 'CC_realizado_unimed', 'realizado_unimed', 
                             'previsto_clin', 'filial_realizada_clin', 'CC_realizado_clin', 'realizado_clin', 
                             'previsto_sv', 'filial_realizada_sv', 'CC_realizado_sv', 'realizado_sv']]
    
    df_merged.fillna({
            'filial_realizada_va': '00',
            'filial_realizada_unimed': '00',
            'filial_realizada_clin': '00',
            'filial_realizada_sv': '00',
            'previsto_filial': '00'
        }, inplace=True)

    return df_merged

def verificar_retorno(resultado):
    # Se estiver vazio, é provavelmente um log (quando nenhuma planilha foi carregada)
    if not resultado:
        return False
    
    # Verifica se existem chaves específicas dos logs
    if 'resumo' in resultado or 'erro_geral' in resultado:
        return False
    
    # Pega o primeiro item do dicionário para verificar seu tipo
    primeira_chave = next(iter(resultado))
    primeiro_valor = resultado[primeira_chave]
    
    # Verificar se é um DataFrame do pandas
    if hasattr(primeiro_valor, 'iloc') and hasattr(primeiro_valor, 'columns'):
        return True
    
    # Se não for um DataFrame, é provavelmente um log
    return False



def process_report(beneficios_file, recorrentes_file, ednaldo=False, 
                  mes_analise=None, progress_callback=None):
    """
        Processa relatórios de benefícios e gera um relatório de análise consolidado.
        
        Esta função processa relatórios de benefícios de várias fontes (Unimed, VA, CLIN, SV)
        e os combina com dados de benefícios recorrentes para criar uma análise abrangente.
        
        Parâmetros:
        -----------
        beneficios_file : str ou objeto tipo arquivo
            Caminho para o arquivo Excel contendo dados de benefícios.
        recorrentes_file : str ou objeto tipo arquivo
            Caminho para o arquivo Excel contendo dados de benefícios recorrentes.
        ednaldo : bool, padrão=False
            Indica se deve processar no modo 'Ednaldo', que inclui uma planilha SV2 adicional.
        mes_analise : str, opcional
            Mês de análise no formato 'MM/AAAA'. Se None, o mês atual será usado.
        progress_callback : callable, opcional
            Uma função para chamar com atualizações de progresso. Recebe dois parâmetros:
            - progress: int (0-100)
            - message: str
            
        Retornos:
        ---------
        tuple
            Se bem-sucedido, retorna (result_df, logs) onde:
            - result_df: DataFrame pandas contendo os dados mesclados e processados
            - logs: dicionário com informações de processamento para cada fonte de dados
            
            Se não for bem-sucedido, retorna (logs, mensagem_erro) onde:
            - logs: dicionário com informações de processamento até o ponto de falha
            - mensagem_erro: str explicando o erro
        
        Exemplo do dicionário de logs:
        -----------------------------
        >>> logs = {
            'unimed': {
                'status': 'Carregada com sucesso',
                'nome_padronizado': 'UNIMED',
                'tipo_planilha': 'UNIMED',
                'linhas': 184,
                'colunas': ['FILIAL', 'CCFORMATADO', 'CPFTITULAR', 'CPFBENEFICIARIO', 'VALOR', '406']
            },
            'VA': {
                'status': 'Carregada com sucesso',
                'nome_padronizado': 'VA',
                'tipo_planilha': 'VA',
                'linhas': 244,
                'colunas': ['FILIAL', 'CCFORMATADO', 'CPFTITULAR', 'VALOR', '424']
            },
            'clin': {
                'status': 'Carregada com sucesso',
                'nome_padronizado': 'CLIN',
                'tipo_planilha': 'CLIN',
                'linhas': 250,
                'colunas': ['FILIAL', 'CPFTITULAR', 'CPFBENEFICIARIO', 'CCFORMATADO', 'VALOR', '441', '442']
            },
            'sv': {
                'status': 'Carregada com sucesso',
                'nome_padronizado': 'SV',
                'tipo_planilha': 'SV',
                'linhas': 253,
                'colunas': ['FILIAL', 'CCFORMATADO', 'CPFTITULAR', 'VALOR']
            },
            'sv2': {
                'status': 'Carregada com sucesso',
                'nome_padronizado': 'SV2',
                'tipo_planilha': 'SV2',
                'linhas': 9,
                'colunas': ['FILIAL', 'CPFTITULAR', 'CCFORMATADO', 'VALOR']
            },
            'resumo': 'Todas as planilhas esperadas foram encontradas'
        }
    """    
    

    def update_progress(progress, message=""):
        if progress_callback:
            progress_callback(progress, message)
    
    update_progress(0, "Carregando arquivos...")
    
    # Carregar os dados dos benefícios realizados
    dataframes = load_excel(beneficios_file, ednaldo)
    
    update_progress(20, "Arquivos carregados com sucesso")
    
    if verificar_retorno(dataframes):
        # Extrair CPFs únicos dos dataframes
        cpfs_unicos = extract_unique_cpfs(dataframes)
        
        update_progress(40, "CPFs extraídos e processados")
        
        # Carregar dados de recorrentes (previstos)
        recorrente_df = load_recorrentes(recorrentes_file, mes_analise)
        
        update_progress(60, "Dados de recorrentes processados")
        
        # Processar os dataframes
        if ednaldo:
            unimed, va, clin, sv, sv2 = process_full(dataframes, ednaldo=ednaldo)
        else:
            unimed, va, clin, sv = process_full(dataframes, ednaldo=ednaldo)
            sv2 = None
        
        update_progress(80, "Dados processados, gerando relatório final")
        
        # Realizar o merge dos dataframes
        result_df = merge_dataframes(cpfs_unicos, unimed, va, clin, sv, sv2, ednaldo)
        
        # Fazer o merge com os dados de recorrentes
        result_df = merge_recorrentes(result_df, recorrente_df)
    
        update_progress(100, "Relatório finalizado")
    
        return result_df
    
    else: 
        return dataframes



def process_report2(beneficios_file, bi_path, ednaldo=False, progress_callback=None):
    """
        2
    """

    def update_progress(progress, message=""):
        if progress_callback:
            progress_callback(progress, message)
    
    update_progress(0, "Carregando arquivos...")
    
    # Carregar os dados dos benefícios realizados
    dataframes = load_excel(beneficios_file, ednaldo)
    
    update_progress(20, "Arquivos carregados com sucesso")
    
    # Initialize result_bi as None
    result_bi = None
    
    if verificar_retorno(dataframes):
        # Extrair CPFs únicos dos dataframes
        cpfs_unicos = extract_unique_cpfs(dataframes)
        
        update_progress(40, "CPFs extraídos e processados")        
        
        # Processar os dataframes
        if ednaldo:
            unimed, va, clin, sv, sv2 = process_full(dataframes, ednaldo=ednaldo)
        else:
            unimed, va, clin, sv = process_full(dataframes, ednaldo=ednaldo)
            sv2 = None
        
        update_progress(80, "Dados processados, gerando relatório final")
        
        # Realizar o merge dos dataframes
        result_df = merge_dataframes(cpfs_unicos, unimed, va, clin, sv, sv2, ednaldo)
    
        update_progress(100, "Relatório finalizado")
        result_bi = pd.read_excel(bi_path, 
                                  dtype= {'COD CENTRO CUSTO': str, 
                                        'SINTETICO CC': str,
                                        'CONTA': str, 
                                        'VALOR': float}, 
                                usecols= ['COD CENTRO CUSTO', 'SINTETICO CC', 'CONTA', 'VALOR'])
        result_bi = result_bi.rename(columns={'COD CENTRO CUSTO': 'CC', 'SINTETICO CC': 'FILIAL', 'CONTA': 'BENEFICIO'})
        excluded_benefits = ['SUBSIDIO EDUCACAO', 'CURSOS E TREINAMENTOS', 'VALE TRANSPORTE']
        result_bi = result_bi[~result_bi['BENEFICIO'].isin(excluded_benefits)]
        filial_mapping = {
            'CD3 - CABEDELO' : '31',
            'CD7 - CABEDELO 2': '59',
            'CD1 - SANTA CECILIA': '02',
            'AST': '67',
            'CD4 - CAMPINA GRANDE': '41',
            'CD6 - IRECE': '58'
        }
        result_bi['FILIAL'] = result_bi['FILIAL'].replace(filial_mapping)

        benefit_mapping = {
            'VALE ALIMENTACAO - PAT': 'VA',
            'ASSISTENCIA MEDICA': 'UNIMED',
            'ASSISTENCIA ODONTOLOGICA': 'CLIN',
            'SEGURO DE VIDA': 'SV'
        }

        result_bi['BENEFICIO'] = result_bi['BENEFICIO'].replace(benefit_mapping)

        result_bi['VALOR'] = result_bi['VALOR'] * -1        
        
        return result_df, result_bi
    
    else: 
        return dataframes, None
