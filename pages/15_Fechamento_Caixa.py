from datetime import date
from database import engine
from menu import render_menu
import pandas as pd
from services.financeiro import registrar_movimentacao
from sqlalchemy import text
import streamlit as st

# =====================================
# 1. CONFIGURAÇÃO DA PÁGINA (Primeiro comando)
# =====================================
st.set_page_config(
    page_title="Fechamento de Caixa", page_icon="🔒", layout="wide"
)


def carregar_css():
    with open("assets/style.css", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


carregar_css()

# =====================================
# 2. SEGURANÇA E GOVERNANÇA DE ACESSO
# =====================================
if "usuario" not in st.session_state:
    st.switch_page("pages/00_Login.py")
    st.stop()

if st.session_state["usuario"]["perfil"] != "ADMIN":
    st.error("Acesso restrito. Esta rotina requer privilégios de Administrador.")
    st.stop()

render_menu()

filial_id = st.session_state.get("filial_operacao")
if filial_id is None:
    st.error("Selecione uma filial ativa no menu lateral para prosseguir.")
    st.stop()

# =====================================
# 3. INTERFACE E PROCESSAMENTO FINANCEIRO
# =====================================
with engine.connect() as conn:
    filial_nome = conn.execute(
        text("SELECT nome FROM filiais WHERE id = :id"), {"id": filial_id}
    ).scalar()

st.title("🔒 Fechamento e Conciliação de Caixa")
st.caption(f"Unidade Controlada: **{filial_nome}** (ID: {filial_id})")
st.write(" ")

tab_fechamento, tab_historico = st.tabs(
    ["🔒 Encerrar Período Atual", "📋 Histórico de Fechamentos"]
)

# =====================================
# TAB 1: OPERAÇÃO DE FECHAMENTO
# =====================================
with tab_fechamento:
    col_data, _ = st.columns([3, 7])
    with col_data:
        data_fechamento = st.date_input("Data de Referência", value=date.today())

    # Coleta de métricas e prevenção de incompatibilidade de tipos (Decimal para float)
    with engine.connect() as conn:
        res_inicial = conn.execute(
            text(
                "SELECT COALESCE(SUM(saldo_inicial), 0) FROM caixa WHERE filial_id = :filial_id AND data_caixa::date = :data"
            ),
            {"filial_id": filial_id, "data": data_fechamento},
        ).scalar()
        saldo_inicial = float(res_inicial)

        res_compras = conn.execute(
            text(
                "SELECT COALESCE(SUM(valor_total), 0) FROM compras WHERE filial_id = :filial_id AND data_compra::date = :data"
            ),
            {"filial_id": filial_id, "data": data_fechamento},
        ).scalar()
        total_compras = float(res_compras)

        res_vendas = conn.execute(
            text(
                "SELECT COALESCE(SUM(valor_total), 0) FROM vendas WHERE filial_id = :filial_id AND data_venda::date = :data"
            ),
            {"filial_id": filial_id, "data": data_fechamento},
        ).scalar()
        total_vendas = float(res_vendas)

        res_reforcos = conn.execute(
            text(
                "SELECT COALESCE(SUM(entrada), 0) FROM movimentacao_financeira WHERE filial_id = :filial AND origem = 'REFORCO_CAIXA' AND data_movimento::date = :data"
            ),
            {"filial": filial_id, "data": data_fechamento},
        ).scalar()
        total_reforcos = float(res_reforcos)

        res_disponivel = conn.execute(
            text(
                "SELECT saldo_disponivel FROM caixa WHERE filial_id = :filial AND fechado_em IS NULL"
            ),
            {"filial": filial_id},
        ).scalar()
        saldo_disponivel = float(res_disponivel) if res_disponivel else 0.0

        saldo_final = saldo_disponivel

    # Validação de consistência do período operacional
    if saldo_inicial <= 0:
        st.warning("Aviso de Auditoria: Não foi identificado registro de abertura de caixa para esta data.")
    else:
        # Cockpit Gerencial de Conferência de Valores
        with st.container(border=True):
            st.subheader("Balancete Operacional Diário")
            st.write(" ")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("💵 Abertura (Fundo de Reserva)", f"R$ {saldo_inicial:,.2f}")
            c2.metric("🛒 Total Compras (Saídas)", f"R$ {total_compras:,.2f}")
            c3.metric("💰 Total Vendas (Entradas)", f"R$ {total_vendas:,.2f}")
            c4.metric("📈 Saldo de Fechamento (Disponível)", f"R$ {saldo_final:,.2f}")

        st.write(" ")
        observacao = st.text_area("Notas e Justificativas de Caixa (Opcional)", placeholder="Informe eventuais quebras de caixa, sangrias especiais ou justificativas...")
        
        if st.button("🔒 Homologar Fechamento de Caixa", use_container_width=True):
            with engine.begin() as conn:
                # Evita duplicidade de encerramento no mesmo dia
                existe = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM fechamento_caixa WHERE filial_id = :filial_id AND data_fechamento = :data"
                    ),
                    {"filial_id": filial_id, "data": data_fechamento},
                ).scalar()

                if existe > 0:
                    st.error("Conflito de Operação: Já consta no sistema um fechamento ativo para esta data.")
                    st.stop()

                # 1. Registra o Fechamento Principal
                fechamento_id = conn.execute(
                    text(
                        """
                        INSERT INTO fechamento_caixa (filial_id, usuario_id, data_fechamento, saldo_inicial, total_compras, total_vendas, saldo_final, total_reforcos, saldo_disponivel, observacao)
                        VALUES (:filial_id, :usuario_id, :data_fechamento, :saldo_inicial, :total_compras, :total_vendas, :saldo_final, :total_reforcos, :saldo_disponivel, :observacao)
                        RETURNING id
                    """
                    ),
                    {
                        "filial_id": filial_id,
                        "usuario_id": st.session_state["usuario"]["id"],
                        "data_fechamento": data_fechamento,
                        "saldo_inicial": saldo_inicial,
                        "total_compras": total_compras,
                        "total_vendas": total_vendas,
                        "saldo_final": saldo_final,
                        "total_reforcos": total_reforcos,
                        "saldo_disponivel": saldo_disponivel,
                        "observacao": observacao,
                    },
                ).scalar()

                # 2. Insere Trilha de Auditoria Geral
                conn.execute(
                    text(
                        """
                        INSERT INTO auditoria (usuario_id, acao, tabela, registro_id)
                        VALUES (:usuario_id, :acao, 'fechamento_caixa', :registro_id)
                    """
                    ),
                    {
                        "usuario_id": st.session_state["usuario"]["id"],
                        "acao": f"Fechamento homologado da filial {filial_id} referente ao dia {data_fechamento}",
                        "registro_id": int(fechamento_id),
                    },
                )

                # 3. Associa os Itens Movimentados do Dia ao Fechamento
                conn.execute(
                    text(
                        """
                        INSERT INTO fechamento_caixa_itens (fechamento_id, movimentacao_id)
                        SELECT :fechamento_id, id FROM movimentacao_financeira
                        WHERE filial_id = :filial AND data_movimento::date = :data
                    """
                    ),
                    {"fechamento_id": fechamento_id, "filial": filial_id, "data": data_fechamento},
                )

                # 4. Atualiza e Trava o Caixa Operacional Anterior
                conn.execute(
                    text(
                        """
                        UPDATE caixa SET saldo_disponivel = :saldo, fechado_em = CURRENT_TIMESTAMP
                        WHERE filial_id = :filial AND fechado_em IS NULL
                    """
                    ),
                    {"saldo": saldo_final, "filial": filial_id},
                )

                # 5. Registra o Evento Contábil de Fechamento via Serviço Dedicado
                registrar_movimentacao(
                    conn=conn,
                    filial_id=filial_id,
                    usuario_id=st.session_state["usuario"]["id"],
                    origem="FECHAMENTO_CAIXA",
                    referencia_id=int(fechamento_id),
                    tipo="SAIDA",
                    descricao=f"Fechamento de Caixa Ref: {data_fechamento}",
                    valor=0.0,
                )

            st.success("Período contábil encerrado e movimentações auditadas com sucesso.")
            st.rerun()

