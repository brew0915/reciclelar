import bcrypt
from sqlalchemy import text
from database import engine

def autenticar(email, senha):

    with engine.connect() as conn:

        usuario = conn.execute(
            text("""
                SELECT *
                FROM usuarios
                WHERE email = :email
                AND ativo = true
            """),
            {
                "email": email
            }
        ).mappings().first()

    if not usuario:
        return None

    if bcrypt.checkpw(
        senha.encode(),
        usuario["senha"].encode()
    ):
        return usuario

    return None