import pandas as pd
from sqlalchemy import text
import streamlit as st

from database import engine
from menu import render_menu

# =====================================
# 1. CONFIGURAÇÃO DA PÁGINA & CSS
# =====================================
# CRÍTICO: st.set_page_config deve ser a primeira instrução Streamlit executada na página
st.set_page_config(page_title="Controle de Estoque", page_icon="📦", layout="wide")


def carregar_css():
    with open("assets/style.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


carregar_css()

# =====================================
# 2. SEGURANÇA E VALIDAÇÃO DE ACESSO
# =====================================
if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()

render_menu()

perfil = st.session_state["usuario"]["perfil"]
filial_id = st.session_state.get("filial_operacao")

if filial_id is None:
    st.error("Selecione uma filial no menu lateral.")
    st.stop()

# =====================================
# 3. CARREGAMENTO DE INFORMAÇÕES DA FILIAL
# =====================================
with engine.connect() as conn:
    filial_nome = conn.execute(
        text("SELECT nome FROM filiais WHERE id = :id"), {"id": filial_id}
    ).scalar()

st.title(f"📦 Controle de Estoque - {filial_nome}")

# =====================================
# 4. CONSULTA: ESTOQUE ATUAL
# =====================================
with engine.connect() as conn:
    estoque = pd.read_sql(
        text(
            """
            SELECT
                m.id AS "ID",
                m.descricao AS "Descrição do Material",
                COALESCE(
                    SUM(
                        CASE
                            WHEN e.tipo = 'ENTRADA' THEN e.quantidade
                            ELSE -e.quantidade
                        END
                    ),
                    0
                ) AS "Estoque Atual"
            FROM materiais m
            LEFT JOIN estoque_movimentacao e
                ON m.id = e.material_id
                AND e.filial_id = :filial_id
            GROUP BY
                m.id,
                m.descricao
            ORDER BY
                "Estoque Atual" DESC
            """
        ),
        conn,
        params={"filial_id": filial_id},
    )

# =====================================
# 5. PAINEL DE METRICAS (KPIs)
# =====================================
total_materiais = len(estoque)
peso_total = (
    estoque["Estoque Atual"].sum() if not estoque.empty else 0
)

c1, c2 = st.columns(2)
with c1:
    st.metric("📦 Materiais Cadastrados", f"{total_materiais} itens")
with c2:
    st.metric("⚖️ Volume em Estoque (Total)", f"{peso_total:,.3f} KG")

# =====================================
# 6. FILTRO DE PESQUISA DINÂMICA
# =====================================
busca = st.text_input("🔎 Filtrar por descrição do material", placeholder="Digite o nome do material...")

# Cria uma cópia para exibição sem alterar a base de cálculo dos KPIs principais
estoque_filtrado = estoque.copy()
if busca:
    estoque_filtrado = estoque_filtrado[
        estoque_filtrado["Descrição do Material"].str.contains(
            busca, case=False, na=False
        )
    ]

# =====================================
# 7. EXIBIÇÃO: ESTOQUE ATUAL
# =====================================
st.subheader("📦 Posição de Estoque")

if estoque_filtrado.empty:
    st.info("Nenhum material localizado para este critério de busca.")
else:
    st.dataframe(
        estoque_filtrado,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID": st.column_config.NumberColumn(format="%d"),
            "Estoque Atual": st.column_config.NumberColumn(format="%.3f KG"),
        },
    )

# =====================================
# 8. CONSULTA: ESTOQUE BAIXO (ALERTAS COGNITIVOS)
# =====================================
st.divider()
st.subheader("⚠️ Materiais com Estoque Crítico (Abaixo do Mínimo)")

with engine.connect() as conn:
    estoque_baixo = pd.read_sql(
        text(
            """
            SELECT
                m.descricao AS "Descrição do Material",
                em.quantidade_minima AS "Qtd Mínima Requerida",
                COALESCE(
                    SUM(
                        CASE
                            WHEN e.tipo = 'ENTRADA' THEN e.quantidade
                            ELSE -e.quantidade
                        END
                    ),
                    0
                ) AS "Estoque Atual"
            FROM estoque_minimo em
            INNER JOIN materiais m
                ON em.material_id = m.id
            LEFT JOIN estoque_movimentacao e
                ON m.id = e.material_id
                AND e.filial_id = :filial_id
            GROUP BY
                m.descricao,
                em.quantidade_minima
            HAVING
                COALESCE(
                    SUM(
                        CASE
                            WHEN e.tipo = 'ENTRADA' THEN e.quantidade
                            ELSE -e.quantidade
                        END
                    ),
                    0
                ) <= em.quantidade_minima
            """
        ),
        conn,
        params={"filial_id": filial_id},
    )

if estoque_baixo.empty:
    st.success("Operação Segura: Nenhum material está abaixo do nível de segurança operacional.")
else:
    st.dataframe(
        estoque_baixo,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Qtd Mínima Requerida": st.column_config.NumberColumn(format="%.3f KG"),
            "Estoque Atual": st.column_config.NumberColumn(format="%.3f KG"),
        },
    )

# =====================================
# 9. CONSULTA: ÚLTIMAS MOVIMENTAÇÕES
# =====================================
st.divider()
st.subheader("📋 Auditoria: Últimas 100 Movimentações")

with engine.connect() as conn:
    movimentacoes = pd.read_sql(
        text(
            """
            SELECT
                e.id AS "ID Reg.",
                e.data_movimentacao AS "Data/Hora",
                m.descricao AS "Material",
                e.tipo AS "Operação",
                e.quantidade AS "Qtd (KG)",
                e.origem AS "Módulo de Origem",
                e.referencia_id AS "ID Ref."
            FROM estoque_movimentacao e
            INNER JOIN materiais m
                ON e.material_id = m.id
            WHERE e.filial_id = :filial_id
            ORDER BY
                e.id DESC
            LIMIT 100
            """
        ),
        conn,
        params={"filial_id": filial_id},
    )

if movimentacoes.empty:
    st.info("Nenhum registro de movimentação encontrado nesta filial.")
else:
    st.dataframe(
        movimentacoes,
        use_container_width=True,
        hide_index=True,
        column_config={
            "ID Reg.": st.column_config.NumberColumn(format="%d"),
            "ID Ref.": st.column_config.NumberColumn(format="%d"),
            "Qtd (KG)": st.column_config.NumberColumn(format="%.3f KG"),
            "Data/Hora": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
        },
    )

# =====================================
# 10. GRÁFICO (RANKING DE VOLUMES)
# =====================================
st.divider()
st.subheader("🏆 Análise Gráfica: Maiores Volumes")

if not estoque.empty:
    # Seleciona as colunas renomeadas corretamente para plotagem equilibrada
    ranking = estoque[["Descrição do Material", "Estoque Atual"]]
    st.bar_chart(
        ranking.set_index("Descrição do Material"),
        color="#16a34a"  # Mantém a paleta verde corporativa do seu CSS profissional
    )