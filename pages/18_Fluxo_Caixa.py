from datetime import date, timedelta
from database import engine
from menu import render_menu
import pandas as pd
from sqlalchemy import text
import streamlit as st

# =====================================
# 1. CONFIGURAÇÃO DA PÁGINA (Sempre no início)
# =====================================
st.set_page_config(
    page_title="Fluxo de Caixa", page_icon="💵", layout="wide"
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
    st.error("Selecione uma filial ativa no menu lateral para carregar a Tesouraria.")
    st.stop()

# Busca metadados da filial selecionada
with engine.connect() as conn:
    filial_nome = conn.execute(
        text("SELECT nome FROM filiais WHERE id = :id"), {"id": filial_id}
    ).scalar()

# =====================================
# 3. CABEÇALHO E FILTROS TEMPORAIS
# =====================================
st.title("💵 Fluxo de Caixa Consolidado")
st.caption(f"Unidade Gestora: **{filial_nome}** (ID: {filial_id})")

hoje = date.today()
with st.container(border=True):
    col_ini, col_fim = st.columns(2)
    with col_ini:
        data_inicio = st.date_input("Data Inicial", hoje - timedelta(days=30))
    with col_fim:
        data_fim = st.date_input("Data Final", hoje)

# =====================================
# 4. EXTRATOS E PROCESSAMENTO FINANCEIRO
# =====================================
sql_movimentacoes = """
SELECT
    data_movimento AS "Data/Hora",
    tipo AS "Operação",
    origem AS "Origem",
    descricao AS "Descrição do Evento",
    entrada AS "Entrada (R$)",
    saida AS "Saída (R$)",
    saldo AS "Saldo Linha"
FROM movimentacao_financeira
WHERE filial_id = :filial AND data_movimento::date BETWEEN :inicio AND :fim
ORDER BY data_movimento
"""

sql_saldo_anterior = """
SELECT COALESCE(SUM(entrada) - SUM(saida), 0)
FROM movimentacao_financeira
WHERE filial_id = :filial AND data_movimento::date < :inicio
"""

with engine.connect() as conn:
    # Captura a movimentação do período
    df = pd.read_sql(
        text(sql_movimentacoes),
        conn,
        params={"filial": filial_id, "inicio": data_inicio, "fim": data_fim},
    )
    # Captura o saldo histórico prévio para ajuste de linha de tendência real
    # Captura o saldo histórico prévio e converte explicitamente para float
    res_saldo = conn.execute(
        text(sql_saldo_anterior), {"filial": filial_id, "inicio": data_inicio}
    ).scalar()
    saldo_anterior = float(res_saldo) if res_saldo is not None else 0.0

# Agregações financeiras do período
entradas = df["Entrada (R$)"].sum() if not df.empty else 0.0
saidas = df["Saída (R$)"].sum() if not df.empty else 0.0
saldo_periodo = entradas - saidas

# =====================================
# 5. COCKPIT DE MÉTRICAS (KPIs)
# =====================================
st.write(" ")
c1, c2, c3 = st.columns(3)
c1.metric("⬆️ Total Entradas (Aportes/Vendas)", f"R$ {entradas:,.2f}")
c2.metric("⬇️ Total Saídas (Custo/Despesas)", f"R$ {saidas:,.2f}")
c3.metric(
    "💰 Saldo Líquido do Período",
    f"R$ {saldo_periodo:,.2f}",
    delta=f"Saldo Geral Atual: R$ {(saldo_anterior + saldo_periodo):,.2f}",
    help="O valor menor (delta) representa o saldo histórico da filial somado ao resultado do período selecionado.",
)

st.write("---")

if df.empty:
    st.info("Nenhum fluxo de caixa ou movimentação bancária registrada neste intervalo de datas.")
else:
    # Split executivo: Tabela detalhada à esquerda e Insights gráficos à direita
    col_tabela, col_grafico = st.columns([6, 4])

    with col_tabela:
        with st.container(border=True):
            st.subheader("📋 Extrato Analítico de Lançamentos")
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Entrada (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Saída (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Saldo Linha": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Data/Hora": st.column_config.DateColumn(format="DD/MM/YYYY HH:mm"),
                },
            )

    with col_grafico:
        # Gráfico de Evolução Patrimonial do Caixa
        with st.container(border=True):
            st.subheader("📊 Linha de Tendência de Saldo")
            
            # Cálculo corretivo de liquidez acumulada considerando o saldo passado
            df["Liquidez Real Acumulada"] = saldo_anterior + (df["Entrada (R$)"] - df["Saída (R$)"]).cumsum()
            df_grafico = df.set_index("Data/Hora")[["Liquidez Real Acumulada"]]
            
            st.line_chart(df_grafico, y="Liquidez Real Acumulada", color="#10b981")

        # Tabela Auxiliar de Distribuição por Centro de Custo/Origem
        with st.container(border=True):
            st.subheader("🔀 Distribuição por Origem de Recursos")
            resumo = (
                df.groupby("Origem")[["Entrada (R$)", "Saída (R$)"]]
                .sum()
                .reset_index()
            )
            st.dataframe(
                resumo,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Entrada (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Saída (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                },
            )