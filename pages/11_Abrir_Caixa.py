from datetime import date
from database import engine
from menu import render_menu
import pandas as pd
from services.financeiro import registrar_movimentacao
from sqlalchemy import text
import streamlit as st

# =====================================
# 1. CONFIGURAÇÃO DA PÁGINA
# =====================================
st.set_page_config(page_title="Abrir Caixa", page_icon="💵", layout="wide")


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
    st.error("Selecione uma filial ativa no menu lateral para iniciar.")
    st.stop()

# Auto-fechamento preventivo de caixas retroativos
with engine.begin() as conn:
    conn.execute(
        text(
            """
            UPDATE caixa 
            SET fechado_em = CURRENT_TIMESTAMP 
            WHERE filial_id = :filial_id 
              AND data_caixa < CURRENT_DATE 
              AND fechado_em IS NULL
        """
        ),
        {"filial_id": filial_id},
    )

# Busca metadados e estado atual do caixa para o dia corrente
hoje = date.today()
with engine.connect() as conn:
    filial_nome = conn.execute(
        text("SELECT nome FROM filiais WHERE id = :id"), {"id": filial_id}
    ).scalar()

    caixa_aberto = conn.execute(
        text(
            """
            SELECT id, saldo_inicial, saldo_disponivel, observacao 
            FROM caixa 
            WHERE filial_id = :filial_id 
              AND fechado_em IS NULL 
              AND data_caixa = :data 
            LIMIT 1
        """
        ),
        {"filial_id": filial_id, "data": hoje},
    ).fetchone()

    # Coleta de reforços do dia corrente
    res_reforcos = conn.execute(
        text(
            """
            SELECT COALESCE(SUM(entrada), 0) 
            FROM movimentacao_financeira 
            WHERE filial_id = :filial 
              AND origem = 'REFORCO_CAIXA' 
              AND data_movimento::date = CURRENT_DATE
        """
        ),
        {"filial": filial_id},
    ).scalar()

# Definição segura de saldos estruturais
saldo_inicial = float(caixa_aberto.saldo_inicial) if caixa_aberto else 0.0
saldo_disponivel = float(caixa_aberto.saldo_disponivel) if caixa_aberto else 0.0
total_reforcos = float(res_reforcos) if res_reforcos else 0.0

# =====================================
# 3. INTERFACE EXECUTIVA
# =====================================
st.title(f"📦 Gestão de Caixa — {filial_nome}")
st.caption(f"Status Operacional da Unidade (ID: {filial_id}) em {hoje.strftime('%d/%m/%Y')}")
st.write(" ")

# Alertas de Status Centralizados
if caixa_aberto:
    st.success("💼 Competência do dia ativa: O caixa desta filial encontra-se aberto e apto a transacionar.")
else:
    st.warning("⚠️ Atenção: Nenhum caixa ativo localizado para o dia de hoje. É necessário realizar a abertura antes de operar.")

# Divisão das ferramentas por abas funcionais
tab_operacao, tab_reabertura, tab_historico = st.tabs(
    ["🔓 Abertura & Reforços", "🛠️ Reabertura de Caixa", "📋 Histórico de Movimentações"]
)

