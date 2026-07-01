from database import engine
from menu import render_menu
import pandas as pd
from seguranca import exigir_perfil
from sqlalchemy import text
import streamlit as st

# =====================================
# 1. CONFIGURAÇÃO DA PÁGINA
# =====================================
st.set_page_config(
    page_title="Recicle Lar — ERP",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def carregar_css():
    with open("assets/style.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


carregar_css()

# =====================================
# 2. CONTROLE DE ACESSO E CONTEXTO
# =====================================
if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()

exigir_perfil(["ADMIN"])
render_menu()

filial_id = st.session_state.get("filial_operacao")

# =====================================
# 3. INTERFACE PRINCIPAL
# =====================================
st.title("♻️ Recicle Lar")
st.caption("Central de Comando Operacional e Controladoria Consolidadas")
st.divider()

if filial_id is None:
    st.warning("📊 Por favor, selecione uma Filial no menu lateral para consolidar os indicadores operacionais.")
    st.stop()

# =====================================
# 4. PROCESSAMENTO DE DADOS (KPIs)
# =====================================
with engine.connect() as conn:
    # Nome da Filial Atual
    filial_nome = conn.execute(
        text("SELECT nome FROM filiais WHERE id = :filial_id"),
        {"filial_id": filial_id},
    ).scalar()

    # Volumetria de Estoque Atualizado
    res_estoque = conn.execute(
        text(
            """
            SELECT COALESCE(
                SUM(CASE WHEN tipo = 'ENTRADA' THEN quantidade ELSE -quantidade END), 
                0
            )
            FROM estoque_movimentacao
            WHERE filial_id = :filial_id
        """
        ),
        {"filial_id": filial_id},
    ).scalar()

    # Custo de Aquisição de Insumos (Compras)
    res_compras = conn.execute(
        text(
            """
            SELECT COALESCE(SUM(valor_total), 0)
            FROM compras
            WHERE filial_id = :filial_id
        """
        ),
        {"filial_id": filial_id},
    ).scalar()

    # Receita Bruta de Escoamento (Vendas)
    res_vendas = conn.execute(
        text(
            """
            SELECT COALESCE(SUM(valor_total), 0)
            FROM vendas
            WHERE filial_id = :filial_id
        """
        ),
        {"filial_id": filial_id},
    ).scalar()

# Tipagem estrita e cálculo de margem operacional
estoque = float(res_estoque) if res_estoque else 0.0
compras = float(res_compras) if res_compras else 0.0
vendas = float(res_vendas) if res_vendas else 0.0
lucro = vendas - compras

# =====================================
# 5. COCKPIT DE MÉTRICAS OPERACIONAIS
# =====================================
st.subheader(f"📊 Desempenho Econômico — {filial_nome or 'Unidade de Negócio'}")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="📦 Balanço Volumétrico",
        value=f"{estoque:,.2f} KG",
        help="Volume total de materiais armazenados no pátio desta unidade.",
    )

with col2:
    st.metric(
        label="💰 Faturamento Bruto",
        value=f"R$ {vendas:,.2f}",
        help="Total acumulado gerado pelo escoamento de recicláveis para indústrias.",
    )

with col3:
    st.metric(
        label="🛒 Custo de Aquisição",
        value=f"R$ {compras:,.2f}",
        help="Total desembolsado no pagamento a fornecedores e catadores.",
    )

with col4:
    # Sinalização visual de performance financeira
    delta_lucro = "Positivo" if lucro >= 0 else "Déficit"
    st.metric(
        label="📈 Resultado Líquido Operacional",
        value=f"R$ {lucro:,.2f}",
        delta=delta_lucro if lucro != 0 else None,
        help="Diferença direta entre receita de vendas e custo de compras na unidade.",
    )

# =====================================
# 6. ATALHOS GESTIONAIS E RESUMO
# =====================================
st.divider()
col_links, col_resumo = st.columns([6, 4])

with col_links:
    st.subheader("🚀 Painel de Navegação Direta")

    c1, c2 = st.columns(2)
    with c1:
        with st.container(border=True):
            st.markdown("**📁 Cadastros Estruturais**")
            st.page_link("pages/01_Materiais.py", label="📦 Catálogo de Materiais", use_container_width=True)
            st.page_link("pages/02_Fornecedores.py", label="👥 Carteira de Fornecedores", use_container_width=True)
            st.page_link("pages/05_Industrias.py", label="🏭 Indústrias Parceiras", use_container_width=True)

    with c2:
        with st.container(border=True):
            st.markdown("**💸 Fluxos Financeiros**")
            st.page_link("pages/03_Compras.py", label="🛒 Registrar Entrada / Compra", use_container_width=True)
            st.page_link("pages/04_Vendas.py", label="💰 Registrar Escoamento / Venda", use_container_width=True)
            st.page_link("pages/11_Abrir_Caixa.py", label="💵 Controle de Caixa Diário", use_container_width=True)

    # REMOVIDO: type="primary"
    st.page_link(
        "pages/06_Dashboard.py",
        label="📊 Acessar Business Intelligence Completo (BI)",
        use_container_width=True,
    )

    
with col_resumo:
    st.subheader("📋 Status da Plataforma")
    with st.container(border=True):
        st.markdown(
            """
            **Módulos Operacionais Integrados:**
            *   **Suprimentos:** Precificação inteligente por tipo de polímero/metal.
            *   **Logística Reversa:** Controle severo de entradas por pesagem física.
            *   **Controladoria:** Conciliação integrada com abertura, suprimento e fechamento contábil.
            *   **Análise Fiscal:** Demonstrativo de Resultado de Exercício (DRE) gerado dinamicamente no módulo de BI.
            """
        )