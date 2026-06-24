
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

if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()

render_menu()

perfil = st.session_state["usuario"]["perfil"]

filial_id = st.session_state.get(
    "filial_operacao"
)

if filial_id is None:

    st.warning(
        "Selecione uma filial no menu lateral."
    )

    st.stop()


validar_caixa_aberto(filial_id)

st.set_page_config(
    page_title="Compras",
    page_icon="🛒",
    layout="wide"
)


# =====================================
# CONFIGURAÇÃO
# =====================================


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
    f"📦 Compras - {filial_nome}"
)


# =====================================
# SESSION CARRINHO
# =====================================

if "carrinho" not in st.session_state:
    st.session_state.carrinho = []

# =====================================
# CARREGAR DADOS
# =====================================

with engine.connect() as conn:

    fornecedores = pd.read_sql(
        """
        SELECT
            id,
            nome
        FROM fornecedores
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

    

# =====================================
# FORNECEDOR
# =====================================

st.subheader("Fornecedor")

tipo_fornecedor = st.radio(
    "Origem do Material",
    [
        "Fornecedor Cadastrado",
        "Fornecedor Avulso"
    ],
    horizontal=True
)

fornecedor_id = None
fornecedor_avulso = None

if tipo_fornecedor == "Fornecedor Cadastrado":

    if fornecedores.empty:
        st.warning("Cadastre um fornecedor primeiro.")
        st.stop()

    fornecedor_nome = st.selectbox(
        "Fornecedor",
        fornecedores["nome"].tolist()
    )

else:

    fornecedor_avulso = st.text_input(
        "Fornecedor Avulso"
    )

# =====================================
# MATERIAL
# =====================================

st.divider()

st.subheader("Adicionar Item")

if materiais.empty:
    st.warning("Cadastre materiais primeiro.")
    st.stop()

col1, col2, col3 = st.columns(3)

with col1:

    material_nome = st.selectbox(
        "Material",
        materiais["descricao"].tolist()
    )

with col2:

    quantidade = st.number_input(
        "Peso (KG)",
        min_value=0.0,
        step=0.01,
        format="%.3f"
    )

with col3:

    valor_kg = st.number_input(
        "Valor por KG",
        min_value=0.0,
        step=0.01,
        format="%.2f"
    )

valor_total_item = quantidade * valor_kg

# =====================================
# RESUMO ITEM
# =====================================

c1, c2, c3 = st.columns(3)

with c1:
    st.metric(
        "Peso",
        f"{quantidade:.3f} KG"
    )

with c2:
    st.metric(
        "Preço/KG",
        f"R$ {valor_kg:.2f}"
    )

with c3:
    st.metric(
        "Valor Item",
        f"R$ {valor_total_item:.2f}"
    )

# =====================================
# ADICIONAR ITEM
# =====================================

if st.button(
    "➕ Adicionar Item",
    use_container_width=True
):

    if quantidade <= 0:
        st.warning("Informe uma quantidade válida.")
        st.stop()

    if valor_kg <= 0:
        st.warning("Informe um valor válido.")
        st.stop()

    material_id = materiais.loc[
        materiais["descricao"] == material_nome,
        "id"
    ].iloc[0]

    st.session_state.carrinho.append({
        "material_id": int(material_id),
        "material": material_nome,
        "quantidade": float(quantidade),
        "valor_kg": float(valor_kg),
        "valor_total": float(valor_total_item)
    })

    st.rerun()

# =====================================
# CARRINHO
# =====================================

st.divider()

st.subheader("🛒 Carrinho")

if len(st.session_state.carrinho) == 0:

    st.info("Nenhum item adicionado.")

else:

    df_carrinho = pd.DataFrame(
        st.session_state.carrinho
    )

    st.dataframe(
        df_carrinho[
            [
                "material",
                "quantidade",
                "valor_kg",
                "valor_total"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

    st.subheader("Remover Item")

    item_remover = st.selectbox(
        "Selecione um item",
        range(len(st.session_state.carrinho)),
        format_func=lambda x:
            st.session_state.carrinho[x]["material"]
    )

    if st.button("🗑️ Remover Item"):

        st.session_state.carrinho.pop(
            item_remover
        )

        st.rerun()

# =====================================
# TOTAL GERAL
# =====================================

total_geral = sum(
    item["valor_total"]
    for item in st.session_state.carrinho
)

st.markdown(
    f"""
    <div style="
        background-color:rgb(19 227 192);
        padding:25px;
        border-radius:12px;
        text-align:center;
        margin-top:15px;
        margin-bottom:15px;
    ">
        <h3>TOTAL DA COMPRA</h3>
        <h1>💰 R$ {total_geral:.2f}</h1>
    </div>
    """,
    unsafe_allow_html=True
)

observacao = st.text_area(
    "Observação"
)

# =====================================
# FINALIZAR
# =====================================

if st.button(
    "💾 Finalizar Compra",
    use_container_width=True
):

    if len(st.session_state.carrinho) == 0:

        st.warning(
            "Adicione pelo menos um item."
        )

        st.stop()

    if (
        tipo_fornecedor == "Fornecedor Avulso"
        and fornecedor_avulso.strip() == ""
    ):

        st.warning(
            "Informe o fornecedor avulso."
        )

        st.stop()

    with engine.begin() as conn:

        if tipo_fornecedor == "Fornecedor Cadastrado":

            fornecedor_id = conn.execute(
                text("""
                    SELECT id
                    FROM fornecedores
                    WHERE nome = :nome
                """),
                {
                    "nome": fornecedor_nome
                }
            ).scalar()

        compra_id = conn.execute(
            text("""
                INSERT INTO compras
                    (
                        filial_id,
                        fornecedor_id,
                        fornecedor_avulso,
                        valor_total,
                        observacao
                    )
                    VALUES
                    (
                        :filial_id,
                        :fornecedor_id,
                        :fornecedor_avulso,
                        :valor_total,
                        :observacao
                    )
                RETURNING id
            """),
           {
                "filial_id": filial_id,
                "fornecedor_id": fornecedor_id,
                "fornecedor_avulso": fornecedor_avulso,
                "valor_total": total_geral,
                "observacao": observacao
            }
        ).scalar()

        for item in st.session_state.carrinho:

            conn.execute(
                text("""
                    INSERT INTO itens_compra
                    (
                        compra_id,
                        material_id,
                        quantidade,
                        valor_kg,
                        valor_total
                    )
                    VALUES
                    (
                        :compra_id,
                        :material_id,
                        :quantidade,
                        :valor_kg,
                        :valor_total
                    )
                """),
                {
                    "compra_id": compra_id,
                    "material_id": item["material_id"],
                    "quantidade": item["quantidade"],
                    "valor_kg": item["valor_kg"],
                    "valor_total": item["valor_total"]
                }
            )

            conn.execute(
                text("""
                    INSERT INTO estoque_movimentacao
                    (
                        filial_id,
                        material_id,
                        tipo,
                        quantidade,
                        origem,
                        referencia_id
                    )
                    VALUES
                    (
                        :filial_id,
                        :material_id,
                        'ENTRADA',
                        :quantidade,
                        'COMPRA',
                        :referencia_id
                    )
                """),
                {
                    "filial_id": filial_id,
                    "material_id": item["material_id"],
                    "quantidade": item["quantidade"],
                    "referencia_id": compra_id
                }
            )
            conn.execute(
                text("""
                    INSERT INTO financeiro_movimentacao
                    (
                        filial_id,
                        tipo,
                        valor,
                        origem,
                        referencia_id,
                        observacao
                    )
                    VALUES
                    (
                        :filial_id,
                        'SAIDA',
                        :valor,
                        'COMPRA',
                        :referencia_id,
                        :observacao
                    )
                """),
                {
                    "filial_id": filial_id,
                    "valor": total_geral,
                    "referencia_id": compra_id,
                    "observacao": "Compra registrada"
                }
            )

    st.session_state.carrinho = []


    st.success(
        "Compra registrada com sucesso!"
    )

    st.rerun()



# =====================================
# HISTÓRICO
# =====================================

st.divider()

st.subheader("📋 Histórico de Compras")

with engine.connect() as conn:
    historico = pd.read_sql(
        """
        SELECT

            c.id,

            COALESCE(
                f.nome,
                c.fornecedor_avulso
            ) AS fornecedor,

            m.descricao AS material,

            ic.quantidade,

            ic.valor_kg,

            ic.valor_total,

            c.data_compra

        FROM compras c

        LEFT JOIN fornecedores f
            ON c.fornecedor_id = f.id

        INNER JOIN itens_compra ic
            ON c.id = ic.compra_id

        INNER JOIN materiais m
            ON ic.material_id = m.id

        WHERE c.filial_id = %(filial_id)s

        ORDER BY c.id DESC
        """,
        conn,
        params={
            "filial_id": filial_id
        }
    )

if historico.empty:

    st.info("Nenhuma compra registrada.")

else:

    st.dataframe(
        historico,
        use_container_width=True,
        hide_index=True
    )