# =====================================
# TAB 2: AUDITORIA E HISTÓRICO DE FECHAMENTOS
# =====================================
with tab_historico:
    st.subheader("Livro Diário de Encerramentos")
    with engine.connect() as conn:
        historico = pd.read_sql(
            text(
                """
                SELECT
                    f.data_fechamento AS "Data Competência",
                    fi.nome AS "Filial/Unidade",
                    f.saldo_inicial AS "Abertura (R$)",
                    f.total_reforcos AS "Aportes/Reforços (R$)",
                    f.total_compras AS "Compras (R$)",
                    f.total_vendas AS "Vendas (R$)",
                    f.saldo_final AS "Saldo Final (R$)",
                    u.nome AS "Homologado Por"
                FROM fechamento_caixa f
                INNER JOIN filiais fi ON f.filial_id = fi.id
                LEFT JOIN usuarios u ON f.usuario_id = u.id
                WHERE f.filial_id = :filial
                ORDER BY f.data_fechamento DESC
            """
            ),
            conn,
            params={"filial": filial_id},
        )

    if historico.empty:
        st.info("Nenhum histórico de encerramento localizado para esta unidade gestora.")
    else:
        st.dataframe(
            historico,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Abertura (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Aportes/Reforços (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Compras (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Vendas (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Saldo Final (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Data Competência": st.column_config.DateColumn(format="DD/MM/YYYY"),
            },
        )