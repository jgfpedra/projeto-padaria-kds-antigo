# app/conexao_app.py
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def conectar_app():
    try:
        conn = psycopg2.connect(os.getenv("DATABASE_URL"))
        return conn
    except Exception as e:
        print(f"Erro na conexão com o banco do app: {e}")
        return None
