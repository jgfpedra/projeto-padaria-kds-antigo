# main.py
# Este é o ponto de entrada principal do sistema da padaria

from pedidos import listar_pedidos_hoje

def main():
    print("=== Sistema de Encomendas da Padaria ===\n")
    listar_pedidos_hoje()
    print("\nFim da execução.")

# Garante que o código só roda se esse arquivo for executado diretamente
if __name__ == "__main__":
    main()
