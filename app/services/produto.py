from app.repo.produto import (
    repo_vr_buscar_produtos,
    repo_get_precos_produtos,
)


def adicionar_nomes_produtos(itens, nomes):
    return [
        {
            **item,
            "descricao": nomes.get(item["id_produto"], f"#{item['id_produto']}"),
        }
        for item in itens
    ]


def buscar_produtos(termo, id_loja):
    if not termo:
        return []
    por_id = termo.isdigit()
    return repo_vr_buscar_produtos(
        termo=termo,
        id_loja=int(id_loja),
        por_id=por_id,
        limite=20,
    )


def preencher_precos_opcionais(grupos, id_loja):
    ids = {
        it["id_produto"]
        for g in grupos
        for it in g["itens"]
        if it.get("considera_valor")
    }
    precos = repo_get_precos_produtos(ids, id_loja)
    for g in grupos:
        for it in g["itens"]:
            it["preco_venda"] = (
                precos.get(it["id_produto"], 0) if it.get("considera_valor") else 0
            )
