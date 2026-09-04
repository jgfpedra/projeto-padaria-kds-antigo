from app.repo.produto import repo_vr_buscar_produtos


def adicionar_nomes_produtos(itens, nomes):
    return [
        {
            **item,
            "descricao": nomes.get(item["id_produto"], f"#{item['id_produto']}"),
        }
        for item in itens
    ]


def buscar_produtos(termo):
    termo = (termo or "").strip()

    if not termo:
        return []

    por_id = termo.isdigit()

    return repo_vr_buscar_produtos(
        termo=termo,
        por_id=por_id,
        limite=20,
    )
