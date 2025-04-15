# Processador de Relatórios de Benefícios

## Sobre o Projeto

O Processador de Relatórios de Benefícios é uma aplicação web desenvolvida para automatizar e simplificar a análise dos dados de benefícios. A ferramenta permite o cruzamento de informações orçadas versus realizadas, facilitando a identificação de discrepâncias e transferências entre centro de custos.

## Funcionalidades Principais

### 1. Processamento de Relatórios
- Carregamento e validação automática de arquivos Excel
- Padronização e limpeza de dados de benefícios
- Processamento integrado de múltiplas fontes de dados

### 2. Análise Comparativa
- Comparação entre valores orçados e realizados
- Análise detalhada por tipo de benefício
- Visualização por filial e centro de custo
- Destaque automático para variações significativas

### 3. Rastreamento de Transferências
- Matriz de transferência entre filiais
- Detalhamento de CPFs transferidos
- Identificação de colaboradores desligados, contratados e transferidos

### 4. Reconciliação com BI
- Comparação entre dados do relatório e do BI
- Análise por filial e centro de custo
- Identificação de diferenças e discrepâncias

### 5. Relatórios Dinâmicos
- Visualização interativa de dados
- Exportação para Excel
- Formatação automática em padrão monetário brasileiro

## Benefícios Analisados

A aplicação processa e analisa quatro tipos principais de benefícios:

- **Vale Alimentação**
- **Assistência Médica**
- **Assistência Odontológica**
- **Seguro de Vida**

## Tecnologias Utilizadas

### Backend
- **Python3**: Linguagem de programação principal
- **Pandas**: Manipulação e análise de dados
- **NumPy**: Processamento numérico
- **Datetime**: Manipulação de datas e horas

### Frontend
- **Streamlit**: Framework para criação da interface web interativa
- **Streamlit Data Editor**: Componente para edição de tabelas
- **Streamlit Tabs**: Organização de conteúdo por abas

### Processamento de Dados
- **Regex**: Para limpeza e padronização de textos e CPFs
- **Unicodedata**: Tratamento de caracteres especiais e acentuação
- **Excel Engine**: Processamento de arquivos XLSX

## Estrutura do Projeto

```
report/
├── app.py                  # Ponto de entrada principal da aplicação
├── main.py                 # Funções centrais de processamento
```

## Notas Importantes

- A aplicação espera formatos específicos para as colunas dos arquivos de entrada
- O processamento de arquivos grandes pode levar alguns minutos
- Para mais detalhes sobre os formatos esperados, consulte a página de ajuda na aplicação.
