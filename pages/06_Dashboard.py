import streamlit as st
import pandas as pd
from sqlalchemy import text
from datetime import date, timedelta
from database import engine
from seguranca import exigir_perfil
from menu import render_menu


import streamlit as st

st.set_page_config(
    page_title="Dashboard",
    page_icon="📊",
    layout="wide"
)

def carregar_css():
    with open("assets/style.css") as f:
        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True
        )

carregar_css()


render_menu()

if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()


filial_id = st.session_state.get("filial_operacao")

if filial_id is None:

    st.error("Selecione uma filial.")
    st.stop()

filial_id = int(filial_id)

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


with engine.connect() as conn:

    status_caixa = conn.execute(
        text("""
            SELECT COUNT(*)
            FROM fechamento_caixa
            WHERE filial_id = :filial_id
            AND data_fechamento = CURRENT_DATE
        """),
        {
            "filial_id": filial_id
        }
    ).scalar()

exigir_perfil(["ADMIN"])


st.info(
    f"🏢 Filial: {filial_nome}"
)


if status_caixa  > 0:

    st.error(
        f"🔒 Caixa Fechado - {filial_nome}"
    )

elif status_caixa  > 0:

    st.success(
        f"🟢 Caixa Aberto - {filial_nome}"
    )

else:

    st.warning(
        f"🟡 Caixa Não Aberto - {filial_nome}"
    )

st.title(
    f"📊 Dashboard Recicle Lar - {filial_nome}"
)

# =====================================
# FILTROS
# =====================================

st.sidebar.header("Filtros")

periodo = st.sidebar.selectbox(
    "Período",
    [
        "Hoje",
        "7 dias",
        "30 dias",
        "Mês Atual",
        "Ano Atual",
        "Personalizado"
    ]
)

hoje = date.today()

if periodo == "Hoje":

    data_inicio = hoje
    data_fim = hoje

elif periodo == "7 dias":

    data_inicio = hoje - timedelta(days=7)
    data_fim = hoje

elif periodo == "30 dias":

    data_inicio = hoje - timedelta(days=30)
    data_fim = hoje

elif periodo == "Mês Atual":

    data_inicio = hoje.replace(day=1)
    data_fim = hoje

elif periodo == "Ano Atual":

    data_inicio = date(hoje.year, 1, 1)
    data_fim = hoje

else:

    data_inicio = st.sidebar.date_input(
        "Data Inicial",
        hoje - timedelta(days=30)
    )

    data_fim = st.sidebar.date_input(
        "Data Final",
        hoje
    )

# =====================================
# KPIs
# =====================================
# =====================================
# KPIs
# =====================================

with engine.connect() as conn:

    # CAIXA

    saldo_inicial = conn.execute(
        text("""
            SELECT COALESCE(
                SUM(saldo_inicial),
                0
            )
            FROM caixa
            WHERE filial_id = :filial_id
            AND data_caixa = CURRENT_DATE
        """),
        {
    "filial_id": filial_id
        }
    ).scalar()

    movimentacao = conn.execute(
        text("""
            SELECT COALESCE(
                SUM(
                    CASE
                        WHEN tipo = 'ENTRADA'
                        THEN valor
                        ELSE -valor
                    END
                ),
                0
            )
            FROM financeiro_movimentacao
            WHERE filial_id = :filial_id
            AND DATE(data_movimentacao) = CURRENT_DATE
        """),
        {
            "filial_id": filial_id
        }
    ).scalar()

    saldo_caixa = saldo_inicial + movimentacao

    # COMPRAS

    total_comprado = conn.execute(
        text("""
            SELECT COALESCE(
                SUM(valor_total),
                0
            )
            FROM compras
            WHERE filial_id = :filial_id
            AND data_compra::date
            BETWEEN :inicio AND :fim
        """),
        {
            "inicio": data_inicio,
            "fim": data_fim,
            "filial_id": filial_id
        }
    ).scalar()

    # VENDAS

    total_vendido = conn.execute(
        text("""
            SELECT COALESCE(
                SUM(valor_total),
                0
            )
            FROM vendas
            WHERE filial_id = :filial_id 
            AND data_venda::date
            BETWEEN :inicio AND :fim
        """),
        {
            "inicio": data_inicio,
            "fim": data_fim,
             "filial_id": filial_id
        }
    ).scalar()

lucro = total_vendido - total_comprado

# =====================================
# KPIs PRINCIPAIS
# =====================================

col1, col2, col3, col4 = st.columns(4)

with col1:

    st.metric(
        "🛒 Compras",
        f"R$ {total_comprado:,.2f}"
    )

with col2:

    st.metric(
        "💰 Vendas",
        f"R$ {total_vendido:,.2f}"
    )

with col3:

    st.metric(
        "📈 Lucro Bruto",
        f"R$ {lucro:,.2f}"
    )

with col4:

    st.metric(
        "💵 Caixa Atual",
        f"R$ {saldo_caixa:,.2f}"
    )

# =====================================
# CONTROLE DE CAIXA
# =====================================

st.divider()

st.subheader("💵 Controle de Caixa")

c1, c2, c3 = st.columns(3)

with c1:

    st.metric(
        "Saldo Inicial",
        f"R$ {saldo_inicial:,.2f}"
    )

with c2:

    st.metric(
        "Movimentação",
        f"R$ {movimentacao:,.2f}"
    )

with c3:

    st.metric(
        "Saldo Atual",
        f"R$ {saldo_caixa:,.2f}"
    )


###____________________________________________________________________________________

