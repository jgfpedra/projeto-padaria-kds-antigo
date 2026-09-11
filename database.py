# database.py
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def conectar():
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
        )
        return conn
    except Exception as e:
        print(f"Erro na conexão com o banco: {e}")
        return None
