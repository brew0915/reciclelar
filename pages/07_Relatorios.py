import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import engine
from datetime import date, timedelta
from io import BytesIO
from menu import render_menu

render_menu()

def carregar_css():
    with open("assets/style.css") as f:
        st.markdown(
            f"<style>{f.read()}</style>",
            unsafe_allow_html=True
        )

carregar_css()


if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()


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

if filial_id is None:

    st.error(
        "Selecione uma filial."
    )

    st.stop()

st.set_page_config(
    page_title="Relatórios",
    page_icon="📑",
    layout="wide"
)





st.title(
    f"📑 Relatórios - {filial_nome}"
)

st.caption(
    f"Filial selecionada: {filial_nome}"
)

# ====================================
# FILTROS
# ====================================

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

tipo_relatorio = st.selectbox(
    "Tipo de Relatório",
    [
        "Compras",
        "Vendas",
        "Estoque",
        "Resultado Financeiro"
    ]
)

# ====================================
# COMPRAS
# ====================================

if tipo_relatorio == "Compras":

    with engine.connect() as conn:

        df = pd.read_sql(
            """
            SELECT

                c.id,

                COALESCE(
                    f.nome,
                    c.fornecedor_avulso
                ) AS fornecedor,

                c.valor_total,

                c.observacao,

                c.data_compra

            FROM compras c

            LEFT JOIN fornecedores f
                ON c.fornecedor_id = f.id

            WHERE c.filial_id = %(filial_id)s
            AND c.data_compra::date
            BETWEEN %(inicio)s
            AND %(fim)s

            ORDER BY c.data_compra DESC
            """,
            conn,
            params={
                "inicio": data_inicio,
                "fim": data_fim,
                "filial_id": filial_id
            }
        )

# ====================================
# VENDAS
# ====================================

elif tipo_relatorio == "Vendas":

    with engine.connect() as conn:

        df = pd.read_sql(
            """
            SELECT

                v.id,

                i.nome AS industria,

                m.descricao AS material,

                v.quantidade,

                v.valor_kg,

                v.valor_total,

                v.data_venda

            FROM vendas v

            INNER JOIN industrias i
                ON v.industria_id = i.id

            INNER JOIN materiais m
                ON v.material_id = m.id

            WHERE v.filial_id = %(filial_id)s
            AND v.data_venda::date
            BETWEEN %(inicio)s
            AND %(fim)s

            ORDER BY v.data_venda DESC
            """,
            conn,
            params={
                "inicio": data_inicio,
                "fim": data_fim,
                "filial_id": filial_id
            }
        )

# ====================================
# ESTOQUE
# ====================================

elif tipo_relatorio == "Estoque":

    with engine.connect() as conn:

            df = pd.read_sql(
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
            conn

# ====================================
# RESULTADO FINANCEIRO
# ====================================

else:

    with engine.connect() as conn:

        compras = conn.execute(
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

        vendas = conn.execute(
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

    lucro = vendas - compras

    df = pd.DataFrame({
        "Indicador": [
            "Compras",
            "Vendas",
            "Lucro Bruto"
        ],
        "Valor": [
            compras,
            vendas,
            lucro
        ]
    })

# ====================================
# EXIBIÇÃO
# ====================================

st.divider()

st.subheader(f"Relatório - {tipo_relatorio}")

if df.empty:

    st.info("Nenhum registro encontrado.")

else:

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )

    # ================================
    # EXCEL
    # ================================

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        df.to_excel(
            writer,
            sheet_name="Relatorio",
            index=False
        )

    excel_data = output.getvalue()

    st.download_button(
        label="📥 Baixar Excel",
        data=excel_data,
        file_name=f"{tipo_relatorio}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
