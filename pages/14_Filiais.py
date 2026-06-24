import streamlit as st
import pandas as pd
from sqlalchemy import text

from database import engine
from menu import render_menu

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
# SEGURANÇA
# =====================================

if "usuario" not in st.session_state:

    st.switch_page("pages/00_Login.py")
    st.stop()

if st.session_state["usuario"]["perfil"] != "ADMIN":

    st.error(
        "Acesso permitido apenas para administradores."
    )
    st.stop()

# =====================================
# CONFIG
# =====================================

st.set_page_config(
    page_title="Filiais",
    page_icon="🏢",
    layout="wide"
)


# =====================================
# TÍTULO
# =====================================

st.title("🏢 Cadastro de Filiais")

# =====================================
# FORMULÁRIO
# =====================================

with st.form("form_filial"):

    col1, col2 = st.columns(2)

    with col1:

        nome = st.text_input(
            "Nome da Filial"
        )

    with col2:

        cidade = st.text_input(
            "Cidade"
        )

    ativo = st.checkbox(
        "Filial Ativa",
        value=True
    )

    salvar = st.form_submit_button(
        "💾 Salvar Filial",
        use_container_width=True
    )

# =====================================
# SALVAR
# =====================================

if salvar:

    if nome.strip() == "":

        st.warning(
            "Informe o nome da filial."
        )

        st.stop()

    with engine.begin() as conn:

        existe = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM filiais
                WHERE UPPER(nome)
                    = UPPER(:nome)
            """),
            {
                "nome": nome
            }
        ).scalar()

        if existe > 0:

            st.warning(
                "Filial já cadastrada."
            )

            st.stop()

        conn.execute(
            text("""
                INSERT INTO filiais
                (
                    nome,
                    cidade,
                    ativo
                )
                VALUES
                (
                    :nome,
                    :cidade,
                    :ativo
                )
            """),
            {
                "nome": nome,
                "cidade": cidade,
                "ativo": ativo
            }
        )

    st.success(
        "Filial cadastrada com sucesso!"
    )

    st.rerun()

# =====================================
# LISTAGEM
# =====================================

st.divider()

st.subheader("📋 Filiais Cadastradas")

with engine.connect() as conn:

    filiais = pd.read_sql(
        """
        SELECT
            id,
            nome,
            cidade,
            ativo
        FROM filiais
        ORDER BY nome
        """,
        conn
    )

if filiais.empty:

    st.info(
        "Nenhuma filial cadastrada."
    )

else:

    st.dataframe(
        filiais,
        use_container_width=True,
        hide_index=True
    )

# =====================================
# ALTERAR STATUS
# =====================================

st.divider()

st.subheader("🔄 Ativar / Desativar Filial")

if not filiais.empty:

    filial_nome = st.selectbox(
        "Filial",
        filiais["nome"].tolist()
    )

    if st.button(
        "Alterar Status",
        use_container_width=True
    ):

        filial_id = int(
            filiais.loc[
                filiais["nome"] == filial_nome,
                "id"
            ].iloc[0]
        )

        with engine.begin() as conn:

            conn.execute(
                text("""
                    UPDATE filiais
                    SET ativo = NOT ativo
                    WHERE id = :id
                """),
                {
                    "id": filial_id
                }
            )

        st.success(
            "Status atualizado."
        )

        st.rerun()

# =====================================
# EXCLUIR
# =====================================

st.divider()

st.subheader("🗑️ Excluir Filial")

if not filiais.empty:

    filial_excluir = st.selectbox(
        "Filial para excluir",
        filiais["nome"].tolist(),
        key="excluir_filial"
    )

    if st.button(
        "Excluir Filial",
        use_container_width=True
    ):

        filial_id = int(
            filiais.loc[
                filiais["nome"] == filial_excluir,
                "id"
            ].iloc[0]
        )

        with engine.begin() as conn:

            usuarios_vinculados = conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM usuarios
                    WHERE filial_id = :id
                """),
                {
                    "id": filial_id
                }
            ).scalar()

            if usuarios_vinculados > 0:

                st.error(
                    "Existem usuários vinculados a esta filial."
                )

                st.stop()

            conn.execute(
                text("""
                    DELETE FROM filiais
                    WHERE id = :id
                """),
                {
                    "id": filial_id
                }
            )

        st.success(
            "Filial excluída."
        )

        st.rerun()