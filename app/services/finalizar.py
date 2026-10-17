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

        obs = it.get("observacao")
        if obs is None or obs == "":
            obs = obs_por_produto.get(str(cod), "")

        saida.append({
            "cod_produto": cod,
            # se não há peso, usa as unidades como quantidade de venda
            "quantidade": peso if peso > 0 else un,
            "quantidade_un": un,
            "valor_unitario": to_decimal(it.get("preco_venda")),
            "observacao": obs,
            "id_setor": it.get("id_setor"),
            "peso_bruto": to_decimal(it.get("peso_bruto")),
            "cod_produto_associado": it.get("cod_produto_associado") or None,
            "id_status": 0,
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


def finalizar_vrficha(cur_app, cur_vr, id_pedido, numero_ficha, itens_front):
    if not numero_ficha:
        raise ValueError("Número da ficha é obrigatório.")
    if not itens_front:
        raise ValueError("Nenhum item informado.")

    cab = buscar_cabecalho(cur_app, id_pedido)
    if not cab:
        raise PedidoNaoEncontrado()
    id_loja, _id_cliente = cab

    obs = buscar_observacoes(cur_app, id_pedido)   # antes do DELETE
    itens_editados = normalizar_itens_editados(itens_front, obs)
    substituir_itens(cur_app, id_pedido, itens_editados)

    # ficha: reaproveita se já existe, senão cria
    cur_vr.execute(
        "SELECT id FROM pdv.ficha WHERE numeroficha = %s AND id_loja = %s",
        (numero_ficha, id_loja),
    )
    row = cur_vr.fetchone()
    if row:
        id_ficha = row[0]
        # sem DELETE: mantém os itens que já estão na ficha
        cur_vr.execute(
            "SELECT COALESCE(MAX(sequencia), 0) FROM pdv.fichaitem WHERE id_ficha = %s",
            (id_ficha,),
        )
        sequencia = cur_vr.fetchone()[0] + 1
    else:
        cur_vr.execute("SELECT nextval('ficha.ficha_id_seq')")
        id_ficha = cur_vr.fetchone()[0]
        cur_vr.execute(
            """
            INSERT INTO pdv.ficha (id, id_loja, numeroficha,
            data, datahora, id_mesa, cliente)
            VALUES (%s, %s, %s, CURRENT_DATE, NOW(), %s, %s)
            """,
            (id_ficha, id_loja, numero_ficha, 1, None),
        )

    sequencia = 1
    for linha in buscar_itens_finalizacao(cur_app, id_pedido):
        id_produto, quantidade, valor_unitario = linha[0], linha[1], linha[2]
        if not quantidade or quantidade <= 0 or not valor_unitario or valor_unitario <= 0:
            continue

        cur_vr.execute(
            "SELECT codigobarras FROM produtoautomacao WHERE id_produto = %s LIMIT 1",
            (id_produto,),
        )
        cb = cur_vr.fetchone()

        cur_vr.execute("SELECT nextval('ficha.fichaitem_id_seq')")
        id_fichaitem = cur_vr.fetchone()[0]
        cur_vr.execute(
            """
            INSERT INTO pdv.fichaitem (
                id, id_ficha, sequencia, codigobarras, quantidade,
                precovenda, id_atendente, iscancelado, isimpresso
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (id_fichaitem, id_ficha, sequencia, cb[0] if cb else None,
             quantidade, valor_unitario, -1, False, False),
        )
        sequencia += 1

    marcar_finalizado(cur_app, id_pedido, "vrficha")
    return {"id_ficha": id_ficha, "itens_inseridos": sequencia - 1}


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
