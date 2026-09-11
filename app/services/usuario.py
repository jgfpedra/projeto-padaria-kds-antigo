from app.repo.usuario import (
    consultar,
    buscar_por_id,
    inserir,
    atualizar,
)


def consultar_usuarios(filtro=""):
    return consultar(filtro)


def buscar_usuario(id_usuario):
    try:
        id_usuario = int(id_usuario)
    except (TypeError, ValueError):
        raise ValueError("ID do usuário inválido")

    usuario = buscar_por_id(id_usuario)

    if not usuario:
        raise LookupError("Usuário não encontrado")

    return usuario


def criar_usuario(dados):
    dados = dados or {}

    nome = (dados.get("nome") or "").strip()
    email = (dados.get("email") or "").strip()
    senha = (dados.get("senha") or "").strip()
    id_loja = dados.get("id_loja")
    cargo = (dados.get("cargo") or "").strip() or None

    if not nome:
        raise ValueError("Nome é obrigatório")

    if not email:
        raise ValueError("Email é obrigatório")

    if not senha:
        raise ValueError("Senha é obrigatória")

    if not id_loja:
        raise ValueError("Loja é obrigatória")

    try:
        id_loja = int(id_loja)
    except (TypeError, ValueError):
        raise ValueError("id_loja inválido")

    return inserir(
        nome=nome,
        email=email,
        senha=senha,
        id_loja=id_loja,
        cargo=cargo,
    )


def editar_usuario(id_usuario, dados):
    dados = dados or {}

    try:
        id_usuario = int(id_usuario)
    except (TypeError, ValueError):
        raise ValueError("ID do usuário inválido")

    nome = (dados.get("nome") or "").strip()
    email = (dados.get("email") or "").strip()
    senha = (dados.get("senha") or "").strip()
    id_loja = dados.get("id_loja")
    cargo = (dados.get("cargo") or "").strip() or None

    if not nome:
        raise ValueError("Nome é obrigatório")

    if not email:
        raise ValueError("Email é obrigatório")

    if not id_loja:
        raise ValueError("Loja é obrigatória")

    try:
        id_loja = int(id_loja)
    except (TypeError, ValueError):
        raise ValueError("id_loja inválido")

    atualizado = atualizar(
        id_usuario=id_usuario,
        nome=nome,
        email=email,
        senha=senha or None,
        id_loja=id_loja,
        cargo=cargo,
    )

    if not atualizado:
        raise LookupError("Usuário não encontrado")

    return True
