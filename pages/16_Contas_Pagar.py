import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import engine
from menu import render_menu
from datetime import date, timedelta

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

if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()

render_menu()

filial_id = st.session_state.get("filial_operacao")

if filial_id is None:
    st.error("Selecione uma filial.")
    st.stop()

st.set_page_config(
    page_title="Contas a Pagar",
    page_icon="💳",
    layout="wide"
)


with engine.connect() as conn:

    filial_nome = conn.execute(
        text("""
            SELECT nome
            FROM filiais
            WHERE id=:id
        """),
        {
            "id": filial_id
        }
    ).scalar()

st.title(f"💳 Contas a Pagar - {filial_nome}")

st.caption(f"Filial: {filial_nome}")

col1,col2,col3,col4 = st.columns(4)

with col1:

    data_inicio = st.date_input(
        "Data Inicial",
        date.today()-timedelta(days=30)
    )

with col2:

    data_fim = st.date_input(
        "Data Final",
        date.today()
    )

with col3:

    status = st.selectbox(
        "Status",
        [
            "Todos",
            "ABERTO",
            "PAGO",
            "VENCIDO"
        ]
    )

with col4:

    fornecedor = st.text_input(
        "Fornecedor"
    )


# =====================================
# CONSULTA
# =====================================

# =====================================
# CONSULTA
# =====================================

sql = """
SELECT

    cp.id,

    COALESCE(
        f.nome,
        'Fornecedor Avulso'
    ) AS fornecedor,

    cf.descricao AS categoria,

    cp.descricao,

    cp.valor,

    cp.saldo,

    cp.vencimento,

    cp.data_pagamento,

    cp.status

FROM contas_pagar cp

LEFT JOIN fornecedores f
    ON f.id = cp.fornecedor_id

LEFT JOIN categorias_financeiras cf
    ON cf.id = cp.categoria_id

WHERE cp.filial_id = :filial
AND cp.vencimento
BETWEEN :inicio AND :fim
"""

parametros = {
    "filial": filial_id,
    "inicio": data_inicio,
    "fim": data_fim
}

if status != "Todos":

    sql += """
    AND cp.status = :status
    """

    parametros["status"] = status

if fornecedor:

    sql += """
    AND UPPER(
        COALESCE(f.nome,'')
    )
    LIKE UPPER(:fornecedor)
    """

    parametros["fornecedor"] = f"%{fornecedor}%"

sql += """
ORDER BY

    cp.status,

    cp.vencimento,

    cp.id
"""

with engine.connect() as conn:

    df = pd.read_sql(
        text(sql),
        conn,
        params=parametros
    )


total_aberto = df.loc[
    df["status"] == "ABERTO",
    "saldo"
].sum()

total_pago = df.loc[
    df["status"] == "PAGO",
    "valor"
].sum()

total_vencido = df.loc[
    df["status"] == "VENCIDO",
    "saldo"
].sum()

total_geral = df["valor"].sum()


st.divider()

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        "💰 Em Aberto",
        f"R$ {total_aberto:,.2f}"
    )

with c2:
    st.metric(
        "✅ Pago",
        f"R$ {total_pago:,.2f}"
    )

with c3:
    st.metric(
        "⚠️ Vencido",
        f"R$ {total_vencido:,.2f}"
    )

with c4:
    st.metric(
        "📊 Total",
        f"R$ {total_geral:,.2f}"
    )

st.divider()

if df.empty:

    st.info("Nenhuma conta encontrada.")

else:

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

