from datetime import date, timedelta
from database import engine
from menu import render_menu
import pandas as pd
from sqlalchemy import text
import streamlit as st

# =====================================
# 1. CONFIGURAÇÃO DA PÁGINA & CSS (Sempre no topo)
# =====================================
st.set_page_config(
    page_title="Demonstrativo de Resultados", page_icon="📦", layout="wide"
)


def carregar_css():
    with open("assets/style.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


carregar_css()
render_menu()

# =====================================
# 2. SEGURANÇA E CONTEXTO DE CONEXÃO
# =====================================
if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()

if st.session_state["usuario"]["perfil"] != "ADMIN":
    st.error("Acesso restrito. Esta página requer privilégios de Administrador.")
    st.stop()

filial_id = st.session_state.get("filial_operacao")
if filial_id is None:
    st.error("Selecione uma filial ativa no menu lateral para carregar a DRE.")
    st.stop()

filial_id = int(filial_id)

with engine.connect() as conn:
    filial_nome = conn.execute(
        text("SELECT nome FROM filiais WHERE id = :id"), {"id": filial_id}
    ).scalar()

if filial_nome is None:
    st.error("A filial selecionada é inválida ou não foi localizada no sistema.")
    st.stop()

# =====================================
# 3. CABEÇALHO E FILTROS GERENCIAIS
# =====================================
st.title("📊 Demonstrativo de Resultados Exercício (DRE)")
st.caption(f"Unidade Controlada: **{filial_nome}** (ID: {filial_id})")

hoje = date.today()
with st.container(border=True):
    col_ini, col_fim = st.columns(2)
    with col_ini:
        data_inicio = st.date_input("Data Inicial do Período", hoje - timedelta(days=30))
    with col_fim:
        data_fim = st.date_input("Data Final do Período", hoje)

# =====================================
# 4. EXECUÇÃO DOS COCKPITS FINANCEIROS
# =====================================
with engine.connect() as conn:
    # Receita de Vendas
    receita_bruta = conn.execute(
        text(
            """
            SELECT COALESCE(SUM(valor_total), 0)
            FROM vendas
            WHERE filial_id = :filial_id AND data_venda::date BETWEEN :inicio AND :fim
        """
        ),
        {"inicio": data_inicio, "fim": data_fim, "filial_id": filial_id},
    ).scalar()

    # Custo de Aquisição (Compras)
    custo_aquisicao = conn.execute(
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

# Cálculos Estruturais
lucro_bruto = receita_bruta - custo_aquisicao
margem = (lucro_bruto / receita_bruta * 100) if receita_bruta > 0 else 0.0

# Painel Superior de Métricas
st.write(" ")
c1, c2, c3, c4 = st.columns(4)
c1.metric("💰 Receita Bruta (Faturamento)", f"R$ {receita_bruta:,.2f}")
c2.metric("🛒 Custo de Aquisição (CPV)", f"R$ {custo_aquisicao:,.2f}")
c3.metric("📈 Lucro Bruto Operacional", f"R$ {lucro_bruto:,.2f}")
c4.metric("🎯 Margem Bruta", f"{margem:.2f}%")

# =====================================
# 5. VISUALIZAÇÕES ANALÍTICAS (DRE & EVOLUÇÃO)
# =====================================
st.write("---")
sec_dre, sec_evolucao = st.columns([1, 1])

with sec_dre:
    with st.container(border=True):
        st.subheader("📋 Estrutura de Resultado")
        dre = pd.DataFrame(
            {
                "Conta Corrente": ["(+) Receita Operacional Bruta", "(-) Custo das Mercadorias Adquiridas", "(=) Lucro Bruto Comercial"],
                "Valor Planejado": [receita_bruta, custo_aquisicao, lucro_bruto],
            }
        )
        st.dataframe(
            dre,
            use_container_width=True,
            hide_index=True,
            column_config={"Valor Planejado": st.column_config.NumberColumn(format="R$ %.2f")},
        )

with sec_evolucao:
    with st.container(border=True):
        st.subheader("📈 Tendência de Faturamento Mensal")
        with engine.connect() as conn:
            vendas_mes = pd.read_sql(
                text(
                    """
                    SELECT DATE_TRUNC('month', data_venda) AS mes, SUM(valor_total) AS receita
                    FROM vendas
                    WHERE filial_id = :filial_id
                    GROUP BY mes ORDER BY mes
                """
                ),
                conn,
                params={"filial_id": filial_id},
            )
        if not vendas_mes.empty:
            vendas_mes["mes"] = pd.to_datetime(vendas_mes["mes"])
            st.line_chart(vendas_mes.set_index("mes"), y="receita", color="#0284c7", height=118)
        else:
            st.caption("Histórico de faturamento inexistente.")

# =====================================
# 6. PERFORMANCE POR CATEGORIA DE MATERIAL
# =====================================
st.write("---")
with st.container(border=True):
    st.subheader("🏆 Análise de Margem por Tipo de Material")
    
    # Query Inteligente unificada via FULL OUTER JOIN para evitar falhas de agregação de datas
    with engine.connect() as conn:
        df_materiais = pd.read_sql(
            text(
                """
                SELECT 
                    m.descricao AS "Material",
                    COALESCE(v.receita, 0) AS "Receita (R$)",
                    COALESCE(c.custo, 0) AS "Custo (R$)",
                    (COALESCE(v.receita, 0) - COALESCE(c.custo, 0)) AS "Resultado Líquido (R$)"
                FROM materiais m
                FULL OUTER JOIN (
                    SELECT material_id, SUM(valor_total) AS receita 
                    FROM vendas 
                    WHERE filial_id = :filial_id AND data_venda::date BETWEEN :inicio AND :fim
                    GROUP BY material_id
                ) v ON m.id = v.material_id
                FULL OUTER JOIN (
                    SELECT ic.material_id, SUM(ic.valor_total) AS custo 
                    FROM itens_compra ic
                    INNER JOIN compras cmp ON ic.compra_id = cmp.id
                    WHERE cmp.filial_id = :filial_id AND cmp.data_compra::date BETWEEN :inicio AND :fim
                    GROUP BY ic.material_id
                ) c ON m.id = c.material_id
                WHERE v.receita IS NOT NULL OR c.custo IS NOT NULL
                ORDER BY "Resultado Líquido (R$)" DESC
            """
            ),
            conn,
            params={"inicio": data_inicio, "fim": data_fim, "filial_id": filial_id},
        )

    if not df_materiais.empty:
        st.dataframe(
            df_materiais,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Receita (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Custo (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Resultado Líquido (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
            },
        )
    else:
        st.info("Nenhuma transação mercantil com materiais registrada neste intervalo de tempo.")

# =====================================
# 7. SUMÁRIO E PARECER DO DIRETOR
# =====================================
st.write("---")
st.subheader("📋 Sumário Executivo do Período")

if lucro_bruto > 0:
    st.markdown(
        f"""
        <div style="padding:15px; border-radius:8px; background-color:rgba(22,163,74,0.1); border-left:5px solid #16a34a;">
            <strong>🟢 Desempenho Superavitário:</strong> A operação apresentou um superávit comercial consolidado de 
            <strong>R$ {lucro_bruto:,.2f}</strong>, operando com uma eficiência de margem bruta de <strong>{margem:.2f}%</strong>. 
            O fluxo de entrada cobre integralmente o custo de reposição de estoque atual.
        </div>
        """,
        unsafe_allow_html=True,
    )
elif lucro_bruto < 0:
    st.markdown(
        f"""
        <div style="padding:15px; border-radius:8px; background-color:rgba(220,38,38,0.1); border-left:5px solid #dc2626;">
            <strong>🔴 Alerta de Déficit Operacional:</strong> Foi detectado um descompasso financeiro com prejuízo acumulado de 
            <strong>R$ {abs(lucro_bruto):,.2f}</strong> para as datas selecionadas. Recomenda-se avaliar imediatamente as tabelas de 
            preços de compra praticadas junto aos fornecedores ou a precificação de saída industrial.
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
        <div style="padding:15px; border-radius:8px; background-color:rgba(217,119,6,0.1); border-left:5px solid #d97706;">
            <strong>🟡 Posição Neutra / Inércia:</strong> Não houveram registros de entradas ou saídas financeiras na filial para as chaves temporais indicadas.
        </div>
        """,
        unsafe_allow_html=True,
    )