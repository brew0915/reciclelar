import streamlit as st
from auth import autenticar
from database import engine
import streamlit as st
import pandas as pd
from sqlalchemy import text
from menu import render_menu


def carregar_css():
    with open("assets/style.css", encoding="utf-8") as f:
        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True
        )

carregar_css()

st.set_page_config(
    page_title="Login",
    page_icon="🔐",
    layout="centered"
)

st.markdown("""
<style>
[data-testid="stSidebar"] {
    display: none;
}

[data-testid="collapsedControl"] {
    display: none;
}
</style>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1,2,1])

with col2:

    st.image(
        "assets/logo.png",
        width=250
    )

    st.title("Login")

    email = st.text_input("E-mail")

    senha = st.text_input(
        "Senha",
        type="password"
    )

    if st.button(
        "Entrar",
        use_container_width=True
    ):

        usuario = autenticar(
            email,
            senha
        )

        if usuario:

            st.session_state["usuario"] = dict(usuario)

            # Admin escolhe depois no menu
            with engine.connect() as conn:

                filial_padrao = conn.execute(
                    text("""
                        SELECT id
                        FROM filiais
                        ORDER BY id
                        LIMIT 1
                        """)
                    ).scalar()

            st.session_state["filial_operacao"] = filial_padrao

            perfil = usuario["perfil"]

            if perfil == "ADMIN":

                st.session_state["filial_operacao"] = (
                    usuario.get("filial_padrao_id")
                )

                st.switch_page("app.py")

            elif perfil == "OPERADOR":

                st.session_state["filial_operacao"] = (
                    usuario["filial_id"]
                )

                st.switch_page(
                    "pages/03_Compras.py"
                )

            elif perfil == "CONSULTA":

                st.session_state["filial_operacao"] = (
                    usuario["filial_id"]
                )

                st.switch_page(
                    "pages/06_Dashboard.py"
                )
        else:

            st.error(
                "Usuário ou senha inválidos."
            )