from datetime import datetime


def br_date(data):
    if not data:
        return ""

    if isinstance(data, datetime):
        return data.strftime("%d/%m/%Y")

    try:
        return datetime.strptime(str(data)[:10],
                                 "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return str(data)


def br_time(hora):
    if not hora:
        return ""

    if isinstance(hora, datetime):
        return hora.strftime("%H:%M")

    return str(hora)[:5]


def normalize_text(texto):
    if texto is None:
        return ""

    texto = str(texto)

    substituicoes = {
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "—": "-",
        "–": "-",
        "…": "...",
        "•": "*",
    }

    for antigo, novo in substituicoes.items():
        texto = texto.replace(antigo, novo)

    return texto
