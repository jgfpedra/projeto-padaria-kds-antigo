from app.utils.conversions import to_decimal
from app.repo.pedido import (
    buscar_cabecalho,
    buscar_observacoes,
    substituir_itens,
    buscar_itens_finalizacao,
    marcar_finalizado,
    proximo_id_venda,
    inserir_item,
    inserir_venda
)


class PedidoNaoEncontrado(Exception):
    pass


def normalizar_itens_editados(itens_front, obs_por_produto):
    """Converte o payload do front no formato gravado em pedido_itens."""
    saida = []
    for it in itens_front:
        cod = it.get("cod_produto")
        peso = to_decimal(it.get("quantidade"))
        un = to_decimal(it.get("quantidade_un"))
        saida.append({
            "cod_produto": cod,
            # se não há peso, usa as unidades como quantidade de venda
            "quantidade": peso if peso > 0 else un,
            "quantidade_un": un,
            "valor_unitario": to_decimal(it.get("preco_venda")),
            "observacao": obs_por_produto.get(str(cod), ""),
            "id_setor": it.get("id_setor"),
        })
    return saida


def montar_itens_venda(linhas):
    """Linhas de pedido_itens -> itens de food.vendaitem (ignora zerados)."""
    itens = []
    for id_produto, quantidade, preco, obs, id_setor in linhas:
        qtd = to_decimal(quantidade)
        pv = to_decimal(preco)
        total = pv * qtd
        if qtd <= 0 or total <= 0:
            continue
        itens.append({
            "id_produto": int(id_produto),
            "quantidade": float(qtd),
            "precovenda": float(pv),
            "valortotal": float(total),
            "observacao": obs,
            "id_setor": int(id_setor),
        })
    return itens


def finalizar_vrfood(cur_app, cur_vr, id_pedido, itens_front):
    cab = buscar_cabecalho(cur_app, id_pedido)
    if not cab:
        raise PedidoNaoEncontrado()
    id_loja, id_cliente = cab

    obs = buscar_observacoes(cur_app, id_pedido)
    itens_editados = normalizar_itens_editados(itens_front, obs)
    substituir_itens(cur_app, id_pedido, itens_editados)

    itens_venda = montar_itens_venda(buscar_itens_finalizacao(cur_app, id_pedido))

    id_venda = proximo_id_venda(cur_vr)
    inserir_venda(cur_vr, id_venda, id_loja, id_cliente, int(id_pedido))
    for it in itens_venda:
        inserir_item(cur_vr, id_venda, it)

    marcar_finalizado(cur_app, id_pedido, "vrfood")
    return {"id_venda": id_venda,
            "codigo": int(id_pedido),
            "itens_inseridos": len(itens_venda)}
