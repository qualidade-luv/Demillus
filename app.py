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
    </style>
""", unsafe_allow_html=True)

# ============================
# CONEXÃO COM GOOGLE SHEETS
# ============================
def conectar_google_sheets():
    """Estabelece conexão com Google Sheets usando credenciais do Streamlit Secrets"""
    try:
        # Obtém as credenciais do secrets
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # Define os escopos necessários
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # Cria as credenciais
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        
        # Conecta ao Google Sheets
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
        
        # Abre a planilha pelo nome
        try:
            spreadsheet = client.open("Demillus")
        except:
            st.error("❌ Planilha 'Demillus' não encontrada. Verifique o nome.")
            return None
        
        # Seleciona a aba PEDIDOS
        try:
            worksheet = spreadsheet.worksheet("PEDIDOS")
        except:
            st.error("❌ Aba 'PEDIDOS' não encontrada. Verifique o nome da aba.")
            return None
        
        # Obtém todos os dados
        dados = worksheet.get_all_values()
        
        if not dados or len(dados) < 2:
            st.warning("⚠️ A planilha está vazia ou contém apenas cabeçalho.")
            return None
        
        # Primeira linha como cabeçalho
        cabecalho = dados[0]
        dados = dados[1:]
        
        # Cria DataFrame
        df = pd.DataFrame(dados, columns=cabecalho)
        
        # Limpeza e conversão de tipos
        df = df.replace('', pd.NA)
        
        # Converte colunas numéricas
        colunas_numericas = ['QUANTIDADE', 'VALOR_PAGO', 'DEDUÇÃO', 'VALOR _CLIENTE']
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
            'total_itens': 0
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
    
    for col in colunas:
        if 'VALOR _CLIENTE' in col or 'VALOR_CLIENTE' in col:
            col_valor_cliente = col
        elif 'VALOR_PAGO' in col:
            col_valor_pago = col
        elif 'DEDUÇÃO' in col or 'DEDUCAO' in col:
            col_deducao = col
        elif 'QUANTIDADE' in col:
            col_quantidade = col
        elif 'CLIENTE' in col:
            col_cliente = col
        elif 'CAMPANHA' in col:
            col_campanha = col
    
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
    
    return {
        'total_pedidos': total_pedidos,
        'total_clientes': total_clientes,
        'faturamento_bruto': faturamento_bruto,
        'faturamento_liquido': faturamento_liquido,
        'total_deducoes': total_deducoes,
        'valor_medio_pedido': valor_medio_pedido,
        'total_itens': total_itens,
        'col_valor_cliente': col_valor_cliente,
        'col_valor_pago': col_valor_pago,
        'col_deducao': col_deducao,
        'col_quantidade': col_quantidade,
        'col_cliente': col_cliente,
        'col_campanha': col_campanha
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
            ["📊 Dashboard", "📝 Cadastrar Pedido", "📈 Análises", "⚙️ Configurações"],
            index=0
        )
        
        st.markdown("---")
        st.caption(f"Última atualização: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    # Carrega os dados
    with st.spinner("🔄 Carregando dados da planilha..."):
        df = carregar_dados()
    
    if df is None or df.empty:
        st.warning("⚠️ Nenhum dado encontrado na planilha. Cadastre seu primeiro pedido!")
    
    # Menu principal
    if opcao == "📊 Dashboard":
        mostrar_dashboard(df)
    elif opcao == "📝 Cadastrar Pedido":
        cadastrar_pedido(df)
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
                <div class="metric-value">R$ {metricas['valor_medio_pedido']:,.2f}</div>
                <div class="metric-label">Ticket Médio</div>
            </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
            <div class="metric-card">
                <div class="metric-value">{metricas['total_clientes']}</div>
                <div class="metric-label">Clientes Ativos</div>
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
    
    # Tabela de dados recentes
    st.markdown("---")
    st.subheader("📋 Últimos Pedidos")
    
    # Prepara dados para exibição
    colunas_exibir = []
    for col in ['ID', 'CAMPANHA', 'CLIENTE', 'REFERÊNCIA', 'QUANTIDADE', 'VALOR _CLIENTE']:
        if col in df.columns:
            colunas_exibir.append(col)
    
    if colunas_exibir:
        df_exibir = df[colunas_exibir].head(10).copy()
        # Formata valores
        for col in df_exibir.columns:
            if 'VALOR' in col or 'DEDUÇÃO' in col:
                df_exibir[col] = df_exibir[col].apply(lambda x: f"R$ {x:,.2f}" if pd.notna(x) else "R$ 0,00")
        
        st.dataframe(df_exibir, use_container_width=True)
    else:
        st.info("Nenhum dado disponível para exibir")

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
            'VALOR _CLIENTE': valor_cliente
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

def mostrar_analises(df):
    """Exibe análises detalhadas dos dados"""
    st.markdown("## 📈 Análises Detalhadas")
    
    if df is None or df.empty:
        st.info("💡 Nenhum pedido cadastrado para análise.")
        return
    
    metricas = calcular_metricas(df)
    
    tabs = st.tabs(["📊 Visão Geral", "📈 Tendências", "👥 Por Cliente", "📦 Por Produto"])
    
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
        st.subheader("Tendências Temporais")
        
        # Distribuição por campanha
        if metricas['col_campanha'] and metricas['col_valor_cliente']:
            df_campanha = df.groupby(metricas['col_campanha']).agg({
                metricas['col_valor_cliente']: 'sum',
                metricas['col_quantidade']: 'sum' if metricas['col_quantidade'] else 'count'
            }).reset_index()
            
            # Gráfico de barras empilhadas
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_campanha[metricas['col_campanha']],
                y=df_campanha[metricas['col_valor_cliente']],
                name='Faturamento',
                marker_color='#1E88E5'
            ))
            
            if metricas['col_quantidade']:
                fig.add_trace(go.Scatter(
                    x=df_campanha[metricas['col_campanha']],
                    y=df_campanha[metricas['col_quantidade']],
                    name='Quantidade',
                    yaxis='y2',
                    marker_color='#FF6B6B'
                ))
                
                fig.update_layout(
                    yaxis2=dict(
                        overlaying='y',
                        side='right'
                    )
                )
            
            fig.update_layout(
                title="Faturamento por Campanha",
                xaxis_title="Campanha",
                yaxis_title="Faturamento (R$)",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with tabs[2]:
        st.subheader("Análise por Cliente")
        
        if metricas['col_cliente'] and metricas['col_valor_cliente']:
            df_cliente = df.groupby(metricas['col_cliente']).agg({
                metricas['col_valor_cliente']: 'sum',
                'ID': 'count'
            }).reset_index()
            df_cliente.columns = ['Cliente', 'Faturamento', 'Qtd_Pedidos']
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
        st.info(f"📄 Planilha: Demillus | Aba: PEDIDOS")
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
    st.write(f"**Versão:** 1.0.0")
    st.write(f"**Data/Hora:** {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

if __name__ == "__main__":
    main()
