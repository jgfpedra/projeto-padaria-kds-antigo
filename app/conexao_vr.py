# app/conexao_vr.py
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()


def conectar_vr():
    try:
        conn = psycopg2.connect(
            host=os.getenv("VR_DB_HOST"),
            port=os.getenv("VR_DB_PORT"),
            dbname=os.getenv("VR_DB_NAME"),
            user=os.getenv("VR_DB_USER"),
            password=os.getenv("VR_DB_PASS")
        )
        return conn
    except Exception as e:
        print(f"Erro na conexão com VR: {e}")
        return None


def buscar_clientes():
    conn = conectar_vr()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
        query = """
            SELECT 
                fc.id, fc.nome, fct.telefone, fc.endereco, fc.numero,
                fc.bairro, fc.observacao, m.descricao AS cidade, e.descricao AS estado
            FROM food.cliente AS fc
            INNER JOIN municipio AS m ON m.id = fc.id_municipio
            INNER JOIN estado AS e ON e.id = m.id_estado
            INNER JOIN food.clientetelefone AS fct ON fct.id_cliente = fc.id
            ;
        """
        cursor.execute(query)
        clientes = cursor.fetchall()

        return clientes
    except Exception as e:
        print(f"Erro ao buscar clientes: {e}")
        return []
    finally:
        conn.close()


def buscar_produtos():
    conn = conectar_vr()
    if not conn:
        return []

    try:
        cursor = conn.cursor()
        query = """
            SELECT 
                fsp.id_produto, p.descricaocompleta, p.pesobruto,
                tp.descricao AS tipoembalagem, fs.descricao AS setor
            FROM ficha.setorproduto AS fsp
            INNER JOIN ficha.setor AS fs ON fs.id = fsp.id_setor
            INNER JOIN produto AS p ON p.id = fsp.id_produto
            INNER JOIN tipoembalagem AS tp ON tp.id = p.id_tipoembalagem;
        """
        cursor.execute(query)
        produtos = cursor.fetchall()
        return produtos
    except Exception as e:
        print(f"Erro ao buscar produtos: {e}")
        return []
    finally:
        conn.close()
