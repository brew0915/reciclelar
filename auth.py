import bcrypt
from sqlalchemy import text
from database import engine

def autenticar(email, senha):
    """
    Autentica um usuário validando o e-mail e a senha criptografada com bcrypt.
    Retorna o dicionário com os dados do usuário se bem-sucedido, ou None caso contrário.
    """
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT id, nome, email, senha, ativo
                FROM usuarios
                WHERE email = :email
                AND ativo = true
            """),
            {
                "email": email
            }
        ).mappings().first()

    # Se o usuário não for encontrado ou não estiver ativo
    if not result:
        return None

    # Converte o RowMapping do SQLAlchemy em um dicionário Python nativo
    usuario = dict(result)

    # Verifica se a senha digitada corresponde ao hash do banco de dados
    if bcrypt.checkpw(senha.encode('utf-8'), usuario["senha"].encode('utf-8')):
        # Remove o hash da senha antes de retornar por questões de segurança
        del usuario["senha"]
        return usuario

    return None
