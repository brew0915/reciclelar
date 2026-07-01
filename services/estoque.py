from sqlalchemy import text
from pandas import read_sql
from database import engine
from services.auditoria import registrar_auditoria
from services.financeiro import registrar_movimentacao


# ==========================================================
# CONSULTAS
# ==========================================================

def obter_saldo(
    filial_id: int,
    material_id: int,
    conn=None
) -> float:
    """
    Retorna o saldo atual do material.
    """

    if conn is None:

        with engine.connect() as conn_local:

            saldo = conn_local.execute(
                text("""
                    SELECT quantidade
                    FROM estoque
                    WHERE filial_id = :filial
                    AND material_id = :material
                """),
                {
                    "filial": filial_id,
                    "material": material_id
                }
            ).scalar()

    else:

        saldo = conn.execute(
            text("""
                SELECT quantidade
                FROM estoque
                WHERE filial_id = :filial
                AND material_id = :material
            """),
            {
                "filial": filial_id,
                "material": material_id
            }
        ).scalar()

    return saldo or 0


# ==========================================================
# ENTRADA
# ==========================================================



def entrada_estoque(
    filial_id,
    material_id,
    quantidade,
    referencia_id,
    origem,
    conn
):

    conn.execute(
        text("""
            INSERT INTO estoque_movimentacao
            (
                filial_id,
                material_id,
                tipo,
                quantidade,
                origem,
                referencia_id,
                data_movimentacao
            )
            VALUES
            (
                :filial,
                :material,
                'ENTRADA',
                :quantidade,
                :origem,
                :referencia,
                CURRENT_TIMESTAMP
            )
        """),
        {
            "filial": filial_id,
            "material": material_id,
            "quantidade": quantidade,
            "origem": origem,
            "referencia": referencia_id
        }
    )

    def executar(conexao):

        existe = conexao.execute(
            text("""
                SELECT quantidade
                FROM estoque
                WHERE filial_id=:filial
                  AND material_id=:material
            """),
            {
                "filial": filial_id,
                "material": material_id
            }
        ).scalar()

        if existe is None:

            conexao.execute(
                text("""
                    INSERT INTO estoque
                    (
                        filial_id,
                        material_id,
                        quantidade
                    )
                    VALUES
                    (
                        :filial,
                        :material,
                        :quantidade
                    )
                """),
                {
                    "filial": filial_id,
                    "material": material_id,
                    "quantidade": quantidade
                }
            )

        else:

            conexao.execute(
                text("""
                    UPDATE estoque
                    SET quantidade = quantidade + :quantidade
                    WHERE filial_id=:filial
                    AND material_id=:material
                """),
                {
                    "filial": filial_id,
                    "material": material_id,
                    "quantidade": quantidade
                }
            )

        # ← AQUI

        

    if conn is None:

        with engine.begin() as conn_local:
            executar(conn_local)

    else:

        executar(conn)

def registrar_movimentacao_estoque(
    filial_id,
    material_id,
    tipo,
    quantidade,
    origem,
    referencia_id=None,
    conn=None
):

    def executar(conexao):

        conexao.execute(
            text("""
                INSERT INTO estoque_movimentacao
                (
                    filial_id,
                    material_id,
                    tipo,
                    quantidade,
                    origem,
                    referencia_id,
                    data_movimentacao
                )
                VALUES
                (
                    :filial_id,
                    :material_id,
                    :tipo,
                    :quantidade,
                    :origem,
                    :referencia_id,
                    CURRENT_TIMESTAMP
                )
            """),
            {
                "filial_id": filial_id,
                "material_id": material_id,
                "tipo": tipo,
                "quantidade": quantidade,
                "origem": origem,
                "referencia_id": referencia_id
            }
        )

    if conn is None:

        with engine.begin() as conn_local:
            executar(conn_local)

    else:

        executar(conn)
# ==========================================================
# SAÍDA
# ==========================================================

def saida_estoque(
    filial_id,
    material_id,
    quantidade,
    referencia_id=None,
    origem="VENDA",
    conn=None
):
    """
    Baixa de estoque.
    """

    saldo = obter_saldo(
        filial_id,
        material_id,
        conn
    )

    if saldo < quantidade:
        raise Exception("Estoque insuficiente.")

    def executar(conexao):

        # Baixa do estoque
        conexao.execute(
            text("""
                UPDATE estoque
                SET quantidade = quantidade - :quantidade
                WHERE filial_id = :filial
                AND material_id = :material
            """),
            {
                "quantidade": quantidade,
                "filial": filial_id,
                "material": material_id
            }
        )

        # Registra a movimentação
        registrar_movimentacao_estoque(
            filial_id=filial_id,
            material_id=material_id,
            tipo="SAIDA",
            quantidade=quantidade,
            origem=origem,
            referencia_id=referencia_id,
            conn=conexao
        )

    if conn is None:

        with engine.begin() as conn_local:
            executar(conn_local)

    else:

        executar(conn)


# ==========================================================
# AJUSTE
# ==========================================================

def ajustar_estoque(
    filial_id: int,
    material_id: int,
    quantidade: float,
    conn=None
):
    """
    Ajuste manual de estoque.
    """

    def executar(conexao):

        conexao.execute(
            text("""
                UPDATE estoque
                SET quantidade = :quantidade
                WHERE filial_id = :filial
                AND material_id = :material
            """),
            {
                "quantidade": quantidade,
                "filial": filial_id,
                "material": material_id
            }
        )

    if conn is None:

        with engine.begin() as conn_local:
            executar(conn_local)

    else:

        executar(conn)


# ==========================================================
# INVENTÁRIO
# ==========================================================

def inventario_filial(
    filial_id: int
):

    with engine.connect() as conn:

        return read_sql(
            text("""
                SELECT

                    e.material_id,

                    m.nome,

                    e.quantidade

                FROM estoque e

                INNER JOIN materiais m
                    ON m.id = e.material_id

                WHERE e.filial_id = :filial

                ORDER BY m.nome
            """),
            conn,
            params={
                "filial": filial_id
            }
        )

    if conn is None:

        with engine.begin() as conn_local:
            executar(conn_local)

    else:

        executar(conn)