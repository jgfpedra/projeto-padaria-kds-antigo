import bcrypt

senha_plana = "102030"
senha_criptografada = bcrypt.hashpw(senha_plana.encode('utf-8'), bcrypt.gensalt())

print(senha_criptografada.decode())
