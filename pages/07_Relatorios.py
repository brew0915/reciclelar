from datetime import date, timedelta
from io import BytesIO
import pandas as pd
from sqlalchemy import text
import streamlit as st

from database import engine
from menu import render_menu

# =====================================
# 1. CONFIGURAÇÃO DA PÁGINA & CSS (Sempre no início)
# =====================================
st.set_page_config(page_title="Relatórios Executivos", page_icon="📑", layout="wide")


def carregar_css():
    with open("assets/style.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


carregar_css()
render_menu()

# =====================================
# 2. SEGURANÇA E CONTEXTO
# =====================================
if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()

filial_id = st.session_state.get("filial_operacao")
if filial_id is None:
    st.error("Selecione uma filial no menu lateral para gerar os relatórios.")
    st.stop()

# Busca nome da filial de forma limpa
with engine.connect() as conn:
    filial_nome = conn.execute(
        text("SELECT nome FROM filiais WHERE id = :id"), {"id": filial_id}
    ).scalar()

# =====================================
# 3. CABEÇALHO E FILTROS GERENCIAIS
# =====================================
st.title("📑 Central de Relatórios Analíticos")
st.caption(f"Unidade Operacional Auditada: **{filial_nome}**")

with st.container(border=True):
    col_tipo, col_ini, col_fim = st.columns([2, 1, 1])

    with col_tipo:
        tipo_relatorio = st.selectbox(
            "Módulo de Análise",
            ["Compras", "Vendas", "Estoque", "Resultado Financeiro"],
        )

    hoje = date.today()
    with col_ini:
        data_inicio = st.date_input("Data Inicial", hoje - timedelta(days=30))

    with col_fim:
        data_fim = st.date_input("Data Final", hoje)

# =====================================
# 4. PROCESSAMENTO DAS QUERIES (Sintaxe text() corrigida)
# =====================================
df = pd.DataFrame()  # Inicialização de segurança
config_colunas = {}  # Configuração visual dinâmica

with engine.connect() as conn:
    if tipo_relatorio == "Compras":
        df = pd.read_sql(
            text(
                """
                SELECT
                    c.id AS "Cód. Compra",
                    COALESCE(f.nome, c.fornecedor_avulso) AS "Fornecedor",
                    m.descricao AS "Material",
                    ic.quantidade AS "Qtd (KG)",
                    ic.valor_unitario AS "Preço Unitário",
                    ic.valor_total AS "Valor Total (R$)",
                    c.observacao AS "Observações",
                    c.data_compra AS "Data/Hora"
                FROM compras c
                LEFT JOIN fornecedores f ON f.id = c.fornecedor_id
                INNER JOIN itens_compra ic ON ic.compra_id = c.id
                INNER JOIN materiais m ON m.id = ic.material_id
                WHERE c.filial_id = :filial_id
                  AND c.data_compra::date BETWEEN :inicio AND :fim
                ORDER BY c.id DESC
            """
            ),
            conn,
            params={
                "inicio": data_inicio,
                "fim": data_fim,
                "filial_id": filial_id,
            },
        )
        config_colunas = {
            "Qtd (KG)": st.column_config.NumberColumn(format="%.3f KG"),
            "Preço Unitário": st.column_config.NumberColumn(format="R$ %.2f"),
            "Valor Total (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Data/Hora": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
        }

    elif tipo_relatorio == "Vendas":
        df = pd.read_sql(
            text(
                """
                SELECT
                    v.id AS "Cód. Venda",
                    i.nome AS "Indústria",
                    m.descricao AS "Material",
                    v.quantidade AS "Qtd (KG)",
                    v.valor_unitario AS "Preço Unitário",
                    v.valor_total AS "Faturamento (R$)",
                    v.data_venda AS "Data Emissão"
                FROM vendas v
                INNER JOIN industrias i ON v.industria_id = i.id
                INNER JOIN materiais m ON v.material_id = m.id
                WHERE v.filial_id = :filial_id
                  AND v.data_venda::date BETWEEN :inicio AND :fim
                ORDER BY v.data_venda DESC
            """
            ),
            conn,
            params={
                "inicio": data_inicio,
                "fim": data_fim,
                "filial_id": filial_id,
            },
        )
        config_colunas = {
            "Qtd (KG)": st.column_config.NumberColumn(format="%.3f KG"),
            "Preço Unitário": st.column_config.NumberColumn(format="R$ %.2f"),
            "Faturamento (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            "Data Emissão": st.column_config.DatetimeColumn(format="DD/MM/YYYY HH:mm"),
        }

    elif tipo_relatorio == "Estoque":
        df = pd.read_sql(
            text(
                """
                SELECT
                    m.descricao AS "Descrição do Material",
                    COALESCE(SUM(CASE WHEN e.tipo = 'ENTRADA' THEN e.quantidade ELSE -e.quantidade END), 0) AS "Saldo em Estoque (KG)"
                FROM materiais m
                LEFT JOIN estoque_movimentacao e ON m.id = e.material_id AND e.filial_id = :filial_id
                GROUP BY m.descricao
                ORDER BY m.descricao ASC
            """
            ),
            conn,
            params={"filial_id": filial_id},
        )
        config_colunas = {
            "Saldo em Estoque (KG)": st.column_config.NumberColumn(format="%.3f KG")
        }

    elif tipo_relatorio == "Resultado Financeiro":
        compras = conn.execute(
            text(
                """
                SELECT COALESCE(SUM(ic.valor_total), 0)
                FROM compras c
                INNER JOIN itens_compra ic ON ic.compra_id = c.id
                WHERE c.filial_id = :filial_id AND c.data_compra::date BETWEEN :inicio AND :fim
            """
            ),
            {"inicio": data_inicio, "fim": data_fim, "filial_id": filial_id},
        ).scalar()

        vendas = conn.execute(
            text(
                """
                SELECT COALESCE(SUM(valor_total), 0)
                FROM vendas
                WHERE filial_id = :filial_id AND data_venda::date BETWEEN :inicio AND :fim
            """
            ),
            {"inicio": data_inicio, "fim": data_fim, "filial_id": filial_id},
        ).scalar()

        lucro = vendas - compras
        df = pd.DataFrame(
            {
                "Indicador de Performance": ["(-) Custo Total de Compras", "(+) Faturamento de Vendas", "(=) Lucro Bruto Operacional"],
                "Montante Financeiro": [compras, vendas, lucro],
            }
        )
        config_colunas = {
            "Montante Financeiro": st.column_config.NumberColumn(format="R$ %.2f")
        }

# =====================================
# 5. RENDERIZAÇÃO E ENTREGA CORPORATIVA
# =====================================
st.write("---")

if df.empty or (tipo_relatorio != "Resultado Financeiro" and len(df) == 0):
    st.info("Nenhuma movimentação comercial registrada para os critérios selecionados.")
else:
    # Seção de Destaques Gerenciais (KPIs Rápidos) baseados nos DataFrames
    if tipo_relatorio in ["Compras", "Vendas"]:
        col_kpi1, col_kpi2 = st.columns(2)
        col_nome = "Valor Total (R$)" if tipo_relatorio == "Compras" else "Faturamento (R$)"
        qtd_nome = "Qtd (KG)"
        
        with col_kpi1:
            st.metric("Volume Total Movimentado", f"{df[qtd_nome].sum():,.2f} KG")
        with col_kpi2:
            st.metric("Impacto Financeiro Consolidado", f"R$ {df[col_nome].sum():,.2f}")
        st.write(" ")

    # Tabela Executiva Formatada
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config=config_colunas,
    )

    # Exportador em Memória para Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Data_Report", index=False)
    excel_data = output.getvalue()

    # Botão de Ação Alinhado à Direita usando colunas
    st.write(" ")
    _, col_btn = st.columns([3, 1])
    with col_btn:
        st.download_button(
            label="📥 Exportar Dados para Excel",
            data=excel_data,
            file_name=f"Relatorio_{tipo_relatorio}_{data_inicio}_{data_fim}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )