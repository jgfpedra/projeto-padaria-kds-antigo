from app.utils.date import normalize_text, br_date, br_time
from app.repo.pedido import (
    buscar_cliente,
    buscar_nome_loja,
    buscar_status,
    buscar_valor_total,
    buscar_itens,
    buscar_impresso,
    buscar_pedidos,
)
from app.utils.monetary import formatar_valor


def adicionar_cabecalho(linhas, pedido, cliente, nome_loja, status):
    linhas.append(f"Pedido #{pedido['id']}")

    linhas.append(f"Loja: {normalize_text(nome_loja)}")

    linhas.append(f"Cliente: {normalize_text(cliente['nome'])}")

    linhas.append(f"Telefone: {normalize_text(cliente['telefone'])}")

    if status:
        linhas.append(f"Status: {normalize_text(status)}")


def adicionar_entrega(linhas, pedido):
    data_entrega = br_date(pedido["data_entrega"])

    hora_entrega = br_time(pedido["hora_entrega"])

    linhas.append(f"Tipo Entrega: {normalize_text(pedido['tipo_entrega'])}")

    linhas.append(f"Data Entrega: {data_entrega} - {hora_entrega}")


def adicionar_observacoes(linhas, observacoes):
    if not observacoes:
        return

    linhas.append("")
    linhas.append("Observações do Pedido:")

    for linha in str(observacoes).splitlines():
        linha = linha.strip()

        if linha:
            linhas.append(normalize_text(linha))


def adicionar_produtos(linhas, itens):
    linhas.append("")
    linhas.append("Produtos (ordem alfabética):")

    for item in itens:
        linha = f"{item['quantidade_un']
                   } un - " f"{normalize_text(item['descricao'])}"

        if item["observacao"]:
            linha += f" ({normalize_text(item['observacao'])})"

        linhas.append(linha)


def montar_texto_pedido(
    pedido, cliente, nome_loja, status, valor_total, itens, linhas_extras=3
):
    linhas = []

    adicionar_cabecalho(linhas, pedido, cliente, nome_loja, status)

    adicionar_entrega(linhas, pedido)

    adicionar_observacoes(linhas, pedido["observacoes"])

    adicionar_produtos(linhas, itens)

    linhas.append(f"Valor Total: {formatar_valor(valor_total)}")

    for _ in range(max(0, linhas_extras)):
        linhas.append("")

    return "\r\n".join(linhas) + "\r\n"


def consultar_encomendas(filtros, cursor_app, cursor_vr):
    pedidos_rows = buscar_pedidos(cursor_app, filtros)

    pedidos = []

    for pedido in pedidos_rows:
        cliente = buscar_cliente(
            cursor_vr,
            pedido["id_cliente"],
        )

        nome_loja = buscar_nome_loja(
            cursor_vr,
            pedido["id_loja"],
        )

        status = buscar_status(
            cursor_app,
            pedido["id_status"],
        )

        valor_total = buscar_valor_total(
            cursor_app,
            pedido["id"],
        )

        itens = buscar_itens(
            cursor_app,
            cursor_vr,
            pedido["id"],
        )

        impresso = buscar_impresso(
            cursor_app,
            pedido["id"],
        )

        pedidos.append(
            {
                "id": pedido["id"],
                "nome_cliente": cliente["nome"],
                "telefone": cliente["telefone"],
                "endereco": cliente["endereco"],
                "tipo_entrega": pedido["tipo_entrega"],
                "observacoes": pedido["observacoes"],
                "data_pedido": (
                    pedido["criado_em"].isoformat() if pedido["criado_em"] else ""
                ),
                "data_entrega": (
                    pedido["data_entrega"].isoformat() if pedido["data_entrega"] else ""
                ),
                "hora_entrega": (
                    pedido["hora_entrega"].strftime("%H:%M")
                    if pedido["hora_entrega"]
                    else ""
                ),
                "id_status": pedido["id_status"],
                "status_descricao": status,
                "valor_total": valor_total,
                "nome_loja": nome_loja,
                "impresso": impresso,
                "itens": itens,
            }
        )

    return pedidos