# =====================================
# TAB 1: ABERTURA E REFORÇO
# =====================================
with tab_operacao:
    if not caixa_aberto:
        # SE O CAIXA NÃO ESTIVER ABERTO: Exibe exclusivamente o formulário de abertura de fato
        st.subheader("Formulário de Abertura Contábil")
        with st.form("form_caixa_abertura", clear_on_submit=True):
            saldo_input = st.number_input(
                "Fundo de Reserva / Saldo Inicial em Dinheiro (R$)", min_value=0.0, step=10.0, format="%.2f"
            )
            obs_input = st.text_area("Observações / Notas de Abertura", placeholder="Ex: Entrada de troco padrão em moedas e cédulas...")
            
            if st.form_submit_button("🔓 Homologar e Abrir Caixa", use_container_width=True):
                with engine.begin() as conn:
                    # Cria o registro na tabela de caixas
                    conn.execute(
                        text(
                            """
                            INSERT INTO caixa (data_caixa, saldo_inicial, saldo_disponivel, observacao, criado_em, filial_id, fechado_em)
                            VALUES (CURRENT_DATE, :saldo_inicial, :saldo_inicial, :observacao, CURRENT_TIMESTAMP, :filial_id, NULL)
                        """
                        ),
                        {"saldo_inicial": saldo_input, "observacao": obs_input, "filial_id": filial_id},
                    )
                    # Registra o fluxo de entrada contábil correspondente
                    registrar_movimentacao(
                        conn=conn,
                        filial_id=filial_id,
                        usuario_id=st.session_state["usuario"]["id"],
                        origem="ABERTURA_CAIXA",
                        referencia_id=None,
                        tipo="ENTRADA",
                        descricao="Abertura de Caixa Regular",
                        valor=saldo_input,
                    )
                st.success("Caixa inicializado e liberado para operações.")
                st.rerun()
    else:
        # SE O CAIXA JÁ ESTIVER ABERTO: Exibe o Balanço e o formulário de Suprimento/Reforço
        col_painel, col_acoes = st.columns([6, 4])

        with col_painel:
            with st.container(border=True):
                st.subheader("Cockpit de Saldos do Dia")
                st.write(" ")
                c1, c2, c3 = st.columns(3)
                c1.metric("💵 Fundo de Abertura", f"R$ {saldo_inicial:,.2f}")
                c2.metric("➕ Aportes / Reforços", f"R$ {total_reforcos:,.2f}")
                c3.metric(
                    "🏦 Saldo Atual Disponível",
                    f"R$ {saldo_disponivel:,.2f}",
                    help="Saldo em tempo real atualizado com base no fluxo de caixa computado.",
                )

        with col_acoes:
            with st.container(border=True):
                st.subheader("Injetar Reforço (Suprimento)")
                valor_reforco = st.number_input("Valor do Aporte (R$)", min_value=0.0, step=50.0, format="%.2f")
                motivo = st.text_input("Motivo / Justificativa", placeholder="Ex: Necessidade de troco para o PDV")

                if st.button("➕ Confirmar Entrada de Reforço", use_container_width=True):
                    if valor_reforco <= 0:
                        st.error("Operação cancelada: Insira um valor estritamente positivo.")
                        st.stop()

                    with engine.begin() as conn:
                        registrar_movimentacao(
                            conn=conn,
                            filial_id=filial_id,
                            usuario_id=st.session_state["usuario"]["id"],
                            origem="REFORCO_CAIXA",
                            referencia_id=None,
                            tipo="ENTRADA",
                            descricao=motivo or "Reforço de Caixa",
                            valor=valor_reforco,
                        )
                        conn.execute(
                            text(
                                """
                                UPDATE caixa 
                                SET saldo_disponivel = saldo_disponivel + :valor 
                                WHERE filial_id = :filial AND fechado_em IS NULL
                            """
                            ),
                            {"valor": valor_reforco, "filial": filial_id},
                        )
                        conn.execute(
                            text(
                                """
                                INSERT INTO auditoria (usuario_id, acao, tabela, registro_id)
                                VALUES (:usuario, :acao, 'movimentacao_financeira', 0)
                            """
                            ),
                            {
                                "usuario": st.session_state["usuario"]["id"],
                                "acao": f"Suprimento de caixa efetuado no valor de R$ {valor_reforco:.2f}",
                            },
                        )
                    st.success("Aporte financeiro processado com sucesso.")
                    st.rerun()

