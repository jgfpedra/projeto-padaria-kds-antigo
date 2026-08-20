# pedidos.py
from database import conectar
from datetime import date

def listar_pedidos_hoje():
    conn = conectar()
    if not conn:
        print("Não foi possível conectar ao banco.")
        return

    try:
        cursor = conn.cursor()
        hoje = date.today().isoformat()
        
        query = """
            SELECT id, nome_cliente, telefone, data_entrega, observacoes
            FROM encomendas
            WHERE data_entrega = %s
            ORDER BY data_entrega, nome_cliente;
        """

        cursor.execute(query, (hoje,))
        pedidos = cursor.fetchall()

        print("📦 Encomendas para hoje:")
        for p in pedidos:
            print(f"ID: {p[0]} | Cliente: {p[1]} | Tel: {p[2]} | Entrega: {p[3]} | Obs: {p[4]}")

    except Exception as e:
        print(f"Erro ao buscar pedidos: {e}")
    finally:
        conn.close()
