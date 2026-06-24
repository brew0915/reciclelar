
import streamlit as st
import pandas as pd
from sqlalchemy import text

from database import engine
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
perfil = st.session_state["usuario"]["perfil"]

# ADMIN escolhe a filial
if perfil == "ADMIN":

    with engine.connect() as conn:

        filiais = pd.read_sql(
            """
            SELECT id, nome
            FROM filiais
            ORDER BY nome
            """,
            conn
        )

    filial_escolhida = st.sidebar.selectbox(
        "🏢 Filial",
        ["Todas"] + filiais["nome"].tolist(),
        key="filial_admin"
    )

    st.session_state["filial_ativa"] = filial_escolhida

# OPERADOR e CONSULTA ficam presos à própria filial
else:

    st.session_state["filial_ativa"] = (
        st.session_state["usuario"]["filial_id"]
    )




st.title("⚠️ Configuração de Estoque Mínimo")

st.markdown(
    """
    Defina a quantidade mínima aceitável para cada material.
    Quando o estoque atual ficar abaixo desse valor,
    o sistema emitirá alertas.
    """
)

# =====================================
# CARREGAR MATERIAIS
# =====================================

with engine.connect() as conn:

    materiais = pd.read_sql(
        """
        SELECT

            m.id,
            m.descricao,

            COALESCE(
                em.quantidade_minima,
                0
            ) AS quantidade_minima

        FROM materiais m

        LEFT JOIN estoque_minimo em
            ON m.id = em.material_id

        ORDER BY m.descricao
        """,
        conn
    )

# =====================================
# CADASTRO / EDIÇÃO
# =====================================

st.divider()

st.subheader("Configurar Estoque Mínimo")

material_nome = st.selectbox(
    "Material",
    materiais["descricao"].tolist()
)

material_id = materiais.loc[
    materiais["descricao"] == material_nome,
    "id"
].iloc[0]

valor_atual = materiais.loc[
    materiais["descricao"] == material_nome,
    "quantidade_minima"
].iloc[0]

quantidade_minima = st.number_input(
    "Quantidade Mínima (KG)",
    min_value=0.0,
    value=float(valor_atual),
    step=1.0
)

if st.button(
    "💾 Salvar Configuração",
    use_container_width=True
):

    with engine.begin() as conn:

        existe = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM estoque_minimo
                WHERE material_id = :material_id
            """),
            {
                "material_id": int(material_id)
            }
        ).scalar()

        if existe > 0:

            conn.execute(
                text("""
                    UPDATE estoque_minimo
                    SET quantidade_minima =
                        :quantidade_minima
                    WHERE material_id =
                        :material_id
                """),
                {
                    "quantidade_minima":
                        quantidade_minima,
                    "material_id":
                        int(material_id)
                }
            )

        else:

            conn.execute(
                text("""
                    INSERT INTO estoque_minimo
                    (
                        material_id,
                        quantidade_minima
                    )
                    VALUES
                    (
                        :material_id,
                        :quantidade_minima
                    )
                """),
                {
                    "material_id":
                        int(material_id),
                    "quantidade_minima":
                        quantidade_minima
                }
            )

    st.success(
        "Configuração salva com sucesso!"
    )

    st.rerun()

# =====================================
# LISTAGEM
# =====================================

st.divider()

st.subheader("Materiais Configurados")

with engine.connect() as conn:

    df = pd.read_sql(
        """
        SELECT

            m.descricao,

            COALESCE(
                em.quantidade_minima,
                0
            ) AS estoque_minimo

        FROM materiais m

        LEFT JOIN estoque_minimo em
            ON m.id = em.material_id

        ORDER BY m.descricao
        """,
        conn
    )

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True
)

# =====================================
# REMOVER CONFIGURAÇÃO
# =====================================

st.divider()

st.subheader("Remover Configuração")

material_remover = st.selectbox(
    "Selecione o material",
    materiais["descricao"].tolist(),
    key="remover_material"
)

if st.button(
    "🗑️ Remover Estoque Mínimo",
    use_container_width=True
):

    material_id_remover = materiais.loc[
        materiais["descricao"] == material_remover,
        "id"
    ].iloc[0]

    with engine.begin() as conn:

        conn.execute(
            text("""
                DELETE FROM estoque_minimo
                WHERE material_id =
                    :material_id
            """),
            {
                "material_id":
                    int(material_id_remover)
            }
        )

    st.success(
        "Configuração removida!"
    )

    st.rerun()

