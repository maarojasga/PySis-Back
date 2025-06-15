from fastapi import APIRouter, Request, HTTPException
import os
import json
import requests
from app.core.telegram_bot import get_bot
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

RAG_CONVERSATION_URL = os.getenv("CORE_SERVICE_URL", "http://core_service:8002") + "/conversation/query"

@router.post("/webhook/")
async def telegram_webhook(request: Request):
    print("Received headers:", request.headers)
    try:
        body = await request.body()
        print("Received raw body:", body)
        if not body:
            print("Received empty body")
            return {"status": "empty body"}
        update = json.loads(body)
        print("Received update:", update)
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        print(f"Body that caused error: {body.decode('utf-8', errors='ignore')}")
        return {"status": "error", "message": f"Invalid JSON body: {e}"}
    except Exception as e:
        print(f"An unexpected error occurred processing the body: {e}")
        return {"status": "error", "message": f"Internal server error: {e}"}
    
    if "message" in update:
        message = update["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        user_name = message.get("from", {}).get("first_name", "Usuario Anónimo")
        
        if not text:
            return {"status": "no text message"}
        
        try:
            bot_instance = get_bot()
        except ValueError as e:
            print(f"Error getting bot instance: {e}")
            raise HTTPException(status_code=500, detail=f"Could not configure bot: {e}")
        except Exception as e:
            print(f"Unexpected error getting bot instance: {e}")
            raise HTTPException(status_code=500, detail=f"Unexpected error configuring bot: {e}")

        payload = {
            "phone_number": str(chat_id),
            "question": text,
            "user_name": user_name,
            "conversation_id": None
        }
        
        answer = "Lo siento, no pude procesar tu consulta en este momento."
        try:
            print(f"Sending payload to RAG service: {payload}")
            response = requests.post(RAG_CONVERSATION_URL, json=payload, timeout=45)
            print(f"RAG service response status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"RAG service response data: {data}")
                answer = data.get("answer", answer)
            else:
                error_detail = response.text[:500]
                print(f"Error from RAG service ({response.status_code}): {error_detail}")
                answer = f"Lo siento, ocurrió un error ({response.status_code}) al comunicarme con el servicio de conversación."
        except requests.exceptions.Timeout:
            print("Timeout calling RAG service.")
            answer = "Lo siento, el servicio de conversación tardó demasiado en responder."
        except requests.exceptions.RequestException as e:
            print(f"RequestException calling RAG service: {e}")
            answer = f"Error en la comunicación con el servicio de conversación."
        except Exception as e:
            print(f"Unexpected error during RAG service call: {e}")
            answer = f"Error inesperado procesando tu solicitud."
        
        try:
            answer = answer.replace('\\n', '\n')
            await bot_instance.send_message(chat_id=chat_id, text=answer, parse_mode='HTML')
            print(f"Message sent to chat_id {chat_id}: {answer[:100]}...")
        except Exception as e:
            print(f"Error sending message via Telegram, chat_id {chat_id}: {e}")

    return {"status": "ok"}