import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import engine

from menu import render_menu


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


render_menu()



if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()


perfil = st.session_state["usuario"]["perfil"]

# ADMIN escolhe a filial
if perfil == "ADMIN":

    with engine.connect() as conn:

        filiais = pd.read_sql(
            """
            SELECT id, nome
            FROM filiais
            ORDER BY nome
            """,
            conn
        )

    filial_escolhida = st.sidebar.selectbox(
        "🏢 Filial",
        ["Todas"] + filiais["nome"].tolist(),
        key="filial_admin"
    )

    st.session_state["filial_ativa"] = filial_escolhida

# OPERADOR e CONSULTA ficam presos à própria filial
else:

    st.session_state["filial_ativa"] = (
        st.session_state["usuario"]["filial_id"]
    )

st.set_page_config(
    page_title="Industrias",
    page_icon="🏭 ",
    layout="wide"
)



st.title("🏭 Cadastro de Indústrias")

# ======================
# FORMULÁRIO
# ======================

with st.form("form_industria"):

    nome = st.text_input("Nome da Indústria")

    cnpj = st.text_input("CNPJ")

    contato = st.text_input("Contato")

    telefone = st.text_input("Telefone")

    email = st.text_input("E-mail")

    endereco = st.text_area("Endereço")

    salvar = st.form_submit_button("Salvar")

# ======================
# SALVAR
# ======================

if salvar:

    if nome.strip() == "":
        st.warning("Informe o nome da indústria.")
        st.stop()

    with engine.begin() as conn:

        existe = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM industrias
                WHERE UPPER(nome) = UPPER(:nome)
            """),
            {"nome": nome}
        ).scalar()

        if existe > 0:
            st.warning("Indústria já cadastrada.")
            st.stop()

        conn.execute(
            text("""
                INSERT INTO industrias
                (
                    nome,
                    cnpj,
                    contato,
                    telefone,
                    email,
                    endereco
                )
                VALUES
                (
                    :nome,
                    :cnpj,
                    :contato,
                    :telefone,
                    :email,
                    :endereco
                )
            """),
            {
                "nome": nome,
                "cnpj": cnpj,
                "contato": contato,
                "telefone": telefone,
                "email": email,
                "endereco": endereco
            }
        )

    st.success("Indústria cadastrada com sucesso!")
    st.rerun()

# ======================
# BUSCA
# ======================

st.divider()

busca = st.text_input(
    "🔎 Buscar indústria"
)

# ======================
# LISTAGEM
# ======================

with engine.connect() as conn:

    df = pd.read_sql(
        """
        SELECT
            id,
            nome,
            cnpj,
            contato,
            telefone
        FROM industrias
        ORDER BY nome
        """,
        conn
    )

if busca:

    df = df[
        df["nome"]
        .str.contains(
            busca,
            case=False,
            na=False
        )
    ]

st.subheader("Indústrias cadastradas")

if df.empty:

    st.info("Nenhuma indústria cadastrada.")

else:

    for _, industria in df.iterrows():

        col1, col2, col3, col4, col5, col6 = st.columns(
            [1, 4, 2, 2, 2, 1]
        )

        with col1:
            st.write(industria["id"])

        with col2:
            st.write(industria["nome"])

        with col3:
            st.write(industria["cnpj"])

        with col4:
            st.write(industria["contato"])

        with col5:
            st.write(industria["telefone"])

        with col6:

            if st.button(
                "🗑️",
                key=f"excluir_{industria['id']}"
            ):

                st.session_state["industria_excluir"] = {
                    "id": int(industria["id"]),
                    "nome": industria["nome"]
                }

        if (
            "industria_excluir" in st.session_state
            and
            st.session_state["industria_excluir"]["id"]
            == int(industria["id"])
        ):

            st.warning(
                f"Deseja realmente excluir "
                f"'{industria['nome']}'?"
            )

            c1, c2 = st.columns(2)

            with c1:

                if st.button(
                    "✅ Confirmar",
                    key=f"confirmar_{industria['id']}"
                ):

                    with engine.begin() as conn:

                        conn.execute(
                            text("""
                                DELETE FROM industrias
                                WHERE id = :id
                            """),
                            {
                                "id": int(industria["id"])
                            }
                        )

                    del st.session_state[
                        "industria_excluir"
                    ]

                    st.success(
                        "Indústria removida!"
                    )

                    st.rerun()

            with c2:

                if st.button(
                    "❌ Cancelar",
                    key=f"cancelar_{industria['id']}"
                ):

                    del st.session_state[
                        "industria_excluir"
                    ]

                    st.rerun()