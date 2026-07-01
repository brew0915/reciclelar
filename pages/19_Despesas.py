from datetime import date
from database import engine
from menu import render_menu
import pandas as pd
from sqlalchemy import text
import streamlit as st

# =====================================
# 1. CONFIGURAÇÃO DA PÁGINA (Sempre no início)
# =====================================
st.set_page_config(
    page_title="Lançamento de Despesas", page_icon="💸", layout="wide"
)


def carregar_css():
    with open("assets/style.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


carregar_css()

# =====================================
# 2. SEGURANÇA E CONTEXTO DE OPERAÇÃO
# =====================================
if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()

render_menu()

filial_id = st.session_state.get("filial_operacao")
if filial_id is None:
    st.error("Selecione uma filial ativa no menu lateral para prosseguir.")
    st.stop()

# Carregamento prévio das categorias cadastrais
with engine.connect() as conn:
    categorias = pd.read_sql(
        text(
            "SELECT id, descricao FROM categorias_financeiras ORDER BY descricao"
        ),
        conn,
    )

# =====================================
# 3. INTERFACE ESTRUTURADA EM ABAS
# =====================================
st.title("💸 Gestão de Despesas e Obrigações")
st.caption("Lançamento de saídas operacionais, provisões e fluxo de caixa")
st.write(" ")

tab_registro, tab_historico = st.tabs(
    ["📝 Registrar Nova Despesa", "📋 Histórico de Lançamentos"]
)

# =====================================
# TAB 1: FORMULÁRIO DE LANÇAMENTO
# =====================================
with tab_registro:
    with st.form("form_despesa", clear_on_submit=True):
        col_form1, col_form2 = st.columns(2)

        with col_form1:
            categoria = st.selectbox("Categoria Financeira", categorias["descricao"])
            descricao = st.text_input("Descrição do Lançamento", placeholder="Ex: Manutenção Predial Ar Condicionado")
            fornecedor = st.text_input("Fornecedor / Credor (Opcional)", placeholder="Razão Social ou Nome Fantasia")
            valor = st.number_input("Valor Nominal (R$)", min_value=0.0, step=0.01, format="%.2f")

        with col_form2:
            data_despesa = st.date_input("Data de Competência", value=date.today())
            vencimento = st.date_input("Data de Vencimento", value=date.today())
            forma = st.radio("Condição de Liquidação", ["Pago Agora (À Vista)", "Pagar Depois (Provisionar)"])
            observacao = st.text_area("Justificativa / Observações Internas", placeholder="Detalhes adicionais sobre a despesa...")

        st.write(" ")
        salvar = st.form_submit_button("💾 Homologar Lançamento Financeiro", use_container_width=True)

    if salvar:
        if not descricao.strip():
            st.warning("Preenchimento obrigatório: Informe a descrição da despesa.")
            st.stop()

        if valor <= 0:
            st.warning("Preenchimento obrigatório: O valor nominal deve ser superior a R$ 0,00.")
            st.stop()

        categoria_id = int(
            categorias.loc[categorias["descricao"] == categoria, "id"].iloc[0]
        )
        status = "PAGO" if "Pago Agora" in forma else "ABERTO"

        # Escopo Transacional Unificado (Garante consistência ACID)
        with engine.begin() as conn:
            # 1. Inserção na Tabela de Despesas
            despesa_id = conn.execute(
                text(
                    """
                    INSERT INTO despesas (filial_id, categoria_id, descricao, fornecedor, valor, data_despesa, observacao, usuario_id)
                    VALUES (:filial, :categoria, :descricao, :fornecedor, :valor, :data, :obs, :usuario)
                    RETURNING id
                """
                ),
                {
                    "filial": filial_id,
                    "categoria": categoria_id,
                    "descricao": descricao,
                    "fornecedor": fornecedor,
                    "valor": valor,
                    "data": data_despesa,
                    "obs": observacao,
                    "usuario": st.session_state["usuario"]["id"],
                },
            ).scalar()

            # 2. Inserção nas Contas a Pagar
            conn.execute(
                text(
                    """
                    INSERT INTO contas_pagar (filial_id, categoria_id, descricao, valor, saldo, vencimento, status, usuario_id)
                    VALUES (:filial, :categoria, :descricao, :valor, :saldo, :vencimento, :status, :usuario)
                """
                ),
                {
                    "filial": filial_id,
                    "categoria": categoria_id,
                    "descricao": descricao,
                    "valor": valor,
                    "saldo": 0.0 if status == "PAGO" else valor,
                    "vencimento": vencimento,
                    "status": status,
                    "usuario": st.session_state["usuario"]["id"],
                },
            )

            # 3. Fluxo de Caixa Imediato (Se pago à vista)
            if status == "PAGO":
                conn.execute(
                    text(
                        """
                        INSERT INTO movimentacao_financeira (filial_id, tipo, origem, descricao, entrada, saida, saldo, data_movimento, usuario_id)
                        VALUES (:filial, 'SAIDA', 'DESPESA', :descricao, 0, :valor, 0, CURRENT_TIMESTAMP, :usuario)
                    """
                    ),
                    {
                        "filial": filial_id,
                        "descricao": descricao,
                        "valor": valor,
                        "usuario": st.session_state["usuario"]["id"],
                    },
                )

                # Dedução do Saldo do Caixa Operacional Ativo
                conn.execute(
                    text(
                        """
                        UPDATE caixa 
                        SET saldo_disponivel = saldo_disponivel - :valor 
                        WHERE filial_id = :filial AND fechado_em IS NULL
                    """
                    ),
                    {"valor": valor, "filial": filial_id},
                )

        st.success(f"Lançamento Financeiro #{despesa_id} homologado com sucesso.")
        st.rerun()

# =====================================
# TAB 2: AUDITORIA E HISTÓRICO
# =====================================
with tab_historico:
    st.subheader("Auditoria de Despesas Recentes")
    
    with engine.connect() as conn:
        historico = pd.read_sql(
            text(
                """
                SELECT
                    d.id AS "Cód. Registro",
                    c.descricao AS "Categoria",
                    d.descricao AS "Descrição da Despesa",
                    d.fornecedor AS "Fornecedor/Credor",
                    d.valor AS "Montante Líquido",
                    d.data_despesa AS "Data Competência"
                FROM despesas d
                LEFT JOIN categorias_financeiras c ON c.id = d.categoria_id
                WHERE d.filial_id = :filial
                ORDER BY d.id DESC
            """
            ),
            conn,
            params={"filial": filial_id},
        )

    if historico.empty:
        st.info("Nenhuma despesa ou saída mercantil localizada para os parâmetros da filial atual.")
    else:
        st.dataframe(
            historico,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Montante Líquido": st.column_config.NumberColumn(format="R$ %.2f"),
                "Data Competência": st.column_config.DateColumn(format="DD/MM/YYYY"),
            },
        )