from datetime import date

import pandas as pd
from sqlalchemy import text

from database import engine


# ==========================================================
# CONTAS A PAGAR
# ==========================================================

def criar_conta_pagar(
    filial_id: int,
    fornecedor_id: int,
    categoria_id: int,
    compra_id: int,
    descricao: str,
    valor: float,
    vencimento,
    observacao: str,
    usuario_id: int,
    conn=None
):
    
    def executar(conexao):

        conexao.execute(
            text("""
                INSERT INTO contas_pagar
                (
                    filial_id,
                    fornecedor_id,
                    categoria_id,
                    compra_id,
                    descricao,
                    valor,
                    saldo,
                    valor_pago,
                    vencimento,
                    status,
                    observacao,
                    usuario_id
                )
                VALUES
                (
                    :filial_id,
                    :fornecedor_id,
                    :categoria_id,
                    :compra_id,
                    :descricao,
                    :valor,
                    :saldo,
                    0,
                    :vencimento,
                    'ABERTO',
                    :observacao,
                    :usuario_id
                )
            """),
            {
                "filial_id": filial_id,
                "fornecedor_id": fornecedor_id,
                "categoria_id": categoria_id,
                "compra_id": compra_id,
                "descricao": descricao,
                "valor": valor,
                "saldo": valor,
                "vencimento": vencimento,
                "observacao": observacao,
                "usuario_id": usuario_id
            }
        )


    if conn is None:

        with engine.begin() as conn_local:
            executar(conn_local)

    else:

        executar(conn)

#---------------------------------------------------------------------


# ==========================================================
# CONTAS A RECEBER
# ==========================================================

def criar_conta_receber(
    filial_id: int,
    industria_id: int,
    categoria_id: int,
    venda_id: int,
    descricao: str,
    valor: float,
    vencimento,
    observacao: str,
    usuario_id: int,
    conn=None
):

    def executar(conexao):

        conexao.execute(
            text("""
                INSERT INTO contas_receber
                (
                    filial_id,
                    industria_id,
                    categoria_id,
                    venda_id,
                    descricao,
                    valor,
                    saldo,
                    valor_pago,
                    vencimento,
                    status,
                    observacao,
                    usuario_id
                )
                VALUES
                (
                    :filial_id,
                    :industria_id,
                    :categoria_id,
                    :venda_id,
                    :descricao,
                    :valor,
                    :saldo,
                    0,
                    :vencimento,
                    'ABERTO',
                    :observacao,
                    :usuario_id
                )
            """),
            {
                "filial_id": filial_id,
                "industria_id": industria_id,
                "categoria_id": categoria_id,
                "venda_id": venda_id,
                "descricao": descricao,
                "valor": valor,
                "saldo": valor,
                "vencimento": vencimento,
                "observacao": observacao,
                "usuario_id": usuario_id
            }
        )

    # ESTE BLOCO TEM QUE FICAR FORA DA FUNÇÃO executar()

    if conn is None:

        with engine.begin() as conn_local:
            executar(conn_local)

    else:

        executar(conn)


# ==========================================================
# LISTAGENS
# ==========================================================

def listar_contas_pagar(
    filial_id=None,
    status=None
):

    sql = """
        SELECT *
        FROM contas_pagar
        WHERE 1=1
    """

    parametros = {}

    if filial_id:

        sql += " AND filial_id = :filial_id"

        parametros["filial_id"] = filial_id

    if status:

        sql += " AND status = :status"

        parametros["status"] = status

    sql += " ORDER BY vencimento"

    with engine.connect() as conn:

        return pd.read_sql(
            text(sql),
            conn,
            params=parametros
        )


def listar_contas_receber(
    filial_id=None,
    status=None
):

    sql = """
        SELECT *
        FROM contas_receber
        WHERE 1=1
    """

    parametros = {}

    if filial_id:

        sql += " AND filial_id = :filial_id"

        parametros["filial_id"] = filial_id

    if status:

        sql += " AND status = :status"

        parametros["status"] = status

    sql += " ORDER BY vencimento"

    with engine.connect() as conn:

        return pd.read_sql(
            text(sql),
            conn,
            params=parametros
        )


# ==========================================================
# KPIs CONTAS A PAGAR
# ==========================================================

def total_pagar_aberto():

    with engine.connect() as conn:

        return conn.execute(
            text("""
                SELECT
                    COALESCE(
                        SUM(saldo),
                        0
                    )
                FROM contas_pagar
                WHERE status <> 'PAGO'
            """)
        ).scalar()


def contas_em_atraso():

    with engine.connect() as conn:

        return conn.execute(
            text("""
                SELECT
                    COUNT(*)
                FROM contas_pagar
                WHERE
                    vencimento < CURRENT_DATE
                AND status <> 'PAGO'
            """)
        ).scalar()


def contas_vencendo_hoje():

    with engine.connect() as conn:

        return conn.execute(
            text("""
                SELECT
                    COUNT(*)
                FROM contas_pagar
                WHERE
                    vencimento = CURRENT_DATE
                AND status <> 'PAGO'
            """)
        ).scalar()


# ==========================================================
# KPIs CONTAS A RECEBER
# ==========================================================

def total_receber_aberto():

    with engine.connect() as conn:

        return conn.execute(
            text("""
                SELECT
                    COALESCE(
                        SUM(saldo),
                        0
                    )
                FROM contas_receber
                WHERE status <> 'RECEBIDO'
            """)
        ).scalar()


# ==========================================================
# MOVIMENTAÇÃO FINANCEIRA
# ==========================================================

def registrar_movimentacao(
    filial_id,
    categoria_id,
    forma_pagamento_id,
    conta_pagar_id,
    conta_receber_id,
    tipo,
    descricao,
    valor,
    usuario_id,
    conn=None
):

    def executar(conexao):

        conexao.execute(
            text("""
                INSERT INTO movimentacao_financeira
                (
                    filial_id,
                    categoria_id,
                    forma_pagamento_id,
                    conta_pagar_id,
                    conta_receber_id,
                    tipo,
                    descricao,
                    valor,
                    data_movimento,
                    usuario_id
                )
                VALUES
                (
                    :filial_id,
                    :categoria_id,
                    :forma_pagamento_id,
                    :conta_pagar_id,
                    :conta_receber_id,
                    :tipo,
                    :descricao,
                    :valor,
                    CURRENT_DATE,
                    :usuario_id
                )
            """),
            {
                "filial_id": filial_id,
                "categoria_id": categoria_id,
                "forma_pagamento_id": forma_pagamento_id,
                "conta_pagar_id": conta_pagar_id,
                "conta_receber_id": conta_receber_id,
                "tipo": tipo,
                "descricao": descricao,
                "valor": valor,
                "usuario_id": usuario_id
            }
        )
    if conn is None:

        with engine.begin() as conn_local:
            executar(conn_local)

    else:

        executar(conn)

# ==========================================================
# CONSULTAS INDIVIDUAIS
# ==========================================================

def obter_conta_pagar(conta_id):

    with engine.connect() as conn:

        return conn.execute(
            text("""
                SELECT *
                FROM contas_pagar
                WHERE id = :id
            """),
            {
                "id": conta_id
            }
        ).mappings().first()


def obter_conta_receber(conta_id):

    with engine.connect() as conn:

        return conn.execute(
            text("""
                SELECT *
                FROM contas_receber
                WHERE id = :id
            """),
            {
                "id": conta_id
            }
        ).mappings().first()
    

