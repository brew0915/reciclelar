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
    page_title="Contas a Receber",
    page_icon="💰",
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

st.title(f"💰 Contas a Receber - {filial_nome}")


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
            "RECEBIDO",
            "VENCIDO"
        ]
    )

with col4:

    cliente = st.text_input(
        "Indústria"
    )



    sql = """
SELECT

    cr.id,

    i.nome AS industria,

    cf.descricao AS categoria,

    cr.descricao,

    cr.valor,

    cr.saldo,

    cr.vencimento,

    cr.data_recebimento,

    cr.status

FROM contas_receber cr

LEFT JOIN industrias i
    ON i.id = cr.industria_id

LEFT JOIN categorias_financeiras cf
    ON cf.id = cr.categoria_id

WHERE cr.filial_id = :filial

AND cr.vencimento
BETWEEN :inicio
AND :fim
"""

parametros = {
    "filial": filial_id,
    "inicio": data_inicio,
    "fim": data_fim
}


if status != "Todos":

    sql += """
    AND cr.status = :status
    """

    parametros["status"] = status


if cliente:

    sql += """
    AND UPPER(i.nome)
    LIKE UPPER(:cliente)
    """

    parametros["cliente"] = f"%{cliente}%"



sql += """
ORDER BY

CASE

WHEN cr.status='VENCIDO' THEN 1
WHEN cr.status='ABERTO' THEN 2
WHEN cr.status='RECEBIDO' THEN 3

END,

cr.vencimento
"""

with engine.connect() as conn:

    df = pd.read_sql(
        text(sql),
        conn,
        params=parametros
    )

    total_aberto = df.loc[
    df["status"]=="ABERTO",
    "saldo"
    ].sum()

    total_recebido = df.loc[
        df["status"]=="RECEBIDO",
        "valor"
    ].sum()

    total_vencido = df.loc[
        df["status"]=="VENCIDO",
        "saldo"
    ].sum()

    total_geral = df["valor"].sum()


    c1,c2,c3,c4 = st.columns(4)

with c1:

    st.metric(
        "💰 Em Aberto",
        f"R$ {total_aberto:,.2f}"
    )

with c2:

    st.metric(
        "✅ Recebido",
        f"R$ {total_recebido:,.2f}"
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

    st.info(
        "Nenhuma conta encontrada."
    )

else:

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

# =====================================
# RECEBER PAGAMENTO
# =====================================

st.divider()

st.subheader("💰 Receber Pagamento")

contas_abertas = df[
    df["status"].isin(["ABERTO", "VENCIDO", "PARCIAL"])
]

if contas_abertas.empty:

    st.success("Nenhuma conta pendente de recebimento.")

else:

    conta = st.selectbox(
        "Conta",
        contas_abertas["id"],
        format_func=lambda x: (
            f"Venda #{x} | "
            f"{contas_abertas.loc[contas_abertas['id']==x,'industria'].iloc[0]} | "
            f"Saldo R$ {contas_abertas.loc[contas_abertas['id']==x,'saldo'].iloc[0]:,.2f}"
        )
    )

    saldo = float(
        contas_abertas.loc[
            contas_abertas["id"] == conta,
            "saldo"
        ].iloc[0]
    )

    data_recebimento = st.date_input(
        "Data do Recebimento",
        value=date.today()
    )

    forma = st.selectbox(
        "Forma de Recebimento",
        [
            "Dinheiro",
            "PIX",
            "TED",
            "Cartão",
            "Boleto"
        ]
    )

    valor = st.number_input(
        "Valor Recebido",
        min_value=0.01,
        max_value=saldo,
        value=saldo,
        step=0.01
    )

    observacao = st.text_area(
        "Observação"
    )

    if st.button(
        "✅ Confirmar Recebimento",
        use_container_width=True
    ):

        with engine.begin() as conn:

            novo_saldo = saldo - valor

            status_final = (
                "RECEBIDO"
                if novo_saldo <= 0
                else "PARCIAL"
            )

            conn.execute(
                text("""
                    UPDATE contas_receber
                    SET
                        saldo = :saldo,
                        valor_pago = valor_pago + :valor,
                        data_recebimento = :data,
                        status = :status
                    WHERE id = :id
                """),
                {
                    "saldo": novo_saldo,
                    "valor": valor,
                    "data": data_recebimento,
                    "status": status_final,
                    "id": conta
                }
            )

            # Atualiza caixa
            conn.execute(
                text("""
                    UPDATE caixa
                    SET saldo_disponivel =
                        saldo_disponivel + :valor
                    WHERE filial_id = :filial
                    AND fechado_em IS NULL
                """),
                {
                    "valor": valor,
                    "filial": filial_id
                }
            )

            # Movimentação financeira
            conn.execute(
                text("""
                    INSERT INTO movimentacao_financeira
                    (
                        filial_id,
                        tipo,
                        origem,
                        descricao,
                        entrada,
                        data_movimento,
                        usuario_id,
                        observacao
                    )
                    VALUES
                    (
                        :filial,
                        'ENTRADA',
                        'RECEBIMENTO',
                        :descricao,
                        :valor,
                        CURRENT_TIMESTAMP,
                        :usuario,
                        :observacao
                    )
                """),
                {
                    "filial": filial_id,
                    "descricao": f"Recebimento Conta #{conta}",
                    "valor": valor,
                    "usuario": st.session_state["usuario"]["id"],
                    "observacao": observacao
                }
            )

            # Auditoria
            conn.execute(
                text("""
                    INSERT INTO auditoria
                    (
                        usuario_id,
                        acao,
                        tabela,
                        registro_id
                    )
                    VALUES
                    (
                        :usuario,
                        :acao,
                        'contas_receber',
                        :registro
                    )
                """),
                {
                    "usuario": st.session_state["usuario"]["id"],
                    "acao": f"Recebeu pagamento da conta {conta}",
                    "registro": conta
                }
            )

        st.success("Pagamento registrado com sucesso!")

        st.rerun()