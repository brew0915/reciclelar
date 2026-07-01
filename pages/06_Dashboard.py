from datetime import date, timedelta
from database import engine
from menu import render_menu
import pandas as pd
from seguranca import exigir_perfil
from sqlalchemy import text
import streamlit as st

# =====================================
# 1. CONFIGURAÇÃO DA PÁGINA (Deve ser o primeiro comando)
# =====================================
st.set_page_config(
    page_title="Dashboard Executivo | Business Intelligence", 
    page_icon="📊", 
    layout="wide"
)

def carregar_css_e_estilos():
    # Tenta carregar o arquivo CSS externo se existir
    try:
        with open("assets/style.css", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass
        
    # Estilização corporativa e fix para quebras de texto em KPIs
    st.markdown(
        """
        <style>
        /* Ajuste fino de métricas para telas de alta resolução */
        [data-testid="stMetricValue"] > div {
            white-space: normal !important;
            word-wrap: break-word !important;
            overflow-wrap: break-word !important;
            font-size: 1.85rem !important;
            font-weight: 700 !important;
            letter-spacing: -0.02em;
        }
        [data-testid="stMetricValue"] {
            overflow: visible !important;
            max-width: 100% !important;
        }
        /* Ajuste sutil nos headers de containers */
        .stHeading h3 {
            font-size: 1.3rem !important;
            font-weight: 600 !important;
            color: #1e293b;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

carregar_css_e_estilos()
render_menu()

# =====================================
# 2. SEGURANÇA E CONTEXTO DE CONEXÃO
# =====================================
if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()

exigir_perfil(["ADMIN"])

filial_id = st.session_state.get("filial_operacao")
if filial_id is None:
    st.error("Aviso: Selecione uma unidade filial no menu lateral para consolidar os dados.")
    st.stop()

filial_id = int(filial_id)

# Carga de metadados da filial de forma consolidada
with engine.connect() as conn:
    filial_nome = conn.execute(
        text("SELECT nome FROM filiais WHERE id = :id"), {"id": filial_id}
    ).scalar()

    status_caixa = conn.execute(
        text(
            """
            SELECT COUNT(*)
            FROM fechamento_caixa
            WHERE filial_id = :filial_id AND data_fechamento = CURRENT_DATE
        """
        ),
        {"filial_id": filial_id},
    ).scalar()

# =====================================
# 3. FILTROS E PARÂMETROS OPERACIONAIS (SIDEBAR)
# =====================================
st.sidebar.header("🎯 Filtros de Análise")

periodo = st.sidebar.selectbox(
    "Período de Competência",
    ["Hoje", "Últimos 7 dias", "Últimos 30 dias", "Mês Atual", "Ano Atual", "Personalizado"],
)

hoje = date.today()

if periodo == "Hoje":
    data_inicio = hoje
    data_fim = hoje
elif periodo == "Últimos 7 dias":
    data_inicio = hoje - timedelta(days=7)
    data_fim = hoje
elif periodo == "Últimos 30 dias":
    data_inicio = hoje - timedelta(days=30)
    data_fim = hoje
elif periodo == "Mês Atual":
    data_inicio = hoje.replace(day=1)
    data_fim = hoje
elif periodo == "Ano Atual":
    data_inicio = date(hoje.year, 1, 1)
    data_fim = hoje
else:
    data_inicio = st.sidebar.date_input("Data Inicial", hoje - timedelta(days=30))
    data_fim = st.sidebar.date_input("Data Final", hoje)

# =====================================
# 4. CABEÇALHO CORPORATIVO
# =====================================
col_tit, col_status = st.columns([3, 1], vertical_alignment="center")

with col_tit:
    st.title("Performance Executiva & Controladoria")
    st.caption(f"Unidade Analisada: **{filial_nome}** | Período de Gestão: {data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')}")

with col_status:
    if status_caixa > 0:
        st.error("🔒 Fluxo de Caixa: Fechado")
    else:
        st.success("🟢 Fluxo de Caixa: Aberto")

st.divider()

# =====================================
# 5. BUSINESS INTELLIGENCE (LEITURA DE DADOS)
# =====================================
with engine.connect() as conn:
    # Saldo Inicial do Caixa
    saldo_inicial = conn.execute(
        text(
            """
            SELECT COALESCE(SUM(saldo_inicial), 0)
            FROM caixa
            WHERE filial_id = :filial_id AND data_caixa = CURRENT_DATE
        """
        ),
        {"filial_id": filial_id},
    ).scalar()

    # Movimentações Financeiras Consolidadas
    movimentacao = conn.execute(
        text(
            """
            SELECT COALESCE(SUM(CASE WHEN tipo = 'ENTRADA' THEN valor ELSE -valor END), 0)
            FROM financeiro_movimentacao
            WHERE filial_id = :filial_id AND DATE(data_movimentacao) = CURRENT_DATE
        """
        ),
        {"filial_id": filial_id},
    ).scalar()

    saldo_caixa = saldo_inicial + movimentacao

    # Compras consolidadas
    total_comprado = conn.execute(
        text(
            """
            SELECT COALESCE(SUM(ic.valor_total), 0)
            FROM compras c
            INNER JOIN itens_compra ic ON ic.compra_id = c.id
            WHERE c.filial_id = :filial_id AND c.data_compra::date BETWEEN :inicio AND :fim
        """
        ),
        {"inicio": data_inicio, "fim": data_fim, "filial_id": filial_id},
    ).scalar()

    # Vendas consolidadas
    total_vendido = conn.execute(
        text(
            """
            SELECT COALESCE(SUM(valor_total), 0)
            FROM vendas
            WHERE filial_id = :filial_id AND data_venda::date BETWEEN :inicio AND :fim
        """
        ),
        {"inicio": data_inicio, "fim": data_fim, "filial_id": filial_id},
    ).scalar()

lucro = total_vendido - total_comprado
# Ajustado para Margem Bruta de Mercado (Lucro / Receita de Vendas)
margem_lucro = (lucro / total_vendido * 100) if total_vendido > 0 else 0.0

# =====================================
# 6. VISUALIZAÇÃO: CARD DE INDICADORES (KPIs)
# =====================================
st.markdown("### 📈 Principais Indicadores de Performance")

with st.container(border=True):
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("🛒 Custo de Compras (Período)", f"R$ {total_comprado:,.2f}")
    kpi2.metric("💰 Faturamento de Vendas (Período)", f"R$ {total_vendido:,.2f}")
    
    # Delta formatado dinamicamente como porcentagem de margem sobre a venda
    kpi3.metric(
        "📈 Resultado Bruto", 
        f"R$ {lucro:,.2f}", 
        delta=f"{margem_lucro:.1f}% Margem",
        delta_color="normal" if lucro >= 0 else "inverse"
    )
    kpi4.metric("💵 Saldo Disponível em Caixa", f"R$ {saldo_caixa:,.2f}")

# =====================================
# 7. DETALHAMENTO: FLUXO DE CAIXA E POSIÇÃO DE ESTOQUE
# =====================================
col_cx, col_est = st.columns([1, 1])

with col_cx:
    with st.container(border=True):
        st.markdown("### 💵 Conciliação de Caixa (Hoje)")
        
        # HTML/CSS para criar cartões executivos que NUNCA cortam o texto
        def criar_card_financeiro(titulo, valor, cor_fundo="#f8fafc", cor_texto="#0f172a"):
            return f"""
            <div style="
                background-color: {cor_fundo}; 
                padding: 12px 16px; 
                border-radius: 8px; 
                border: 1px solid #e2e8f0;
                margin-bottom: 8px;
                box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            ">
                <p style="margin: 0; font-size: 0.85rem; color: #64748b; font-weight: 500; text-transform: uppercase; letter-spacing: 0.05em;">{titulo}</p>
                <p style="margin: 4px 0 0 0; font-size: 1.4rem; color: {cor_texto}; font-weight: 700; white-space: normal; word-break: break-all;">{valor}</p>
            </div>
            """
        
        # Layout em 3 colunas, mas agora usando os cartões HTML imunes a cortes
        cx1, cx2, cx3 = st.columns(3)
        
        with cx1:
            st.markdown(criar_card_financeiro("Abertura / Reserva", f"R$ {saldo_inicial:,.2f}"), unsafe_allow_html=True)
        with cx2:
            # Destaca a variação (Verde se positiva, Vermelho se negativa)
            cor_variacao = "#16a34a" if movimentacao >= 0 else "#dc2626"
            st.markdown(criar_card_financeiro("Variação Líquida", f"R$ {movimentacao:,.2f}", cor_texto=cor_variacao), unsafe_allow_html=True)
        with cx3:
            # Destaca o saldo operacional final com um fundo sutil azul corporativo
            st.markdown(criar_card_financeiro("Saldo Operacional", f"R$ {saldo_caixa:,.2f}", cor_fundo="#eff6ff", cor_texto="#1e40af"), unsafe_allow_html=True)
with col_est:
    with st.container(border=True):
        st.markdown("### 📦 Posição Volumétrica de Estoque")
        with engine.connect() as conn:
            estoque = pd.read_sql(
                text(
                    """
                    SELECT 
                        m.descricao AS "Material",
                        COALESCE(SUM(CASE WHEN e.tipo = 'ENTRADA' THEN e.quantidade ELSE -e.quantidade END), 0) AS "Estoque (KG)"
                    FROM materiais m
                    LEFT JOIN estoque_movimentacao e ON m.id = e.material_id AND e.filial_id = :filial_id
                    GROUP BY m.descricao
                    ORDER BY "Estoque (KG)" DESC
                """
                ),
                conn,
                params={"filial_id": filial_id},
            )
        if not estoque.empty:
            st.dataframe(
                estoque,
                use_container_width=True,
                hide_index=True,
                height=138,
                column_config={"Estoque (KG)": st.column_config.NumberColumn(format="%.3f KG")},
            )
        else:
            st.info("Nenhuma movimentação de estoque registrada para esta filial.")

# =====================================
# 8. ANÁLISE HISTÓRICA & TENDÊNCIAS (GRÁFICOS)
# =====================================
st.divider()
st.markdown("### 📊 Evolução Temporal e Comercial")
g1, g2 = st.columns(2)

with g1:
    with st.container(border=True):
        st.markdown("**Evolução Mensal de Compras (R$)**")
        with engine.connect() as conn:
            compras_mes = pd.read_sql(
                text(
                    """
                    SELECT DATE_TRUNC('month', c.data_compra) AS mes, SUM(ic.valor_total) AS total
                    FROM compras c
                    INNER JOIN itens_compra ic ON ic.compra_id = c.id
                    WHERE c.filial_id = :filial_id
                    GROUP BY mes ORDER BY mes
                """
                ),
                conn,
                params={"filial_id": filial_id},
            )
        if not compras_mes.empty:
            compras_mes["mes"] = pd.to_datetime(compras_mes["mes"])
            st.line_chart(compras_mes.set_index("mes"), y="total", color="#2563eb", height=220)
        else:
            st.caption("Dados históricos insuficientes para projeção de compras.")

with g2:
    with st.container(border=True):
        st.markdown("**Evolução Mensal de Vendas (R$)**")
        with engine.connect() as conn:
            vendas_mes = pd.read_sql(
                text(
                    """
                    SELECT DATE_TRUNC('month', data_venda) AS mes, SUM(valor_total) AS total
                    FROM vendas
                    WHERE filial_id = :filial_id
                    GROUP BY mes ORDER BY mes
                """
                ),
                conn,
                params={"filial_id": filial_id},
            )
        if not vendas_mes.empty:
            vendas_mes["mes"] = pd.to_datetime(vendas_mes["mes"])
            st.line_chart(vendas_mes.set_index("mes"), y="total", color="#16a34a", height=220)
        else:
            st.caption("Dados históricos insuficientes para projeção de vendas.")

# =====================================
# 9. CURVA DE MATERIAIS E FORNECEDORES
# =====================================
col_graph, col_data = st.columns([1, 1])

with col_graph:
    with st.container(border=True):
        st.markdown("**Mix de Materiais Mais Adquiridos (Top 10 Volumétrico)**")
        with engine.connect() as conn:
            top_materiais = pd.read_sql(
                text(
                    """
                    SELECT m.descricao, SUM(ic.quantidade) AS quantidade
                    FROM itens_compra ic
                    INNER JOIN compras c ON ic.compra_id = c.id
                    INNER JOIN materiais m ON ic.material_id = m.id
                    WHERE c.filial_id = :filial_id AND c.data_compra::date BETWEEN :inicio AND :fim
                    GROUP BY m.descricao ORDER BY quantidade DESC LIMIT 10
                """
                ),
                conn,
                params={"filial_id": filial_id, "inicio": data_inicio, "fim": data_fim},
            )
        if not top_materiais.empty:
            st.bar_chart(top_materiais.set_index("descricao"), y="quantidade", color="#3b82f6", height=200)
        else:
            st.caption("Sem dados volumétricos no período selecionado.")

with col_data:
    with st.container(border=True):
        st.markdown("**Curva ABC de Fornecedores por Volume Financeiro**")
        with engine.connect() as conn:
            fornecedores = pd.read_sql(
                text(
                    """
                    SELECT COALESCE(f.nome, c.fornecedor_avulso) AS "Fornecedor", SUM(ic.valor_total) AS "Total Contratado"
                    FROM compras c
                    INNER JOIN itens_compra ic ON ic.compra_id = c.id
                    LEFT JOIN fornecedores f ON c.fornecedor_id = f.id
                    WHERE c.filial_id = :filial_id AND c.data_compra::date BETWEEN :inicio AND :fim
                    GROUP BY "Fornecedor" ORDER BY "Total Contratado" DESC
                """
                ),
                conn,
                params={"filial_id": filial_id, "inicio": data_inicio, "fim": data_fim},
            )
        if not fornecedores.empty:
            st.dataframe(
                fornecedores,
                use_container_width=True,
                hide_index=True,
                height=200,
                column_config={"Total Contratado": st.column_config.NumberColumn(format="R$ %.2f")},
            )
        else:
            st.caption("Nenhuma contratação de fornecedor identificada no período.")

# =====================================
# 10. RANKINGS CORPORATIVOS E AUDITORIA
# =====================================
st.divider()
st.markdown("### 🏭 Escoamento e Destinação Industrial")
with engine.connect() as conn:
    industrias = pd.read_sql(
        text(
            """
            SELECT i.nome AS "Indústria Parceira", SUM(v.valor_total) AS "Faturamento Destinado (R$)"
            FROM vendas v
            INNER JOIN industrias i ON v.industria_id = i.id
            WHERE v.filial_id = :filial_id AND v.data_venda::date BETWEEN :inicio AND :fim
            GROUP BY i.nome ORDER BY "Faturamento Destinado (R$)" DESC LIMIT 10
        """
        ),
        conn,
        params={"filial_id": filial_id, "inicio": data_inicio, "fim": data_fim},
    )
if not industrias.empty:
    st.dataframe(
        industrias,
        use_container_width=True,
        hide_index=True,
        column_config={"Faturamento Destinado (R$)": st.column_config.NumberColumn(format="R$ %.2f")},
    )
else:
    st.info("Nenhum registro de escoamento ou venda industrial no período selecionado.")

# Últimas Transações (Painel de Auditoria Rápida)
st.divider()
t_comp, t_vend = st.columns(2)

with t_comp:
    with st.container(border=True):
        st.markdown("**Últimas Compras Realizadas**")
        with engine.connect() as conn:
            ultimas_compras = pd.read_sql(
                text(
                    """
                    SELECT c.id AS "Ref", COALESCE(f.nome, c.fornecedor_avulso) AS "Fornecedor", 
                           SUM(ic.valor_total) AS "Valor Total", c.data_compra AS "Data/Hora"
                    FROM compras c
                    INNER JOIN itens_compra ic ON ic.compra_id = c.id
                    LEFT JOIN fornecedores f ON c.fornecedor_id = f.id
                    WHERE c.filial_id = :filial_id
                    GROUP BY c.id, "Fornecedor", c.data_compra ORDER BY c.id DESC LIMIT 10
                """
                ),
                conn,
                params={"filial_id": filial_id},
            )
        if not ultimas_compras.empty:
            st.dataframe(
                ultimas_compras,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Valor Total": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Data/Hora": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
                },
            )

with t_vend:
    with st.container(border=True):
        st.markdown("**Últimas Vendas Faturadas**")
        with engine.connect() as conn:
            ultimas_vendas = pd.read_sql(
                text(
                    """
                    SELECT v.id AS "Ref", i.nome AS "Indústria", m.descricao AS "Material", 
                           v.quantidade AS "Qtd (KG)", v.valor_total AS "Total Bruto", v.data_venda AS "Data Emissão"
                    FROM vendas v
                    INNER JOIN industrias i ON v.industria_id = i.id
                    INNER JOIN materiais m ON v.material_id = m.id
                    WHERE v.filial_id = :filial_id ORDER BY v.id DESC LIMIT 10
                """
                ),
                conn,
                params={"filial_id": filial_id},
            )
        if not ultimas_vendas.empty:
            st.dataframe(
                ultimas_vendas,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Qtd (KG)": st.column_config.NumberColumn(format="%.3f"),
                    "Total Bruto": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Data Emissão": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
                },
            )