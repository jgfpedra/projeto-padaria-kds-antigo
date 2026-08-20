import requests

# Substitua pelos seus dados
API_KEY = "801eba4e-5d00-4684-a509-b31993f9cf15"
MEU_NUMERO = "5519981828742"

def enviar_mensagem(numero_destino, mensagem, custom_id):
    payload = {
        "apikey": API_KEY,
        "phone_number": MEU_NUMERO,
        "contact_phone_number": numero_destino,
        "message_custom_id": custom_id,
        "message_type": "text",
        "message_body": mensagem
    }

    response = requests.post("https://app.whatsgw.com.br/api/WhatsGw/Send/", json=payload)
    print("✅ Enviado para", numero_destino, "| Status:", response.status_code)
    return response.json()
