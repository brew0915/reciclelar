import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import date
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

if "usuario" not in st.session_state:

    st.switch_page("pages/00_Login.py")
    st.stop()

render_menu()

filial_id = st.session_state.get(
    "filial_operacao"
)   


if filial_id is None:

    st.error(
        "Selecione uma filial no menu lateral."
    )

    st.stop()

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
    page_title="Fechamento de Caixa",
    page_icon="🔒",
    layout="wide"
)

st.title("🔒 Fechamento de Caixa")

# =====================================
# FILIAL
# =====================================


data_fechamento = st.date_input(
    "Data",
    value=date.today()
)

st.info(
    f"Filial selecionada: {filial_id}"
)

# =====================================
# BUSCAR VALORES
# =====================================

with engine.connect() as conn:

    saldo_inicial = conn.execute(
        text("""
            SELECT
                COALESCE(
                    SUM(saldo_inicial),
                    0
                )
            FROM caixa
            WHERE filial_id = :filial_id
            AND data_caixa::date = :data
        """),
        {
            "filial_id": filial_id,
            "data": data_fechamento
        }
    ).scalar()

    total_compras = conn.execute(
        text("""
            SELECT
                COALESCE(
                    SUM(valor_total),
                    0
                )
            FROM compras
            WHERE filial_id = :filial_id
            AND data_compra::date = :data
        """),
        {
            "filial_id": filial_id,
            "data": data_fechamento
        }
    ).scalar()

    total_vendas = conn.execute(
        text("""
            SELECT
                COALESCE(
                    SUM(valor_total),
                    0
                )
            FROM vendas
            WHERE filial_id = :filial_id
            AND data_venda::date = :data
        """),
        {
            "filial_id": filial_id,
            "data": data_fechamento
        }
    ).scalar()

saldo_final = (
    saldo_inicial
    - total_compras
    + total_vendas
)


if saldo_inicial <= 0:

    st.error(
        "Não existe abertura de caixa para esta data."
    )

    st.stop()
# =====================================
# KPIs
# =====================================

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        "💵 Abertura",
        f"R$ {saldo_inicial:,.2f}"
    )

with c2:
    st.metric(
        "🛒 Compras",
        f"R$ {total_compras:,.2f}"
    )

with c3:
    st.metric(
        "💰 Vendas",
        f"R$ {total_vendas:,.2f}"
    )

with c4:
    st.metric(
        "📈 Saldo Final",
        f"R$ {saldo_final:,.2f}"
    )

# =====================================
# OBSERVAÇÃO
# =====================================

observacao = st.text_area(
    "Observação"
)

# =====================================
# FECHAR CAIXA
# =====================================

if st.button(
    "🔒 Fechar Caixa",
    use_container_width=True
):

    with engine.begin() as conn:

        existe = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM fechamento_caixa
                WHERE filial_id = :filial_id
                AND data_fechamento = :data
            """),
            {
                "filial_id": filial_id,
                "data": data_fechamento
            }
        ).scalar()

        if existe > 0:

            st.error(
                "Já existe fechamento para esta data."
            )

            st.stop()


        conn.execute(
            text("""
                INSERT INTO fechamento_caixa
                (
                    filial_id,
                    usuario_id,
                    data_fechamento,
                    saldo_inicial,
                    total_compras,
                    total_vendas,
                    saldo_final,
                    observacao
                )
                VALUES
                (
                    :filial_id,
                    :usuario_id,
                    :data_fechamento,
                    :saldo_inicial,
                    :total_compras,
                    :total_vendas,
                    :saldo_final,
                    :observacao
                )
            """),
            {
                "filial_id": filial_id,
                "usuario_id":
                    st.session_state["usuario"]["id"],
                "data_fechamento":
                    data_fechamento,
                "saldo_inicial":
                    saldo_inicial,
                "total_compras":
                    total_compras,
                "total_vendas":
                    total_vendas,
                "saldo_final":
                    saldo_final,
                "observacao":
                    observacao
            }
        )


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
            :usuario_id,
            :acao,
            :tabela,
            :registro_id
        )
    """),
    {
        "usuario_id": st.session_state["usuario"]["id"],
        "acao": f"Fechou caixa da filial {filial_id} em {data_fechamento}",
        "tabela": "fechamento_caixa",
        "registro_id": 0
    }
)

    st.success(
        "Caixa fechado com sucesso!"
    )

    st.rerun()

# =====================================
# HISTÓRICO
# =====================================

st.divider()

st.subheader("📋 Histórico de Fechamentos")

with engine.connect() as conn:

    historico = pd.read_sql(
        """
                SELECT

            f.id,

            f.data_fechamento,

            fi.nome AS filial,

            f.saldo_inicial,

            f.total_compras,

            f.total_vendas,

            f.saldo_final,

            u.nome AS usuario

        FROM fechamento_caixa f

        INNER JOIN filiais fi
            ON f.filial_id = fi.id

        LEFT JOIN usuarios u
            ON f.usuario_id = u.id

        ORDER BY f.data_fechamento DESC
                """,
        conn
    )

if historico.empty:

    st.info(
        "Nenhum fechamento realizado."
    )

else:

    st.dataframe(
        historico,
        use_container_width=True,
        hide_index=True
    )