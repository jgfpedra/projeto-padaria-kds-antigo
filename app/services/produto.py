def adicionar_nomes_produtos(itens, nomes):
    return [
        {
            **item,
            "descricao": nomes.get(
                item["id_produto"],
                f"#{item['id_produto']}"
            ),
        }
        for item in itens
    ]
