from datetime import date
import pandas as pd
from seguranca import exigir_perfil
from seguranca_caixa import validar_caixa_aberto
from services.estoque import obter_saldo
from services.vendas import salvar_venda
from sqlalchemy import text
import streamlit as st

from database import engine
from menu import render_menu

# =====================================
# 1. CONFIGURAÇÃO DA PÁGINA & CSS
# =====================================
st.set_page_config(page_title="Vendas", page_icon="💰", layout="wide")


def carregar_css():
    with open("assets/style.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


carregar_css()

# =====================================
# 2. SEGURANÇA E ACESSO
# =====================================
if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()

render_menu()
perfil = st.session_state["usuario"]["perfil"]
filial_id = st.session_state.get("filial_operacao")

if filial_id is None:
    st.warning("Selecione uma filial no menu lateral.")
    st.stop()

# Validações de regras de negócio básicas
validar_caixa_aberto(filial_id)
exigir_perfil(["ADMIN"])

# =====================================
# 3. CARREGAMENTO DE DADOS (DB)
# =====================================
with engine.connect() as conn:
    # Nome da Filial
    filial_nome = conn.execute(
        text("SELECT nome FROM filiais WHERE id = :id"), {"id": filial_id}
    ).scalar()

    # Dataframes de Apoio
    industrias = pd.read_sql(
        "SELECT id, nome FROM industrias ORDER BY nome", conn
    )
    materiais = pd.read_sql(
        "SELECT id, descricao FROM materiais ORDER BY descricao", conn
    )
    categorias = pd.read_sql(
        "SELECT id, descricao FROM categorias_financeiras ORDER BY descricao",
        conn,
    )

st.title(f"📦 Vendas - {filial_nome}")

# Localização da categoria financeira obrigatória
categoria = categorias.loc[
    categorias["descricao"] == "Venda de Material"
]
if categoria.empty:
    st.error("Categoria financeira 'Venda de Material' não encontrada.")
    st.stop()

categoria_financeira_id = int(categoria.iloc[0]["id"])

# =====================================
# 4. INTERFACE E FORMULÁRIO DE VENDA
# =====================================
st.subheader("Nova Venda")

if materiais.empty or industrias.empty:
    st.warning("Certifique-se de ter materiais e indústrias cadastradas no sistema.")
    st.stop()

with st.container(border=True):
    col_mat, col_ind = st.columns(2)

    with col_mat:
        material_nome = st.selectbox(
            "Selecione o Material",
            materiais["descricao"].tolist(),
            key="material_venda",
        )
        material_id = int(
            materiais.loc[
                materiais["descricao"] == material_nome, "id"
            ].iloc[0]
        )

    with col_ind:
        industria_nome = st.selectbox(
            "Selecione a Indústria", industrias["nome"].tolist()
        )
        industria_id = int(
            industrias.loc[
                industrias["nome"] == industria_nome, "id"
            ].iloc[0]
        )

    # Consulta o estoque atualizado em tempo real com base no material selecionado
    estoque_atual = float(obter_saldo(filial_id, material_id) or 0)

    # --- INPUTS DE VALORES ---
    c_qtd, c_val, c_venc, c_pag = st.columns(4)

    with c_qtd:
        quantidade = st.number_input(
            "Quantidade (KG)", min_value=0.0, step=0.1, format="%.3f"
        )
    with c_val:
        valor_unitario = st.number_input(
            "Valor por KG (R$)", min_value=0.0, step=0.01, format="%.2f"
        )
    with c_venc:
        vencimento = st.date_input("Data de Vencimento", value=date.today())
    with c_pag:
        pagamento = st.radio(
            "Forma de Recebimento", ["À Vista", "A Prazo"], horizontal=True
        )

    observacao = st.text_area("Observações da Venda")

    # Cálculos Dinâmicos para os Cards Informativos
    valor_total = quantidade * valor_unitario

    # --- PAINEL INFORMATIVO (MÉTRICAS E STATUS) ---
    st.write("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("📦 Estoque Atual", f"{estoque_atual:,.3f} KG")
    m2.metric("⚖️ Qtd. Digitada", f"{quantidade:,.3f} KG")
    m3.metric("💲 Valor/KG", f"R$ {valor_unitario:,.2f}")
    m4.metric("💰 Total Operação", f"R$ {valor_total:,.2f}")

    # Status Visual do Estoque baseado no input do usuário
    if estoque_atual <= 0:
        st.error("❌ Material sem estoque disponível na filial.")
    elif estoque_atual < 100:
        st.warning("⚠️ Atenção: Estoque baixo para este item.")
    else:
        st.success("✅ Volume de estoque seguro para operação.")

    # --- BOTÃO DE SUBMIT (AÇÃO DE SALVAR) ---
    st.write("---")
    if st.button("💾 Registrar Venda", use_container_width=True):
        # Validações internas antes de chamar a service
        if quantidade <= 0:
            st.warning("Informe uma quantidade válida superior a zero.")
            st.stop()

        if valor_unitario <= 0:
            st.warning("Informe um valor por KG válido.")
            st.stop()

        if quantidade > estoque_atual:
            st.error(
                f"Estoque insuficiente para concluir a venda. Disponível: {estoque_atual:.3f} KG"
            )
            st.stop()

        try:
            venda_id = salvar_venda(
                filial_id=filial_id,
                industria_id=industria_id,
                material_id=material_id,
                quantidade=quantidade,
                valor_unitario=valor_unitario,
                categoria_financeira_id=categoria_financeira_id,
                vencimento=vencimento,
                observacao=observacao,
                usuario_id=st.session_state["usuario"]["id"],
                pagamento="AVISTA" if pagamento == "À Vista" else "PRAZO",
            )

            st.success(f"Venda #{venda_id} registrada com sucesso!")
            st.rerun()

        except Exception as e:
            st.error(f"Erro técnico ao registrar venda no banco: \n{e}")

# =====================================
# 5. HISTÓRICO DE VENDAS
# =====================================
st.divider()
st.subheader("📋 Histórico de Vendas da Filial")

with engine.connect() as conn:
    historico = pd.read_sql(
        text(
            """
            SELECT 
                v.id AS "ID Venda",
                i.nome AS "Indústria",
                m.descricao AS "Material",
                v.quantidade AS "Qtd (KG)",
                v.valor_unitario AS "Valor/KG",
                v.valor_total AS "Total Faturado",
                v.data_venda AS "Data Venda"
            FROM vendas v
            INNER JOIN industrias i ON i.id = v.industria_id
            INNER JOIN materiais m ON m.id = v.material_id
            WHERE v.filial_id = :filial
            ORDER BY v.id DESC
            """
        ),
        conn,
        params={"filial": filial_id},
    )

if historico.empty:
    st.info("Nenhuma venda registrada para esta filial até o momento.")
else:
    st.dataframe(
        historico,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Qtd (KG)": st.column_config.NumberColumn(format="%.3f"),
            "Valor/KG": st.column_config.NumberColumn(format="R$ %.2f"),
            "Total Faturado": st.column_config.NumberColumn(format="R$ %.2f"),
        },
    )