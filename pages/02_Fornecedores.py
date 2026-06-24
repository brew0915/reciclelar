import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import engine
from menu import render_menu

render_menu()

def carregar_css():
    with open("assets/style.css") as f:
        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True
        )

carregar_css()


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
    page_title="Fornecedores",
    page_icon="👥",
    layout="wide"
)



st.title("👥 Cadastro de Fornecedores")

# ======================
# FORMULÁRIO
# ======================

with st.form("form_fornecedor"):

    nome = st.text_input("Nome")

    tipo = st.selectbox(
        "Tipo",
        [
            "Pessoa",
            "Condomínio",
            "Empresa",
            "Cooperativa"
        ]
    )

    documento = st.text_input("CPF/CNPJ")

    telefone = st.text_input("Telefone")

    email = st.text_input("E-mail")

    endereco = st.text_area("Endereço")

    observacoes = st.text_area("Observações")

    salvar = st.form_submit_button("Salvar")

if salvar:

    if nome.strip() == "":
        st.warning("Informe o nome do fornecedor.")

    else:

        with engine.begin() as conn:

            existe = conn.execute(
                text("""
                    SELECT COUNT(*)
                    FROM fornecedores
                    WHERE UPPER(nome) = UPPER(:nome)
                """),
                {"nome": nome}
            ).scalar()

            if existe > 0:
                st.warning("Fornecedor já cadastrado.")
                st.stop()

            conn.execute(
                text("""
                    INSERT INTO fornecedores
                    (
                        nome,
                        tipo,
                        documento,
                        telefone,
                        email,
                        endereco,
                        observacoes
                    )
                    VALUES
                    (
                        :nome,
                        :tipo,
                        :documento,
                        :telefone,
                        :email,
                        :endereco,
                        :observacoes
                    )
                """),
                {
                    "nome": nome,
                    "tipo": tipo,
                    "documento": documento,
                    "telefone": telefone,
                    "email": email,
                    "endereco": endereco,
                    "observacoes": observacoes
                }
            )

        st.success("Fornecedor cadastrado com sucesso!")
        st.rerun()

# ======================
# LISTAGEM
# ======================

st.divider()

st.subheader("Fornecedores cadastrados")

with engine.connect() as conn:

    df = pd.read_sql(
        """
        SELECT
            id,
            nome,
            tipo,
            telefone
        FROM fornecedores
        ORDER BY nome
        """,
        conn
    )

if df.empty:

    st.info("Nenhum fornecedor cadastrado.")

else:

    for _, fornecedor in df.iterrows():

        col1, col2, col3, col4, col5 = st.columns([1,4,2,2,1])

        with col1:
            st.write(fornecedor["id"])

        with col2:
            st.write(fornecedor["nome"])

        with col3:
            st.write(fornecedor["tipo"])

        with col4:
            st.write(fornecedor["telefone"])

        with col5:

            if st.button(
                "🗑️",
                key=f"excluir_{fornecedor['id']}"
            ):

                st.session_state["fornecedor_excluir"] = {
                    "id": int(fornecedor["id"]),
                    "nome": fornecedor["nome"]
                }

        if (
            "fornecedor_excluir" in st.session_state
            and st.session_state["fornecedor_excluir"]["id"] == int(fornecedor["id"])
        ):

            st.warning(
                f"Deseja excluir '{fornecedor['nome']}'?"
            )

            c1, c2 = st.columns(2)

            with c1:

                if st.button(
                    "✅ Confirmar",
                    key=f"confirmar_{fornecedor['id']}"
                ):

                    with engine.begin() as conn:

                        conn.execute(
                            text("""
                                DELETE FROM fornecedores
                                WHERE id = :id
                            """),
                            {
                                "id": int(fornecedor["id"])
                            }
                        )

                    del st.session_state["fornecedor_excluir"]

                    st.success("Fornecedor removido!")
                    st.rerun()

            with c2:

                if st.button(
                    "❌ Cancelar",
                    key=f"cancelar_{fornecedor['id']}"
                ):

                    del st.session_state["fornecedor_excluir"]
                    st.rerun()