# =====================================
# TAB 2: REABERTURA DE CAIXA
# =====================================
with tab_reabertura:
    st.subheader("Estorno de Fechamento Contábil")
    st.caption("Esta operação reativa um dia fiscal previamente encerrado. Use com extrema cautela.")
    st.write(" ")

    data_reabertura = st.date_input("Selecione o Dia para Reabertura", value=hoje, key="reabrir_data_key")

    with engine.connect() as conn:
        existe_fechamento = conn.execute(
            text(
                "SELECT COUNT(*) FROM fechamento_caixa WHERE filial_id = :filial_id AND data_fechamento = :data"
            ),
            {"filial_id": filial_id, "data": data_reabertura},
        ).scalar()

    if existe_fechamento > 0:
        with st.container(border=True):
            st.warning(f"Atenção: Constatamos um fechamento consolidado ativo para o dia {data_reabertura.strftime('%d/%m/%Y')}.")
            
            confirmar = st.checkbox(
                "Confirmo que desejo remover os relatórios consolidados e impactar os trancamentos de auditoria desta data.",
                key="chk_auditoria_seguranca"
            )
            
            if confirmar:
                if st.button("🔓 Proceder com a Reabertura do Caixa", type="primary", use_container_width=True):
                    with engine.begin() as conn:
                        # 1. Primeiro, descobrimos o ID real do fechamento para limpar a tabela filha
                        id_fechamento = conn.execute(
                            text("""
                                SELECT id FROM fechamento_caixa 
                                WHERE filial_id = :filial_id AND data_fechamento = :data
                            """),
                            {"filial_id": filial_id, "data": data_reabertura}
                        ).scalar()

                        if id_fechamento:
                            # 2. Apagamos os itens vinculados na tabela filha para liberar a Foreign Key
                            conn.execute(
                                text("DELETE FROM fechamento_caixa_itens WHERE fechamento_id = :fechamento_id"),
                                {"fechamento_id": int(id_fechamento)}
                            )

                        # 3. Agora sim, apagamos o registro pai com segurança sem violar constraints
                        conn.execute(
                            text("""
                                DELETE FROM fechamento_caixa 
                                WHERE filial_id = :filial_id AND data_fechamento = :data
                            """),
                            {"filial_id": filial_id, "data": data_reabertura},
                        )
                        
                        # 4. Escreve o log na trilha de auditoria corporativa
                        conn.execute(
                            text("""
                                INSERT INTO auditoria (usuario_id, acao, tabela, registro_id)
                                VALUES (:usuario_id, :acao, 'fechamento_caixa', 0)
                            """),
                            {
                                "usuario_id": st.session_state["usuario"]["id"],
                                "acao": f"Reabertura forçada de caixa efetuada. Unidade: {filial_id} Competência: {data_reabertura}",
                            },
                        )
                        
                        # 5. Libera o caixa diário alterando o trancamento temporal para NULL
                        conn.execute(
                            text("""
                                UPDATE caixa SET fechado_em = NULL 
                                WHERE filial_id = :filial_id AND data_caixa = :data
                            """),
                            {"filial_id": filial_id, "data": data_reabertura},
                        )
                        
                    st.success("O período contábil foi restabelecido e liberado com sucesso.")
                    st.rerun()
    else:
        st.info("Nenhum fechamento contábil rígido localizado para o dia selecionado.")

# =====================================
# TAB 3: HISTÓRICO GERENCIAL
# =====================================
with tab_historico:
    st.subheader("Livro Registro de Aberturas e Alocações")
    
    query_historico = """
        SELECT 
            c.data_caixa AS "Data de Execução",
            c.saldo_inicial AS "Fundo Inicial (R$)",
            COALESCE(r.reforcos, 0) AS "Aportes/Reforços (R$)",
            (c.saldo_inicial + COALESCE(r.reforcos, 0)) AS "Total Alocado (R$)",
            CASE WHEN c.fechado_em IS NULL THEN 'ABERTO' ELSE 'FECHADO' END AS "Status do Caixa",
            c.criado_em AS "Data/Hora Criação"
        FROM caixa c
        LEFT JOIN (
            SELECT filial_id, data_movimento::date as dt, SUM(entrada) as reforcos
            FROM movimentacao_financeira
            WHERE origem = 'REFORCO_CAIXA'
            GROUP BY filial_id, data_movimento::date
        ) r ON c.filial_id = r.filial_id AND c.data_caixa = r.dt
        WHERE c.filial_id = :filial
        ORDER BY c.data_caixa DESC
    """
    
    with engine.connect() as conn:
        historico = pd.read_sql(text(query_historico), conn, params={"filial": filial_id})

    if historico.empty:
        st.info("Nenhum histórico operacional computado para esta filial até o momento.")
    else:
        st.dataframe(
            historico,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Fundo Inicial (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Aportes/Reforços (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Total Alocado (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
                "Data de Execução": st.column_config.DateColumn(format="DD/MM/YYYY"),
                "Data/Hora Criação": st.column_config.DateColumn(format="DD/MM/YYYY HH:mm"),
            },
        )