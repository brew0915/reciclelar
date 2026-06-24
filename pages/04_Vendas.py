import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import engine
from menu import render_menu
from seguranca_caixa import validar_caixa_aberto


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

render_menu()

if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()

perfil = st.session_state["usuario"]["perfil"]

filial_id = st.session_state.get(
    "filial_operacao"
)

if filial_id is None:

    st.warning(
        "Selecione uma filial no menu lateral."
    )

    st.stop()
# OPERADOR e CONSULTA ficam presos à própria filial
else:

    st.session_state["filial_ativa"] = (
        st.session_state["usuario"]["filial_id"]
    )



validar_caixa_aberto(filial_id)

from seguranca import exigir_perfil

exigir_perfil(["ADMIN"])

st.set_page_config(
    page_title="Vendas",
    page_icon="💰",
    layout="wide"
)





# ==========================
# TITULO FILIAL
# ==========================


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
    f"📦 Vendas- {filial_nome}"
)
# ==========================
# CARREGAR DADOS
# ==========================

with engine.connect() as conn:

    industrias = pd.read_sql(
        """
        SELECT
            id,
            nome
        FROM industrias
        ORDER BY nome
        """,
        conn
    )

    materiais = pd.read_sql(
        """
        SELECT
            id,
            descricao
        FROM materiais
        ORDER BY descricao
        """,
        conn
    )

# ==========================
# FORMULÁRIO
# ==========================

with st.form("form_venda"):

    industria_nome = st.selectbox(
        "Indústria",
        industrias["nome"].tolist()
    )

    material_nome = st.selectbox(
        "Material",
        materiais["descricao"].tolist()
    )

    # Estoque atual

    with engine.connect() as conn:

        estoque = conn.execute(
            text("""
                SELECT
                    COALESCE(
                        SUM(
                            CASE
                                WHEN tipo = 'ENTRADA'
                                THEN quantidade
                                ELSE -quantidade
                            END
                        ),
                        0
                    )
                FROM estoque_movimentacao e
                INNER JOIN materiais m
                    ON e.material_id = m.id
                WHERE m.descricao = :descricao
            """),
            {
                "descricao": material_nome
            }
        ).scalar()

    st.info(
        f"Estoque disponível: {estoque:.2f} KG"
    )

    quantidade = st.number_input(
        "Quantidade",
        min_value=0.0,
        step=0.1
    )

    valor_kg = st.number_input(
        "Valor por KG (R$)",
        min_value=0.0,
        step=0.01
    )

    valor_total = quantidade * valor_kg

    st.metric(
        "Valor Total",
        f"R$ {valor_total:,.2f}"
    )

    observacao = st.text_area(
        "Observação"
    )

    salvar = st.form_submit_button(
        "Registrar Venda"
    )

# ==========================
# SALVAR
# ==========================

if salvar:

    if quantidade <= 0:

        st.warning("Informe uma quantidade válida.")
        st.stop()

    if valor_kg <= 0:

        st.warning("Informe um valor válido.")
        st.stop()

    if quantidade > estoque:

        st.error(
            f"Estoque insuficiente. Disponível: {estoque:.2f} KG"
        )
        st.stop()

    with engine.begin() as conn:

        material_id = conn.execute(
            text("""
                SELECT id
                FROM materiais
                WHERE descricao = :descricao
            """),
            {
                "descricao": material_nome
            }
        ).scalar()

        industria_id = conn.execute(
            text("""
                SELECT id
                FROM industrias
                WHERE nome = :nome
            """),
            {
                "nome": industria_nome
            }
        ).scalar()

        # REGISTRA VENDA

        venda_id = conn.execute(
            text("""
                INSERT INTO vendas
                (
                    industria_id,
                    material_id,
                    quantidade,
                    valor_kg,
                    valor_total,
                    observacao
                )
                VALUES
                (
                    :industria_id,
                    :material_id,
                    :quantidade,
                    :valor_kg,
                    :valor_total,
                    :observacao
                )
                RETURNING id
            """),
            {
                "industria_id": industria_id,
                "material_id": material_id,
                "quantidade": quantidade,
                "valor_kg": valor_kg,
                "valor_total": valor_total,
                "observacao": observacao
            }
        ).scalar()

        # BAIXA ESTOQUE

        conn.execute(
            text("""
                INSERT INTO estoque_movimentacao
                (
                    material_id,
                    tipo,
                    quantidade,
                    origem,
                    referencia_id
                )
                VALUES
                (
                    :material_id,
                    'SAIDA',
                    :quantidade,
                    'VENDA',
                    :venda_id
                )
            """),
            {
                "material_id": material_id,
                "quantidade": quantidade,
                "venda_id": venda_id
            }
        )

        # ENTRADA FINANCEIRA NO CAIXA

        conn.execute(
            text("""
                INSERT INTO financeiro_movimentacao
                (
                    tipo,
                    valor,
                    origem,
                    referencia_id,
                    observacao
                )
                VALUES
                (
                    'ENTRADA',
                    :valor,
                    'VENDA',
                    :referencia_id,
                    :observacao
                )
            """),
            {
                "valor": valor_total,
                "referencia_id": venda_id,
                "observacao": f"Venda para {industria_nome}"
            }
        )

    st.success("Venda registrada com sucesso!")
    st.rerun()

# ==========================
# HISTÓRICO
# ==========================

st.divider()

st.subheader("Histórico de Vendas")

with engine.connect() as conn:

    historico = pd.read_sql(
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

        ORDER BY v.id DESC
        """,
        conn
    )

if historico.empty:

    st.info("Nenhuma venda registrada.")

else:

    st.dataframe(
        historico,
        use_container_width=True,
        hide_index=True
    )