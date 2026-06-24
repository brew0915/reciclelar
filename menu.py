import streamlit as st
import pandas as pd
from sqlalchemy import text

from database import engine


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


def render_menu():

    if "usuario" not in st.session_state:
        return

    usuario = st.session_state["usuario"]
    perfil = usuario["perfil"]

    with st.sidebar:

        # ==========================
        # LOGO
        # ==========================

        st.image(
            "assets/logo.png",
            width=180
        )


# ==========================
# FILIAL
# ==========================

        if perfil == "ADMIN":

            with engine.connect() as conn:

                filiais = pd.read_sql(
                    """
                    SELECT
                        id,
                        nome
                    FROM filiais
                    ORDER BY nome
                    """,
                    conn
                )

                filial_id_salva = conn.execute(
                    text("""
                        SELECT filial_padrao_id
                        FROM usuarios
                        WHERE id = :id
                    """),
                    {
                        "id": usuario["id"]
                    }
                ).scalar()

            if not filiais.empty:

                indice_padrao = 0

                if filial_id_salva:

                    filtro = filiais[
                        filiais["id"] == filial_id_salva
                    ]

                    if not filtro.empty:

                        indice_padrao = int(
                            filtro.index[0]
                        )

                filial_nome = st.selectbox(
                    "🏢 Filial",
                    filiais["nome"].tolist(),
                    index=indice_padrao
                )

                filial_id = int(
                    filiais.loc[
                        filiais["nome"] == filial_nome,
                        "id"
                    ].iloc[0]
                )

                filial_anterior = st.session_state.get(
                    "filial_operacao"
                )

                st.session_state[
                    "filial_operacao"
                ] = filial_id

                st.session_state[
                    "filial_nome"
                ] = filial_nome

                if filial_anterior != filial_id:

                    with engine.begin() as conn:

                        conn.execute(
                            text("""
                                UPDATE usuarios
                                SET filial_padrao_id = :filial
                                WHERE id = :usuario
                            """),
                            {
                                "filial": filial_id,
                                "usuario": usuario["id"]
                            }
                        )

        else:

            st.session_state[
                "filial_operacao"
            ] = usuario.get(
                "filial_id"
            )

        st.markdown("---")

        # ==========================
        # HOME
        # ==========================

        if perfil == "ADMIN":

            st.page_link(
                "app.py",
                label="🏠 Início"
            )

        # ==========================
        # OPERAÇÃO
        # ==========================

        st.markdown(
            "### 🏢 Operação"
        )

        st.page_link(
            "pages/03_Compras.py",
            label="🛒 Compras"
        )

        if perfil == "ADMIN":

            st.page_link(
                "pages/04_Vendas.py",
                label="💰 Vendas"
            )

        st.page_link(
            "pages/09_Estoque.py",
            label="📦 Estoque"
        )

        st.page_link(
            "pages/11_Abrir_Caixa.py",
            label="💵 Caixa"
        )

        st.page_link(
            "pages/15_Fechamento_Caixa.py",
            label="🔒 Fechamento Caixa"
        )

        # ==========================
        # CADASTROS
        # ==========================

        if perfil == "ADMIN":

            st.markdown(
                "### ⚙️ Cadastros"
            )

            st.page_link(
                "pages/01_Materiais.py",
                label="📦 Materiais"
            )

            st.page_link(
                "pages/02_Fornecedores.py",
                label="👥 Fornecedores"
            )

            st.page_link(
                "pages/05_Industrias.py",
                label="🏭 Indústrias"
            )

            st.page_link(
                "pages/14_Filiais.py",
                label="🏢 Filiais"
            )

        # ==========================
        # GESTÃO
        # ==========================

        if perfil == "ADMIN":

            st.markdown(
                "### 📊 Gestão"
            )

            st.page_link(
                "pages/06_Dashboard.py",
                label="📊 Dashboard"
            )

            st.page_link(
                "pages/07_Relatorios.py",
                label="📑 Relatórios"
            )

            st.page_link(
                "pages/08_DRE.py",
                label="📈 DRE"
            )

        # ==========================
        # ADMINISTRAÇÃO
        # ==========================

        if perfil == "ADMIN":

            st.markdown(
                "### 🔒 Administração"
            )

            st.page_link(
                "pages/13_Usuarios.py",
                label="👤 Usuários"
            )

        # ==========================
        # RODAPÉ
        # ==========================

        st.markdown("---")

        if perfil == "ADMIN":

            st.caption(
                f"🏢 {st.session_state.get('filial_nome', '')}"
            )

        st.caption(
            f"👤 {usuario['nome']}"
        )

        st.caption(
            f"🔑 {usuario['perfil']}"
        )

        if st.button(
            "🚪 Sair",
            use_container_width=True
        ):

            st.session_state.clear()

            st.switch_page(
                "pages/00_login.py"
            )