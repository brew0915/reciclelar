import pandas as pd
from sqlalchemy import text
import streamlit as st

from database import engine


def carregar_css():
    with open("assets/style.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


carregar_css()


def render_menu():
    if "usuario" not in st.session_state:
        return

    usuario = st.session_state["usuario"]
    perfil = usuario["perfil"]

    with st.sidebar:
        # =====================================
        # 1. LOGO E IDENTIDADE
        # =====================================
        st.image("assets/logo.png", use_container_width=True)

        # =====================================
        # 2. SELETOR DE FILIAL OPERACIONAL
        # =====================================
        if perfil == "ADMIN":
            with engine.connect() as conn:
                filiais = pd.read_sql(
                    "SELECT id, nome FROM filiais ORDER BY nome", conn
                )
                filial_id_salva = conn.execute(
                    text(
                        "SELECT filial_padrao_id FROM usuarios WHERE id = :id"
                    ),
                    {"id": usuario["id"]},
                ).scalar()

            if not filiais.empty:
                indice_padrao = 0
                if filial_id_salva:
                    filtro = filiais[filiais["id"] == filial_id_salva]
                    if not filtro.empty:
                        indice_padrao = int(filtro.index[0])

                filial_nome = st.selectbox(
                    "🏢 Empresa / Filial Ativa",
                    filiais["nome"].tolist(),
                    index=indice_padrao,
                )
                filial_id = int(
                    filiais.loc[filiais["nome"] == filial_nome, "id"].iloc[0]
                )

                filial_anterior = st.session_state.get("filial_operacao")
                st.session_state["filial_operacao"] = filial_id
                st.session_state["filial_nome"] = filial_nome

                # Atualiza a filial padrão no banco se houver troca manual
                if filial_anterior != filial_id:
                    with engine.begin() as conn:
                        conn.execute(
                            text(
                                """
                                UPDATE usuarios 
                                SET filial_padrao_id = :filial 
                                WHERE id = :usuario
                            """
                            ),
                            {"filial": filial_id, "usuario": usuario["id"]},
                        )
        else:
            # Operador fica travado na sua própria filial
            st.session_state["filial_operacao"] = usuario.get("filial_id")

        st.markdown("---")

        # =====================================
        # 3. LINKS DE NAVEGAÇÃO INTERNA
        # =====================================
        if perfil == "ADMIN":
            st.page_link("app.py", label="🏠 Painel Inicial (Início)")

        # --- GRUPO: OPERAÇÃO ---
        with st.expander("🏢 Módulos de Operação", expanded=True):
            st.page_link("pages/03_Compras.py", label="🛒 Compras / Suprimentos")
            if perfil == "ADMIN":
                st.page_link("pages/04_Vendas.py", label="💰 Vendas Comerciais")
            st.page_link("pages/09_Estoque.py", label="📦 Controle de Estoque")
            st.page_link("pages/11_Abrir_Caixa.py", label="💵 Frente de Caixa")
            st.page_link(
                "pages/15_Fechamento_Caixa.py", label="🔒 Fechamento de Caixa"
            )

        # --- GRUPO: CADASTROS E PARCEIROS ---
        if perfil == "ADMIN":
            with st.expander("⚙️ Cadastros Estruturais", expanded=False):
                st.page_link("pages/01_Materiais.py", label="📦 Materiais / Itens")
                st.page_link(
                    "pages/02_Fornecedores.py", label="👥 Fornecedores"
                )
                st.page_link("pages/05_Industrias.py", label="🏭 Indústrias")
                st.page_link("pages/14_Filiais.py", label="🏢 Filiais da Rede")
                st.page_link("pages/21_Tabela_Precos.py", label="💲 Tabela de Preços")
                st.page_link("pages/10_Estoque_Minimo.py", label="⚠️ Estoque Mínimo")

        # --- GRUPO: FINANCEIRO ---
        if perfil == "ADMIN":
            with st.expander("💳 Controladoria Financeira", expanded=False):
                st.page_link(
                    "pages/16_Contas_Pagar.py", label="📉 Contas a Pagar"
                )
                st.page_link(
                    "pages/17_Contas_Receber.py", label="📈 Contas a Receber"
                )
                st.page_link(
                    "pages/18_Fluxo_Caixa.py", label="💵 Fluxo de Caixa"
                )
                st.page_link("pages/19_Despesas.py", label="🧾 Lançar Despesas")

        # --- GRUPO: GESTÃO E DECISÃO ---
        if perfil == "ADMIN":
            with st.expander("📊 Business Intelligence", expanded=False):
                st.page_link("pages/06_Dashboard.py", label="📊 Dashboards")
                st.page_link("pages/07_Relatorios.py", label="📑 Relatórios Gerenciais")
                st.page_link("pages/08_DRE.py", label="📈 Demonstrativo (DRE)")

        # --- GRUPO: SISTEMA ---
        if perfil == "ADMIN":
            with st.expander("🔒 Segurança corporativa", expanded=False):
                st.page_link("pages/13_Usuarios.py", label="👤 Controle de Usuários")

        # =====================================
        # 4. METADADOS DO OPERADOR & LOGOUT
        # =====================================
        st.markdown("---")

        # Caixa de contexto do usuário logado estilo ERP de mercado
        with st.container():
            if perfil == "ADMIN":
                st.caption(
                    f"🏢 Unidade: **{st.session_state.get('filial_nome', '')}**"
                )
            st.caption(f"👤 Operador: **{usuario['nome']}**")
            st.caption(f"🔑 Credencial: `{usuario['perfil']}`")

        if st.button("🚪 Encerrar Sessão", use_container_width=True):
            st.session_state.clear()
            st.switch_page("pages/00_Login.py")
