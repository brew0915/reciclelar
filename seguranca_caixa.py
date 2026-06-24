from sqlalchemy import text
from database import engine
import streamlit as st
from datetime import date


def validar_caixa_aberto(filial_id):

    hoje = date.today()

    with engine.connect() as conn:

        fechado = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM fechamento_caixa
                WHERE filial_id = :filial_id
                AND data_fechamento = :data
            """),
            {
                "filial_id": filial_id,
                "data": hoje
            }
        ).scalar()

    if fechado > 0:

        st.error(
            "O caixa desta filial já foi fechado. Não é possível realizar novas movimentações."
        )

        st.stop()