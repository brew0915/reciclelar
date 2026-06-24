
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

if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()


render_menu()
# =====================================
# CONFIGURAÇÃO
# =====================================
    
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
    
st.set_page_config(
    page_title="Materiais",
    page_icon="📦",
    layout="wide"
)


# =====================================
# TÍTULO
# =====================================

st.title("📦 Cadastro de Materiais")

# =====================================
# FORMULÁRIO
# =====================================

with st.expander("➕ Novo Material", expanded=True):

    with st.form("form_material"):

        col1, col2, col3 = st.columns(3)

        with col1:

            descricao = st.text_input(
                "Descrição"
            )

        with col2:

            categoria = st.selectbox(
                "Categoria",
                [
                    "Papel",
                    "Plástico",
                    "Metal",
                    "Vidro",
                    "Eletrônico",
                    "Outros"
                ]
            )

        with col3:

            unidade = st.selectbox(
                "Unidade",
                [
                    "KG",
                    "TON",
                    "UN",
                    "GR"
                ]
            )

        salvar = st.form_submit_button(
            "💾 Salvar Material",
            use_container_width=True
        )

# =====================================
# SALVAR
# =====================================

if salvar:

    descricao = descricao.strip()

    if descricao == "":

        st.warning(
            "Informe a descrição do material."
        )

        st.stop()

    with engine.begin() as conn:

        existe = conn.execute(
            text("""
                SELECT COUNT(*)
                FROM materiais
                WHERE UPPER(descricao)
                    = UPPER(:descricao)
            """),
            {
                "descricao": descricao
            }
        ).scalar()

        if existe > 0:

            st.warning(
                "Material já cadastrado."
            )

            st.stop()

        conn.execute(
            text("""
                INSERT INTO materiais
                (
                    descricao,
                    categoria,
                    unidade
                )
                VALUES
                (
                    :descricao,
                    :categoria,
                    :unidade
                )
            """),
            {
                "descricao": descricao,
                "categoria": categoria,
                "unidade": unidade
            }
        )

    st.success(
        "Material cadastrado com sucesso!"
    )

    st.rerun()

# =====================================
# LISTAGEM
# =====================================

st.divider()

st.subheader("📋 Materiais Cadastrados")

with engine.connect() as conn:

    df = pd.read_sql(
        """
        SELECT
            id,
            descricao,
            categoria,
            unidade
        FROM materiais
        ORDER BY descricao
        """,
        conn
    )

if df.empty:

    st.info(
        "Nenhum material cadastrado."
    )

    st.stop()

# =====================================
# PESQUISA
# =====================================

busca = st.text_input(
    "🔎 Pesquisar Material"
)

if busca:

    df = df[
        df["descricao"]
        .str.contains(
            busca,
            case=False,
            na=False
        )
    ]

# =====================================
# KPIs
# =====================================

c1, c2 = st.columns(2)

with c1:

    st.metric(
        "📦 Total de Materiais",
        len(df)
    )

with c2:

    st.metric(
        "📂 Categorias",
        df["categoria"].nunique()
    )

# =====================================
# TABELA
# =====================================

st.dataframe(
    df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "id": "ID",
        "descricao": "Descrição",
        "categoria": "Categoria",
        "unidade": "Unidade"
    }
)

# =====================================
# EXCLUSÃO
# =====================================

st.divider()

st.subheader("🗑️ Excluir Material")

material_excluir = st.selectbox(
    "Selecione o material",
    df["descricao"].tolist()
)

if st.button(
    "Excluir Material",
    type="secondary",
    use_container_width=True
):

    st.session_state["confirmar_exclusao"] = True

if st.session_state.get(
    "confirmar_exclusao",
    False
):

    st.warning(
        f"Deseja realmente excluir "
        f"'{material_excluir}'?"
    )

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "✅ Confirmar Exclusão",
            use_container_width=True
        ):

            material_id = df.loc[
                df["descricao"]
                == material_excluir,
                "id"
            ].iloc[0]

            with engine.begin() as conn:

                conn.execute(
                    text("""
                        DELETE FROM materiais
                        WHERE id = :id
                    """),
                    {
                        "id": int(material_id)
                    }
                )

            st.session_state[
                "confirmar_exclusao"
            ] = False

            st.success(
                "Material removido com sucesso!"
            )

            st.rerun()

    with col2:

        if st.button(
            "❌ Cancelar",
            use_container_width=True
        ):

            st.session_state[
                "confirmar_exclusao"
            ] = False

            st.rerun()
