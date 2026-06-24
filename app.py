import streamlit as st

st.set_page_config(
    page_title="Recicle Lar",
    page_icon="♻️",
    layout="wide",
    initial_sidebar_state="expanded"
)

from menu import render_menu
from seguranca import exigir_perfil

# =====================================
# SEGURANÇA
# =====================================

if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()

exigir_perfil(["ADMIN"])

# =====================================
# MENU
# =====================================

render_menu()

# =====================================
# CSS
# =====================================

def carregar_css():

    with open(
        "assets/style.css",
        encoding="utf-8"
    ) as f:

        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True
        )

carregar_css()

# =====================================
# HOME
# =====================================

st.title("♻️ Recicle Lar")

st.caption(
    "Sistema de Gestão para Pontos de Reciclagem"
)

st.divider()

from sqlalchemy import text
from database import engine

filial_id = st.session_state.get(
    "filial_operacao"
)

with engine.connect() as conn:

    estoque = conn.execute(
        text("""
            SELECT COALESCE(
                SUM(
                    CASE
                        WHEN tipo = 'ENTRADA'
                        THEN quantidade
                        ELSE -quantidade
                    END
                ),
                0
            )
            FROM estoque_movimentacao
            WHERE filial_id = :filial_id
        """),
        {
            "filial_id": filial_id
        }
    ).scalar()

    compras = conn.execute(
        text("""
            SELECT COALESCE(
                SUM(valor_total),
                0
            )
            FROM compras
            WHERE filial_id = :filial_id
        """),
        {
            "filial_id": filial_id
        }
    ).scalar()

    vendas = conn.execute(
        text("""
            SELECT COALESCE(
                SUM(valor_total),
                0
            )
            FROM vendas
            WHERE filial_id = :filial_id
        """),
        {
            "filial_id": filial_id
        }
    ).scalar()

lucro = vendas - compras

# =====================================
# KPIs
# =====================================

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "📦 Estoque Atual",
        f"{estoque:,.2f} KG"
    )

with col2:
    st.metric(
        "🛒 Compras",
        f"R$ {compras:,.2f}"
    )

with col3:
    st.metric(
        "💰 Vendas",
        f"R$ {vendas:,.2f}"
    )

with col4:
    st.metric(
        "📈 Lucro",
        f"R$ {lucro:,.2f}"
    )

# =====================================
# ACESSO RÁPIDO
# =====================================

st.divider()

st.subheader("🚀 Acesso Rápido")

c1, c2, c3 = st.columns(3)

with c1:

    st.page_link(
        "pages/01_Materiais.py",
        label="📦 Materiais"
    )

    st.page_link(
        "pages/02_Fornecedores.py",
        label="👥 Fornecedores"
    )

with c2:

    st.page_link(
        "pages/03_Compras.py",
        label="🛒 Compras"
    )

    st.page_link(
        "pages/04_Vendas.py",
        label="💰 Vendas"
    )

with c3:

    st.page_link(
        "pages/05_Industrias.py",
        label="🏭 Indústrias"
    )

    st.page_link(
        "pages/06_Dashboard.py",
        label="📊 Dashboard"
    )

st.page_link(
    "pages/11_Abrir_Caixa.py",
    label="💵 Abrir Caixa"
)

# =====================================
# RESUMO
# =====================================

st.divider()

st.subheader("📋 Resumo do Sistema")

st.info(
    """
    Bem-vindo ao Recicle Lar.

    Utilize o menu lateral para:

    • Cadastrar materiais

    • Cadastrar fornecedores

    • Cadastrar indústrias

    • Registrar compras

    • Registrar vendas

    • Controlar estoque

    • Controlar caixa

    • Acompanhar indicadores

    • Gerar relatórios

    • Consultar DRE
    """
)