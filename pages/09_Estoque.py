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

# =====================================
# SEGURANÇA
# =====================================

if "usuario" not in st.session_state:

    st.switch_page("pages/00_Login.py")
    st.stop()

# =====================================
# MENU
# =====================================

render_menu()

# =====================================
# CSS
# =====================================



# =====================================
# FILIAL
# =====================================

perfil = st.session_state["usuario"]["perfil"]

filial_id = st.session_state.get(
    "filial_operacao"
)

if filial_id is None:

    st.error(
        "Selecione uma filial no menu lateral."
    )

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


# =====================================
# TÍTULO
# =====================================

st.title(
    f"📦 Controle de Estoque - {filial_nome}"
)

# =====================================
# ESTOQUE
# =====================================

with engine.connect() as conn:

    estoque = pd.read_sql(
        """
        SELECT

            m.id,

            m.descricao,

            COALESCE(
                SUM(
                    CASE
                        WHEN e.tipo = 'ENTRADA'
                        THEN e.quantidade
                        ELSE -e.quantidade
                    END
                ),
                0
            ) AS estoque

        FROM materiais m

        LEFT JOIN estoque_movimentacao e
            ON m.id = e.material_id
            AND e.filial_id = %(filial_id)s

        GROUP BY
            m.id,
            m.descricao

        ORDER BY
            estoque DESC
        """,
        conn,
        params={
            "filial_id": filial_id
        }
    )

# =====================================
# KPIs
# =====================================

total_materiais = len(estoque)

peso_total = (
    estoque["estoque"].sum()
    if not estoque.empty
    else 0
)

c1, c2 = st.columns(2)

with c1:

    st.metric(
        "📦 Materiais",
        total_materiais
    )

with c2:

    st.metric(
        "⚖️ Peso Total",
        f"{peso_total:,.2f} KG"
    )

# =====================================
# FILTRO
# =====================================

busca = st.text_input(
    "🔎 Buscar Material"
)

if busca:

    estoque = estoque[
        estoque["descricao"]
        .str.contains(
            busca,
            case=False,
            na=False
        )
    ]

# =====================================
# ESTOQUE
# =====================================

st.subheader("📦 Estoque Atual")

if estoque.empty:

    st.info(
        "Nenhum material encontrado."
    )

else:

    st.dataframe(
        estoque,
        use_container_width=True,
        hide_index=True
    )

# =====================================
# ESTOQUE BAIXO
# =====================================

st.divider()

st.subheader("⚠️ Estoque Baixo")

with engine.connect() as conn:

    estoque_baixo = pd.read_sql(
        """
        SELECT

            m.descricao,

            em.quantidade_minima,

            COALESCE(
                SUM(
                    CASE
                        WHEN e.tipo = 'ENTRADA'
                        THEN e.quantidade
                        ELSE -e.quantidade
                    END
                ),
                0
            ) AS estoque_atual

        FROM estoque_minimo em

        INNER JOIN materiais m
            ON em.material_id = m.id

        LEFT JOIN estoque_movimentacao e
            ON m.id = e.material_id
            AND e.filial_id = %(filial_id)s

        GROUP BY
            m.descricao,
            em.quantidade_minima

        HAVING
            COALESCE(
                SUM(
                    CASE
                        WHEN e.tipo = 'ENTRADA'
                        THEN e.quantidade
                        ELSE -e.quantidade
                    END
                ),
                0
            ) <= em.quantidade_minima
        """,
        conn,
        params={
            "filial_id": filial_id
        }
    )

if estoque_baixo.empty:

    st.success(
        "Nenhum material abaixo do mínimo."
    )

else:

    st.dataframe(
        estoque_baixo,
        use_container_width=True,
        hide_index=True
    )

# =====================================
# MOVIMENTAÇÕES
# =====================================

st.divider()

st.subheader("📋 Últimas Movimentações")

with engine.connect() as conn:

    movimentacoes = pd.read_sql(
        """
        SELECT

            e.id,

            e.data_movimentacao,

            m.descricao,

            e.tipo,

            e.quantidade,

            e.origem,

            e.referencia_id

        FROM estoque_movimentacao e

        INNER JOIN materiais m
            ON e.material_id = m.id

        WHERE e.filial_id = %(filial_id)s

        ORDER BY
            e.id DESC

        LIMIT 100
        """,
        conn,
        params={
            "filial_id": filial_id
        }
    )

if movimentacoes.empty:

    st.info(
        "Nenhuma movimentação encontrada."
    )

else:

    st.dataframe(
        movimentacoes,
        use_container_width=True,
        hide_index=True
    )

# =====================================
# RANKING
# =====================================

st.divider()

st.subheader("🏆 Ranking de Estoque")

if not estoque.empty:

    ranking = estoque[
        [
            "descricao",
            "estoque"
        ]
    ]

    st.bar_chart(
        ranking.set_index(
            "descricao"
        )
    )