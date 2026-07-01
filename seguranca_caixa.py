import streamlit as st
from sqlalchemy import text
from database import engine
from datetime import date


def validar_caixa_aberto(filial_id):

    with engine.connect() as conn:

        caixa = conn.execute(
            text("""
                SELECT id
                FROM caixa
                WHERE filial_id = :filial
                  AND data_caixa = CURRENT_DATE
                  AND fechado_em IS NULL
                LIMIT 1
            """),
            {
                "filial": filial_id
            }
        ).scalar()

    if caixa is None:
        st.error("O caixa da filial não está aberto. Faça a abertura de caixa antes de continuar.")
        st.stop()