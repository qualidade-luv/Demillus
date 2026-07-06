# app.py
import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json
import re

# Configuração da página
st.set_page_config(
    page_title="Demillus - Gestão de Pedidos",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo CSS personalizado
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
        text-align: center;
        padding: 1rem;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        color: #1E88E5;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #666;
        margin-top: 0.5rem;
    }
    .success-message {
        padding: 1rem;
        background-color: #d4edda;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
        color: #155724;
    }
    .payment-card {
        background-color: #e8f5e9;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #4CAF50;
        margin: 0.5rem 0;
    }
    .pending-card {
        background-color: #fff3e0;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #FF9800;
        margin: 0.5rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# ============================
# CONEXÃO COM GOOGLE SHEETS
# ============================
def conectar_google_sheets():
    """Estabelece conexão com Google Sheets usando credenciais do Streamlit Secrets"""
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        st.error(f"❌ Erro ao conectar ao Google Sheets: {str(e)}")
        return None

def carregar_dados():
    """Carrega os dados da planilha Demillus - aba PEDIDOS"""
    try:
        client = conectar_google_sheets()
        if client is None:
            return None
        
        try:
            spreadsheet = client.open("Demillus")
        except:
            st.error("❌ Planilha 'Demillus' não encontrada. Verifique o nome.")
            return None
        
        try:
            worksheet = spreadsheet.worksheet("PEDIDOS")
        except:
            st.error("❌ Aba 'PEDIDOS' não encontrada. Verifique o nome da aba.")
            return None
        
        dados = worksheet.get_all_values()
        
        if not dados or len(dados) < 2:
            return pd.DataFrame()
        
        cabecalho = dados[0]
        dados = dados[1:]
        
        df = pd.DataFrame(dados, columns=cabecalho)
        df = df.replace('', pd.NA)
        
        # Converte colunas numéricas
        colunas_numericas = ['QUANTIDADE', 'VALOR_PAGO', 'DEDUÇÃO', 'VALOR _CLIENTE', 'VALOR_PAGO_ACUMULADO', 'SALDO_DEVEDOR']
        for col in colunas_numericas:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # Remove linhas completamente vazias
        df = df.dropna(how='all')
        
        return df
        
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados: {str(e)}")
        return None

def salvar_dados(df):
    """Salva os dados atualizados na planilha"""
    try:
        client = conectar_google_sheets()
        if client is None:
            return False
        
        spreadsheet = client.open("Demillus")
        worksheet = spreadsheet.worksheet("PEDIDOS")
        
        # Prepara os dados para salvar
        dados_para_salvar = [df.columns.tolist()] + df.fillna('').values.tolist()
        
        # Limpa a planilha e salva os novos dados
        worksheet.clear()
        worksheet.update(dados_para_salvar, value_input_option='USER_ENTERED')
        
        return True
        
    except Exception as e:
        st.error(f"❌ Erro ao salvar dados: {str(e)}")
        return False

# ============================
# FUNÇÕES DE ANÁLISE
# ============================
def calcular_metricas(df):
    """Calcula as principais métricas do negócio"""
    if df is None or df.empty:
        return {
            'total_pedidos': 0,
            'total_clientes': 0,
            'faturamento_bruto': 0,
            'faturamento_liquido': 0,
            'total_deducoes': 0,
            'valor_medio_pedido': 0,
            'total_itens': 0,
            'total_recebido': 0,
            'total_saldo_devedor': 0
        }
    
    # Ajusta nomes das colunas
    colunas = df.columns.tolist()
    
    # Encontra as colunas necessárias
    col_valor_cliente = None
    col_valor_pago = None
    col_deducao = None
    col_quantidade = None
    col_cliente = None
    col_campanha = None
    col_valor_pago_acumulado = None
    col_saldo_devedor = None
    
    for col in colunas:
        if 'VALOR _CLIENTE' in col or 'VALOR_CLIENTE' in col:
            col_valor_cliente = col
        elif 'VALOR_PAGO' in col and 'ACUMULADO' not in col:
            col_valor_pago = col
        elif 'DEDUÇÃO' in col or 'DEDUCAO' in col:
            col_deducao = col
        elif 'QUANTIDADE' in col:
            col_quantidade = col
        elif 'CLIENTE' in col:
            col_cliente = col
        elif 'CAMPANHA' in col:
            col_campanha = col
        elif 'VALOR_PAGO_ACUMULADO' in col:
            col_valor_pago_acumulado = col
        elif 'SALDO_DEVEDOR' in col:
            col_saldo_devedor = col
    
    # Calcula as métricas
    total_pedidos = len(df)
    total_clientes = df[col_cliente].nunique() if col_cliente else 0
    
    if col_valor_pago:
        faturamento_bruto = df[col_valor_pago].sum()
    else:
        faturamento_bruto = 0
    
    if col_deducao:
        total_deducoes = df[col_deducao].sum()
    else:
        total_deducoes = 0
    
    if col_valor_cliente:
        faturamento_liquido = df[col_valor_cliente].sum()
    else:
        faturamento_liquido = 0
    
    valor_medio_pedido = faturamento_liquido / total_pedidos if total_pedidos > 0 else 0
    
    if col_quantidade:
        total_itens = df[col_quantidade].sum()
    else:
        total_itens = 0
    
    if col_valor_pago_acumulado:
        total_recebido = df[col_valor_pago_acumulado].sum()
    else:
        total_recebido = 0
    
    if col_saldo_devedor:
        total_saldo_devedor = df[col_saldo_devedor].sum()
    else:
        total_saldo_devedor = 0
    
    return {
        'total_pedidos': total_pedidos,
        'total_clientes': total_clientes,
        'faturamento_bruto': faturamento_bruto,
        'faturamento_liquido': faturamento_liquido,
        'total_deducoes': total_deducoes,
        'valor_medio_pedido': valor_medio_pedido,
        'total_itens': total_itens,
        'total_recebido': total_recebido,
        'total_saldo_devedor': total_saldo_devedor,
        'col_valor_cliente': col_valor_cliente,
        'col_valor_pago': col_valor_pago,
        'col_deducao': col_deducao,
        'col_quantidade': col_quantidade,
        'col_cliente': col_cliente,
        'col_campanha': col_campanha,
        'col_valor_pago_acumulado': col_valor_pago_acumulado,
        'col_saldo_devedor': col_saldo_devedor
    }

# ============================
# INTERFACE DO STREAMLIT
# ============================
def main():
    # Título principal
    st.markdown('<h1 class="main-header">📊 Demillus - Gestão de Pedidos</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.image("https://via.placeholder.com/150x150/1E88E5/FFFFFF?text=Demillus", use_container_width=True)
        st.markdown("## 📋 Menu")
        
        opcao = st.radio(
            "Navegue pelas funcionalidades:",
            ["📊 Dashboard", "📝 Cadastrar Pedido", "💰 Registrar Pagamento", "📈 Análises", "⚙️ Configurações"],
            index=0
        )
        
        st.markdown("---")
        st.caption(f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    # Carrega os dados
    with st.spinner("🔄 Carregando dados da planilha..."):
        df = carregar_dados()
    
    # Menu principal
    if opcao == "📊 Dashboard":
        mostrar_dashboard(df)
    elif opcao == "📝 Cadastrar Pedido":
        cadastrar_pedido(df)
    elif opcao == "💰 Registrar Pagamento":
        registrar_pagamento(df)
    elif opcao == "📈 Análises":
        mostrar_analises(df)
    elif opcao == "⚙️ Configurações":
        mostrar_configuracoes(df)

def mostrar_dashboard(df):
    """Exibe o dashboard principal com indicadores"""
    st.markdown("## 📊 Dashboard de Indicadores")
    
    if df is None or df.empty:
        st.info("💡 Nenhum pedido cadastrado ainda. Use a opção 'Cadastrar Pedido' para começar.")
        return
    
    # Calcula métricas
    metricas = calcular_metricas(df)
    
    # Cards de métricas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{metricas['total_pedidos']}</div>
                <div class="metric-label">Total de Pedidos</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">R$ {metricas['faturamento_liquido']:,.2f}</div>
                <div class="metric-label">Faturamento Líquido</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">R$ {metricas['total_recebido']:,.2f}</div>
                <div class="metric-label">Total Recebido</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">R$ {metricas['total_saldo_devedor']:,.2f}</div>
                <div class="metric-label">Saldo Devedor Total</div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Gráficos
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Faturamento por Campanha")
        if metricas['col_campanha'] and metricas['col_valor_cliente']:
            df_campanha = df.groupby(metricas['col_campanha'])[metricas['col_valor_cliente']].sum().reset_index()
            df_campanha = df_campanha.sort_values(metricas['col_valor_cliente'], ascending=True).tail(10)
            
            fig = px.bar(df_campanha, 
                        x=metricas['col_valor_cliente'], 
                        y=metricas['col_campanha'],
                        title="Top 10 Campanhas por Faturamento",
                        color=metricas['col_valor_cliente'],
                        color_continuous_scale='Blues')
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Dados insuficientes para exibir o gráfico")
    
    with col2:
        st.subheader("🏆 Top 5 Clientes")
        if metricas['col_cliente'] and metricas['col_valor_cliente']:
            df_clientes = df.groupby(metricas['col_cliente'])[metricas['col_valor_cliente']].sum().reset_index()
            df_clientes = df_clientes.sort_values(metricas['col_valor_cliente'], ascending=False).head(5)
            
            fig = px.pie(df_clientes, 
                        values=metricas['col_valor_cliente'], 
                        names=metricas['col_cliente'],
                        title="Concentração de Faturamento",
                        color_discrete_sequence=px.colors.sequential.Blues_r)
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Dados insuficientes para exibir o gráfico")
    
    # Tabela de pedidos com status de pagamento
    st.markdown("---")
    st.subheader("📋 Status de Pagamentos")
    
    if 'ID' in df.columns and 'VALOR _CLIENTE' in df.columns:
        # Verifica se as colunas de pagamento existem
        if 'VALOR_PAGO_ACUMULADO' not in df.columns:
            df['VALOR_PAGO_ACUMULADO'] = 0
        if 'SALDO_DEVEDOR' not in df.columns:
            df['SALDO_DEVEDOR'] = df['VALOR _CLIENTE']
        
        # Cria coluna de status
        df_status = df.copy()
        df_status['STATUS'] = df_status.apply(
            lambda row: '✅ Pago' if row['SALDO_DEVEDOR'] <= 0 else 
                       ('🟡 Parcial' if row['VALOR_PAGO_ACUMULADO'] > 0 else '🔴 Pendente'),
            axis=1
        )
        
        # Seleciona colunas para exibir
        colunas_exibir = []
        for col in ['ID', 'CLIENTE', 'VALOR _CLIENTE', 'VALOR_PAGO_ACUMULADO', 'SALDO_DEVEDOR', 'STATUS']:
            if col in df_status.columns:
                colunas_exibir.append(col)
        
        if colunas_exibir:
            df_exibir = df_status[colunas_exibir].head(10).copy()
            # Formata valores
            for col in df_exibir.columns:
                if 'VALOR' in col or 'SALDO' in col:
                    df_exibir[col] = df_exibir[col].apply(lambda x: f"R$ {x:,.2f}" if pd.notna(x) else "R$ 0,00")
            
            st.dataframe(df_exibir, use_container_width=True)
            
            # Estatísticas de pagamento
            col1, col2, col3 = st.columns(3)
            total_pagos = len(df_status[df_status['SALDO_DEVEDOR'] <= 0])
            total_parciais = len(df_status[(df_status['SALDO_DEVEDOR'] > 0) & (df_status['VALOR_PAGO_ACUMULADO'] > 0)])
            total_pendentes = len(df_status[df_status['VALOR_PAGO_ACUMULADO'] == 0])
            
            with col1:
                st.metric("✅ Pagos", total_pagos)
            with col2:
                st.metric("🟡 Parciais", total_parciais)
            with col3:
                st.metric("🔴 Pendentes", total_pendentes)

def cadastrar_pedido(df):
    """Formulário para cadastrar novos pedidos"""
    st.markdown("## 📝 Cadastrar Novo Pedido")
    
    with st.form("form_cadastro_pedido"):
        st.markdown("### Dados do Pedido")
        
        col1, col2 = st.columns(2)
        
        with col1:
            id_pedido = st.text_input("ID do Pedido", placeholder="Ex: PED001")
            campanha = st.text_input("Campanha", placeholder="Ex: BLACK_FRIDAY_2026")
            cliente = st.text_input("Cliente", placeholder="Nome do cliente")
            codigo = st.text_input("Código", placeholder="Código do produto")
            referencia = st.text_input("Referência", placeholder="Referência do produto")
        
        with col2:
            tamanho = st.text_input("Tamanho", placeholder="Ex: M, G, 42")
            cor = st.text_input("Cor", placeholder="Ex: Azul, Vermelho")
            quantidade = st.number_input("Quantidade", min_value=1, value=1, step=1)
            valor_pago = st.number_input("Valor Pago (R$)", min_value=0.0, value=0.0, step=1.0)
            deducao = st.number_input("Dedução (R$)", min_value=0.0, value=0.0, step=1.0)
        
        valor_cliente = valor_pago - deducao
        
        st.markdown(f"""
            <div style="background-color: #e3f2fd; padding: 1rem; border-radius: 5px; margin: 1rem 0;">
                <strong>💰 Valor Líquido para o Cliente:</strong> R$ {valor_cliente:,.2f}
            </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            submitted = st.form_submit_button("✅ Cadastrar Pedido", type="primary", use_container_width=True)
    
    if submitted:
        # Validações
        if not id_pedido or not cliente:
            st.error("❌ ID do Pedido e Cliente são obrigatórios!")
            return
        
        # Verifica se ID já existe
        if df is not None and not df.empty and 'ID' in df.columns:
            if id_pedido in df['ID'].values:
                st.error(f"❌ ID '{id_pedido}' já existe! Use um ID diferente.")
                return
        
        # Prepara novo pedido
        novo_pedido = {
            'ID': id_pedido,
            'CAMPANHA': campanha,
            'CLIENTE': cliente,
            'CODIGO': codigo,
            'REFERÊNCIA': referencia,
            'TAMANHO': tamanho,
            'COR': cor,
            'QUANTIDADE': quantidade,
            'VALOR_PAGO': valor_pago,
            'DEDUÇÃO': deducao,
            'VALOR _CLIENTE': valor_cliente,
            'VALOR_PAGO_ACUMULADO': 0,  # Inicialmente zero
            'SALDO_DEVEDOR': valor_cliente  # Saldo devedor igual ao valor total
        }
        
        try:
            # Adiciona ao DataFrame existente ou cria novo
            if df is None or df.empty:
                df_novo = pd.DataFrame([novo_pedido])
            else:
                df_novo = pd.concat([df, pd.DataFrame([novo_pedido])], ignore_index=True)
            
            # Salva na planilha
            if salvar_dados(df_novo):
                st.success("✅ Pedido cadastrado com sucesso!")
                
                # Resumo do pedido
                st.markdown("### 📋 Resumo do Pedido")
                resumo_df = pd.DataFrame([novo_pedido])
                st.dataframe(resumo_df, use_container_width=True)
                
                st.balloons()
            else:
                st.error("❌ Erro ao salvar o pedido na planilha!")
                
        except Exception as e:
            st.error(f"❌ Erro ao cadastrar pedido: {str(e)}")

def registrar_pagamento(df):
    """Interface para registrar pagamentos parciais"""
    st.markdown("## 💰 Registrar Pagamento")
    
    if df is None or df.empty:
        st.info("💡 Nenhum pedido cadastrado para registrar pagamento.")
        return
    
    # Verifica se as colunas necessárias existem
    if 'ID' not in df.columns or 'VALOR _CLIENTE' not in df.columns:
        st.error("❌ A planilha não possui as colunas necessárias para registrar pagamentos.")
        return
    
    # Adiciona colunas de pagamento se não existirem
    if 'VALOR_PAGO_ACUMULADO' not in df.columns:
        df['VALOR_PAGO_ACUMULADO'] = 0
    if 'SALDO_DEVEDOR' not in df.columns:
        df['SALDO_DEVEDOR'] = df['VALOR _CLIENTE']
    
    # Filtra pedidos com saldo devedor > 0
    df_com_debito = df[df['SALDO_DEVEDOR'] > 0].copy()
    
    if df_com_debito.empty:
        st.success("🎉 Todos os pedidos estão pagos!")
        return
    
    # Seleciona o pedido
    st.subheader("Selecione o Pedido para Receber Pagamento")
    
    # Cria opções para o selectbox
    opcoes = []
    for idx, row in df_com_debito.iterrows():
        opcao = f"{row['ID']} - {row['CLIENTE']} (Saldo: R$ {row['SALDO_DEVEDOR']:,.2f})"
        opcoes.append((idx, opcao))
    
    selecao = st.selectbox(
        "Pedido:",
        options=[opcao[1] for opcao in opcoes],
        index=0
    )
    
    # Encontra o índice selecionado
    idx_selecionado = None
    for idx, opcao in opcoes:
        if opcao == selecao:
            idx_selecionado = idx
            break
    
    if idx_selecionado is None:
        st.error("❌ Pedido não encontrado.")
        return
    
    # Dados do pedido selecionado
    pedido = df.loc[idx_selecionado]
    
    st.markdown("---")
    st.subheader("📋 Dados do Pedido")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.write(f"**ID:** {pedido['ID']}")
        st.write(f"**Cliente:** {pedido['CLIENTE']}")
    
    with col2:
        st.write(f"**Valor Total:** R$ {pedido['VALOR _CLIENTE']:,.2f}")
        st.write(f"**Já Pago:** R$ {pedido['VALOR_PAGO_ACUMULADO']:,.2f}")
    
    with col3:
        st.write(f"**Saldo Devedor:** R$ {pedido['SALDO_DEVEDOR']:,.2f}")
        status = "✅ Pago" if pedido['SALDO_DEVEDOR'] <= 0 else "🔴 Pendente"
        st.write(f"**Status:** {status}")
    
    st.markdown("---")
    st.subheader("💵 Registrar Pagamento")
    
    # Formulário de pagamento
    with st.form("form_pagamento"):
        valor_pagamento = st.number_input(
            "Valor do Pagamento (R$)",
            min_value=0.01,
            max_value=float(pedido['SALDO_DEVEDOR']),
            value=float(pedido['SALDO_DEVEDOR']),
            step=1.0,
            format="%.2f"
        )
        
        data_pagamento = st.date_input("Data do Pagamento", datetime.now())
        observacao = st.text_area("Observação (opcional)", placeholder="Ex: Pagamento via Pix, Transferência, etc.")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            submitted = st.form_submit_button("💳 Registrar Pagamento", type="primary", use_container_width=True)
    
    if submitted:
        try:
            # Atualiza os valores
            novo_pago = pedido['VALOR_PAGO_ACUMULADO'] + valor_pagamento
            novo_saldo = pedido['SALDO_DEVEDOR'] - valor_pagamento
            
            # Atualiza o DataFrame
            df.at[idx_selecionado, 'VALOR_PAGO_ACUMULADO'] = novo_pago
            df.at[idx_selecionado, 'SALDO_DEVEDOR'] = novo_saldo
            
            # Salva na planilha
            if salvar_dados(df):
                st.success(f"✅ Pagamento de R$ {valor_pagamento:,.2f} registrado com sucesso!")
                
                # Exibe resumo do pagamento
                st.markdown("### 📋 Resumo do Pagamento")
                resumo = {
                    'Pedido': pedido['ID'],
                    'Cliente': pedido['CLIENTE'],
                    'Valor Pago': f"R$ {valor_pagamento:,.2f}",
                    'Data': data_pagamento.strftime('%d/%m/%Y'),
                    'Novo Saldo Devedor': f"R$ {novo_saldo:,.2f}",
                    'Status': '✅ Pago' if novo_saldo <= 0 else '🟡 Parcial'
                }
                
                if observacao:
                    resumo['Observação'] = observacao
                
                st.json(resumo)
                
                if novo_saldo <= 0:
                    st.balloons()
                    st.success("🎉 Pedido completamente pago!")
                else:
                    st.info(f"💰 Saldo restante: R$ {novo_saldo:,.2f}")
            else:
                st.error("❌ Erro ao salvar o pagamento na planilha!")
                
        except Exception as e:
            st.error(f"❌ Erro ao registrar pagamento: {str(e)}")

def mostrar_analises(df):
    """Exibe análises detalhadas dos dados"""
    st.markdown("## 📈 Análises Detalhadas")
    
    if df is None or df.empty:
        st.info("💡 Nenhum pedido cadastrado para análise.")
        return
    
    metricas = calcular_metricas(df)
    
    tabs = st.tabs(["📊 Visão Geral", "💰 Análise de Pagamentos", "👥 Por Cliente", "📦 Por Produto"])
    
    with tabs[0]:
        st.subheader("Visão Geral do Negócio")
        
        # Métricas em cards
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total de Pedidos", metricas['total_pedidos'])
            st.metric("Total de Itens", int(metricas['total_itens']))
        
        with col2:
            st.metric("Faturamento Bruto", f"R$ {metricas['faturamento_bruto']:,.2f}")
            st.metric("Total de Deduções", f"R$ {metricas['total_deducoes']:,.2f}")
        
        with col3:
            st.metric("Faturamento Líquido", f"R$ {metricas['faturamento_liquido']:,.2f}")
            st.metric("Ticket Médio", f"R$ {metricas['valor_medio_pedido']:,.2f}")
        
        # Indicador de margem
        if metricas['faturamento_bruto'] > 0:
            margem = ((metricas['faturamento_liquido'] - metricas['faturamento_bruto']) / metricas['faturamento_bruto']) * 100
            st.metric("Margem Líquida", f"{margem:.1f}%", 
                     delta=f"{margem:.1f}%" if margem > 0 else f"{margem:.1f}%",
                     delta_color="normal" if margem > 0 else "inverse")
    
    with tabs[1]:
        st.subheader("💰 Análise de Pagamentos")
        
        if 'VALOR_PAGO_ACUMULADO' not in df.columns:
            df['VALOR_PAGO_ACUMULADO'] = 0
        if 'SALDO_DEVEDOR' not in df.columns:
            df['SALDO_DEVEDOR'] = df['VALOR _CLIENTE']
        
        # Métricas de pagamento
        col1, col2, col3 = st.columns(3)
        
        total_geral = df['VALOR _CLIENTE'].sum()
        total_recebido = df['VALOR_PAGO_ACUMULADO'].sum()
        total_saldo = df['SALDO_DEVEDOR'].sum()
        percentual_pago = (total_recebido / total_geral * 100) if total_geral > 0 else 0
        
        with col1:
            st.metric("Total a Receber", f"R$ {total_geral:,.2f}")
        with col2:
            st.metric("Total Recebido", f"R$ {total_recebido:,.2f}")
        with col3:
            st.metric("Percentual Recebido", f"{percentual_pago:.1f}%")
        
        # Gráfico de evolução de pagamentos
        st.subheader("📊 Status de Pagamentos por Pedido")
        
        # Cria categorias de status
        df['STATUS_PAGAMENTO'] = df.apply(
            lambda row: 'Pago' if row['SALDO_DEVEDOR'] <= 0 else 
                       ('Parcial' if row['VALOR_PAGO_ACUMULADO'] > 0 else 'Pendente'),
            axis=1
        )
        
        status_counts = df['STATUS_PAGAMENTO'].value_counts().reset_index()
        status_counts.columns = ['Status', 'Quantidade']
        
        fig = px.pie(status_counts, 
                    values='Quantidade', 
                    names='Status',
                    title="Distribuição de Status de Pagamento",
                    color='Status',
                    color_discrete_map={
                        'Pago': '#4CAF50',
                        'Parcial': '#FF9800',
                        'Pendente': '#F44336'
                    })
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        # Lista de pedidos com pagamentos pendentes
        st.subheader("📋 Pedidos com Pagamento Pendente")
        
        df_pendentes = df[df['SALDO_DEVEDOR'] > 0].copy()
        if not df_pendentes.empty:
            df_pendentes_exibir = df_pendentes[['ID', 'CLIENTE', 'VALOR _CLIENTE', 'VALOR_PAGO_ACUMULADO', 'SALDO_DEVEDOR']].head(20)
            for col in ['VALOR _CLIENTE', 'VALOR_PAGO_ACUMULADO', 'SALDO_DEVEDOR']:
                if col in df_pendentes_exibir.columns:
                    df_pendentes_exibir[col] = df_pendentes_exibir[col].apply(lambda x: f"R$ {x:,.2f}")
            st.dataframe(df_pendentes_exibir, use_container_width=True)
        else:
            st.success("🎉 Todos os pedidos estão pagos!")
    
    with tabs[2]:
        st.subheader("Análise por Cliente")
        
        if metricas['col_cliente'] and metricas['col_valor_cliente']:
            df_cliente = df.groupby(metricas['col_cliente']).agg({
                metricas['col_valor_cliente']: 'sum',
                'ID': 'count',
                'VALOR_PAGO_ACUMULADO': 'sum' if 'VALOR_PAGO_ACUMULADO' in df.columns else 'sum'
            }).reset_index()
            df_cliente.columns = ['Cliente', 'Faturamento', 'Qtd_Pedidos', 'Total_Pago']
            df_cliente['Saldo_Devedor'] = df_cliente['Faturamento'] - df_cliente['Total_Pago']
            df_cliente = df_cliente.sort_values('Faturamento', ascending=False)
            
            # Top 10 clientes
            fig = px.bar(df_cliente.head(10), 
                        x='Faturamento', 
                        y='Cliente',
                        text='Qtd_Pedidos',
                        title="Top 10 Clientes por Faturamento",
                        color='Faturamento',
                        color_continuous_scale='Blues')
            fig.update_traces(texttemplate='%{text} pedidos', textposition='outside')
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Tabela completa de clientes
            st.subheader("Lista de Clientes")
            df_cliente_exibir = df_cliente.copy()
            df_cliente_exibir['Faturamento'] = df_cliente_exibir['Faturamento'].apply(lambda x: f"R$ {x:,.2f}")
            df_cliente_exibir['Total_Pago'] = df_cliente_exibir['Total_Pago'].apply(lambda x: f"R$ {x:,.2f}")
            df_cliente_exibir['Saldo_Devedor'] = df_cliente_exibir['Saldo_Devedor'].apply(lambda x: f"R$ {x:,.2f}")
            st.dataframe(df_cliente_exibir, use_container_width=True)
    
    with tabs[3]:
        st.subheader("Análise por Produto")
        
        if 'REFERÊNCIA' in df.columns and metricas['col_valor_cliente']:
            df_produto = df.groupby('REFERÊNCIA')[metricas['col_valor_cliente']].sum().reset_index()
            df_produto.columns = ['Referência', 'Faturamento']
            df_produto = df_produto.sort_values('Faturamento', ascending=False)
            
            # Top produtos
            fig = px.pie(df_produto.head(10), 
                        values='Faturamento', 
                        names='Referência',
                        title="Top 10 Produtos por Faturamento",
                        color_discrete_sequence=px.colors.sequential.Blues_r)
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Lista de produtos
            st.dataframe(df_produto.head(20), use_container_width=True)

def mostrar_configuracoes(df):
    """Configurações do sistema"""
    st.markdown("## ⚙️ Configurações")
    
    st.info("🔧 Esta seção permite visualizar e gerenciar as configurações do sistema.")
    
    # Status da conexão
    st.subheader("📊 Status da Conexão")
    client = conectar_google_sheets()
    if client:
        st.success("✅ Conectado ao Google Sheets")
        st.info("📄 Planilha: Demillus | Aba: PEDIDOS")
    else:
        st.error("❌ Falha na conexão com Google Sheets")
    
    # Dados atuais
    if df is not None and not df.empty:
        st.subheader("📋 Resumo dos Dados")
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**Total de registros:** {len(df)}")
            st.write(f"**Colunas:** {', '.join(df.columns.tolist())}")
        
        with col2:
            # Estatísticas básicas
            st.write("**Tipos de dados:**")
            tipos = df.dtypes.to_dict()
            for col, tipo in tipos.items():
                st.write(f"- {col}: {tipo}")
    
    # Exportar dados
    st.subheader("📥 Exportar Dados")
    if df is not None and not df.empty:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar Dados (CSV)",
            data=csv,
            file_name=f"demillus_pedidos_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    # Informações do sistema
    st.subheader("ℹ️ Informações do Sistema")
    st.write(f"**Versão:** 2.0.0")
    st.write(f"**Data/Hora:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

if __name__ == "__main__":
    main()