# =====================================
# ESTOQUE
# =====================================

st.divider()

st.subheader("📦 Estoque Atual")

with engine.connect() as conn:

    estoque = pd.read_sql(
        """
        SELECT

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

        GROUP BY m.descricao

        ORDER BY estoque DESC
        """,
        conn,
          params={
        "filial_id": filial_id
        }
    )

if not estoque.empty:

    st.dataframe(
        estoque,
        use_container_width=True,
        hide_index=True
    )

# =====================================
# EVOLUÇÃO COMPRAS
# =====================================

st.divider()

st.subheader("📈 Evolução de Compras")

with engine.connect() as conn:

    compras_mes = pd.read_sql(
        """
        SELECT
            DATE_TRUNC('month', data_compra) AS mes,
            SUM(valor_total) AS total
        FROM compras
        WHERE filial_id = %(filial_id)s
        GROUP BY mes
        ORDER BY mes
        """,
        conn,
        params={
            "filial_id": filial_id
        }
    )

if not compras_mes.empty:

    compras_mes["mes"] = pd.to_datetime(
        compras_mes["mes"]
    )

    st.line_chart(
        compras_mes.set_index("mes")
    )

# =====================================
# EVOLUÇÃO VENDAS
# =====================================

st.divider()

st.subheader("💰 Evolução de Vendas")

with engine.connect() as conn:
    vendas_mes = pd.read_sql(
        """
        SELECT
            DATE_TRUNC('month', data_venda) AS mes,
            SUM(valor_total) AS total
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
        vendas_mes.set_index("mes")
    )

# =====================================
# TOP MATERIAIS
# =====================================

st.divider()

st.subheader("🏆 Materiais Mais Comprados")

with engine.connect() as conn:

        top_materiais = pd.read_sql(
            """
            SELECT

                m.descricao,

                SUM(ic.quantidade) AS quantidade

            FROM itens_compra ic

            INNER JOIN compras c
                ON ic.compra_id = c.id

            INNER JOIN materiais m
                ON ic.material_id = m.id

            WHERE c.filial_id = %(filial_id)s

            GROUP BY m.descricao

            ORDER BY quantidade DESC

            LIMIT 10
            """,
            conn,
            params={
                "filial_id": filial_id
            }
        )

if not top_materiais.empty:

    st.bar_chart(
        top_materiais.set_index(
            "descricao"
        )
    )

# =====================================
# TOP FORNECEDORES
# =====================================

st.divider()

st.subheader("🚚 Top Fornecedores")

with engine.connect() as conn:

    fornecedores = pd.read_sql(
        """
        SELECT
    COALESCE(
        f.nome,
        c.fornecedor_avulso
                ) AS fornecedor,

                SUM(c.valor_total) AS total

            FROM compras c

            LEFT JOIN fornecedores f
                ON c.fornecedor_id = f.id

            WHERE c.filial_id = %(filial_id)s

            GROUP BY fornecedor

            ORDER BY total DESC

            LIMIT 10
        """,
        conn,
    params={
        "filial_id": filial_id
    }
    )

if not fornecedores.empty:

    st.dataframe(
        fornecedores,
        use_container_width=True,
        hide_index=True
    )

# =====================================
# TOP INDÚSTRIAS
# =====================================

st.divider()

st.subheader("🏭 Top Indústrias")

with engine.connect() as conn:

    industrias = pd.read_sql(
    """
    SELECT
        i.nome,
        SUM(v.valor_total) AS total

    FROM vendas v

    INNER JOIN industrias i
        ON v.industria_id = i.id

    WHERE v.filial_id = %(filial_id)s

    GROUP BY i.nome

    ORDER BY total DESC

    LIMIT 10
    """,
    conn,
    params={
        "filial_id": filial_id
    }
)

if not industrias.empty:

    st.dataframe(
        industrias,
        use_container_width=True,
        hide_index=True
    )

# =====================================
# ÚLTIMAS COMPRAS
# =====================================

st.divider()

st.subheader("🛒 Últimas Compras")

with engine.connect() as conn:

    ultimas_compras = pd.read_sql(
        """
            SELECT

                c.id,

                COALESCE(
                    f.nome,
                    c.fornecedor_avulso
                ) AS fornecedor,

                c.valor_total,

                c.data_compra

            FROM compras c

            LEFT JOIN fornecedores f
                ON c.fornecedor_id = f.id

            WHERE c.filial_id = %(filial_id)s

            ORDER BY c.id DESC

            LIMIT 20
        """,
        conn,
        params={
    "filial_id": filial_id
    }   
    )

if not ultimas_compras.empty:

    st.dataframe(
        ultimas_compras,
        use_container_width=True,
        hide_index=True
    )

# =====================================
# ÚLTIMAS VENDAS
# =====================================

st.divider()

st.subheader("💰 Últimas Vendas")

with engine.connect() as conn:

    ultimas_vendas = pd.read_sql(
        """
        SELECT

            v.id,

            i.nome AS industria,

            m.descricao AS material,

            v.quantidade,

            v.valor_total,

            v.data_venda

            FROM vendas v

            INNER JOIN industrias i
                ON v.industria_id = i.id

            INNER JOIN materiais m
                ON v.material_id = m.id

            WHERE v.filial_id = %(filial_id)s

            ORDER BY v.id DESC

            LIMIT 20
        """,
        conn,
        params={
    "filial_id": filial_id
    }
    )

if not ultimas_vendas.empty:

    st.dataframe(
        ultimas_vendas,
        use_container_width=True,
        hide_index=True
    )
