import os


def gerar_dados_impressao(texto, cortar=True, tipo_corte="full"):
    ESC = b"\x1b"
    GS = b"\x1d"

    init_printer = ESC + b"@"

    try:
        select_cp = ESC + b"t" + b"\x03"

        dados = init_printer + select_cp + texto.encode("cp860", errors="replace")

    except LookupError:
        select_cp = ESC + b"t" + b"\x02"

        dados = init_printer + select_cp + texto.encode("cp850", errors="replace")

    if cortar:
        corte = b"\x00" if tipo_corte == "full" else b"\x01"
        dados += GS + b"V" + corte

    return dados


def enviar_para_impressora(caminho_impressora, dados, id_pedido):
    with open(caminho_impressora, "wb") as destino:
        destino.write(dados)
