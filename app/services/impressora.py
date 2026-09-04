from app.repo.impressora import salvar


def salvar_impressora_setor(dados):
    dados = dados or {}

    id_loja = dados.get("id_loja")
    id_setor = dados.get("id_setor")
    caminho = (dados.get("caminho_impressora") or "").strip()

    if not id_loja or not caminho:
        raise ValueError(
            "id_loja e caminho_impressora são obrigatórios"
        )

    try:
        id_loja = int(id_loja)

        if id_setor in (None, ""):
            id_setor = None
        else:
            id_setor = int(id_setor)

    except (TypeError, ValueError):
        raise ValueError("id_loja/id_setor inválidos")

    return salvar(
        id_loja=id_loja,
        id_setor=id_setor,
        caminho=caminho,
    )
