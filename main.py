# main.py
# Este é o ponto de entrada principal do sistema da padaria

from pedidos import listar_pedidos_hoje


def main():
    print("=== Sistema de Encomendas da Padaria ===\n")
    listar_pedidos_hoje()
    print("\nFim da execução.")


if __name__ == "__main__":
    main()
