
import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import date, timedelta
from menu import render_menu


from database import engine

if "usuario" not in st.session_state:

    st.switch_page("pages/00_Login.py")
    st.stop()

render_menu()


def carregar_css():
    with open("assets/style.css") as f:
        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True
        )

carregar_css()

perfil = st.session_state["usuario"]["perfil"]

# ADMIN escolhe a filial
filial_id = st.session_state.get(
    "filial_operacao"
)


if filial_id is None:

    st.error(
        "Selecione uma filial no menu lateral."
    )

    st.stop()

if st.session_state["usuario"]["perfil"] != "ADMIN":

    st.error("Acesso negado.")

    st.stop()





with engine.connect() as conn:

    filial_nome = conn.execute(
        text("""
            SELECT nome
            FROM filiais
            WHERE id = :id
        """),
        {
            "id": filial_id
        }
    ).scalar()

if filial_nome is None:

    st.error(
        "Filial inválida."
    )

    st.stop()
st.title(
    f"📦 Demonstrativo de Resultados - {filial_nome}"
)

st.info(
    f"Filial selecionada: {filial_id}"
)

# =====================================
# FILTROS
# =====================================

hoje = date.today()

col1, col2 = st.columns(2)

with col1:

    data_inicio = st.date_input(
        "Data Inicial",
        hoje - timedelta(days=30)
    )

with col2:

    data_fim = st.date_input(
        "Data Final",
        hoje
    )

# =====================================
# RECEITA
# =====================================

with engine.connect() as conn:

    receita_bruta = conn.execute(
        text("""
            SELECT
                COALESCE(
                    SUM(valor_total),
                    0
                )
            FROM vendas
            WHERE filial_id = :filial_id
            AND data_venda::date
            BETWEEN :inicio
            AND :fim
        """),
        {
            "inicio": data_inicio,
            "fim": data_fim,
            "filial_id": filial_id
        }
    ).scalar()

# =====================================
# CUSTO
# =====================================

with engine.connect() as conn:

    custo_aquisicao = conn.execute(
        text("""
            SELECT
                COALESCE(
                    SUM(valor_total),
                    0
                )
            FROM compras
            WHERE filial_id = :filial_id
            AND data_compra::date
            BETWEEN :inicio
            AND :fim
        """),
        {
            "inicio": data_inicio,
            "fim": data_fim,
            "filial_id": filial_id

        }
    ).scalar()

# =====================================
# RESULTADOS
# =====================================

lucro_bruto = receita_bruta - custo_aquisicao

margem = 0

if receita_bruta > 0:

    margem = (
        lucro_bruto /
        receita_bruta
    ) * 100

# =====================================
# KPIs
# =====================================

c1, c2, c3, c4 = st.columns(4)

with c1:

    st.metric(
        "💰 Receita Bruta",
        f"R$ {receita_bruta:,.2f}"
    )

with c2:

    st.metric(
        "🛒 Custo Aquisição",
        f"R$ {custo_aquisicao:,.2f}"
    )

with c3:

    st.metric(
        "📈 Lucro Bruto",
        f"R$ {lucro_bruto:,.2f}"
    )

with c4:

    st.metric(
        "🎯 Margem",
        f"{margem:.2f}%"
    )

# =====================================
# DRE
# =====================================

st.divider()

st.subheader("Demonstrativo")

dre = pd.DataFrame(
    {
        "Descrição": [
            "Receita Bruta",
            "(-) Custo Aquisição",
            "(=) Lucro Bruto"
        ],
        "Valor": [
            receita_bruta,
            custo_aquisicao,
            lucro_bruto
        ]
    }
)

st.dataframe(
    dre,
    use_container_width=True,
    hide_index=True
)

# =====================================
# LUCRO POR MATERIAL
# =====================================

st.divider()

st.subheader("🏆 Lucro por Material")

with engine.connect() as conn:

    receita_material = pd.read_sql(
        """
        SELECT

            m.id,

            m.descricao,

            COALESCE(
                SUM(v.valor_total),
                0
            ) AS receita

        FROM materiais m

        LEFT JOIN vendas v
            ON m.id = v.material_id
            AND v.filial_id = %(filial_id)s

        WHERE
            v.data_venda::date
            BETWEEN %(inicio)s
            AND %(fim)s

        GROUP BY
            m.id,
            m.descricao
        """,
        conn,
        params={
            "inicio": data_inicio,
            "fim": data_fim,
            "filial_id": filial_id
        }
    )

    custo_material = pd.read_sql(
        """
        SELECT

            m.id,

            COALESCE(
                SUM(ic.valor_total),
                0
            ) AS custo

        FROM materiais m

        LEFT JOIN itens_compra ic
            ON m.id = ic.material_id
        LEFT JOIN compras c
            ON ic.compra_id = c.id

        WHERE
            c.filial_id = %(filial_id)s
            AND c.data_compra::date
            BETWEEN %(inicio)s
            AND %(fim)s

        GROUP BY
            m.id
        """,
        conn,
        params={
            "inicio": data_inicio,
            "fim": data_fim,
            "filial_id": filial_id
        }
    )

if not receita_material.empty:

    df = receita_material.merge(
        custo_material,
        on="id",
        how="left"
    )

    df["custo"] = df["custo"].fillna(0)

    df["lucro"] = (
        df["receita"] -
        df["custo"]
    )

    df = df[
        [
            "descricao",
            "receita",
            "custo",
            "lucro"
        ]
    ]

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

# =====================================
# EVOLUÇÃO MENSAL
# =====================================

st.divider()

st.subheader("📊 Evolução Mensal")

with engine.connect() as conn:

        vendas_mes = pd.read_sql(
            """
            SELECT

                DATE_TRUNC(
                    'month',
                    data_venda
                ) AS mes,

                SUM(valor_total) AS receita

            FROM vendas

            WHERE filial_id = %(filial_id)s

            GROUP BY mes

            ORDER BY mes
            """,
            conn,
            params={
                "filial_id": filial_id
            }
        )

if not vendas_mes.empty:

    vendas_mes["mes"] = pd.to_datetime(
        vendas_mes["mes"]
    )

    st.line_chart(
        vendas_mes.set_index(
            "mes"
        )
    )

# =====================================
# RESUMO EXECUTIVO
# =====================================

st.divider()

st.subheader("📋 Resumo Executivo")

if lucro_bruto > 0:

    st.success(
        f"""
        Lucro bruto positivo de
        R$ {lucro_bruto:,.2f}
        com margem de
        {margem:.2f}%.
        """
    )

elif lucro_bruto < 0:

    st.error(
        f"""
        Prejuízo de
        R$ {abs(lucro_bruto):,.2f}.
        """
    )

else:

    st.warning(
        "Sem movimentação no período."
    )

