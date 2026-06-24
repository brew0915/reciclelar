import streamlit as st

def exigir_login():

    if "usuario" not in st.session_state:

        st.switch_page("pages/00_Login.py")
        st.stop()


def exigir_perfil(perfis):

    exigir_login()

    perfil_usuario = st.session_state["usuario"]["perfil"]

    if perfil_usuario not in perfis:

        st.error("🚫 Você não possui permissão para acessar esta página.")
        st.stop()