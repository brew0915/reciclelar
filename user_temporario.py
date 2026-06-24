import bcrypt

senha = "admin123"

hash_senha = bcrypt.hashpw(
    senha.encode(),
    bcrypt.gensalt()
)

print(hash_senha.decode())