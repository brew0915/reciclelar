from sqlalchemy import text

def autenticar(email, senha):
    # Se 'conn' veio de st.connection("banco", type="sql")
    # O correto é abrir um escopo de conexão do SQLAlchemy:
    with conn.connect() as session:
        result = session.execute(
            text("""
                SELECT * FROM usuarios 
                WHERE email = :email AND senha = :senha
            """),
            {"email": email, "senha": senha}
        ).mappings().first()
        
    return result
