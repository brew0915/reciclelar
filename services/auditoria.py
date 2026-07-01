from sqlalchemy import text

from database import engine
from services.financeiro import registrar_movimentacao

def registrar_auditoria(
    usuario_id: int,
    acao: str,
    tabela: str,
    registro_id: int = None,
    conn=None
):

    if conn is None:

        with engine.begin() as conn_local:

            conn_local.execute(
                text("""
                    INSERT INTO auditoria
                    (
                        usuario_id,
                        acao,
                        tabela,
                        registro_id
                    )
                    VALUES
                    (
                        :usuario_id,
                        :acao,
                        :tabela,
                        :registro_id
                    )
                """),
                {
                    "usuario_id": usuario_id,
                    "acao": acao,
                    "tabela": tabela,
                    "registro_id": registro_id
                }
            )

    else:

        conn.execute(
            text("""
                INSERT INTO auditoria
                (
                    usuario_id,
                    acao,
                    tabela,
                    registro_id
                )
                VALUES
                (
                    :usuario_id,
                    :acao,
                    :tabela,
                    :registro_id
                )
            """),
            {
                "usuario_id": usuario_id,
                "acao": acao,
                "tabela": tabela,
                "registro_id": registro_id
            }
        )