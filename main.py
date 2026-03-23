import os
import base64
import re
import httpx

from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
from openai import OpenAI

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

prompt = """
Transcribe el comprobante exactamente como aparece en la imagen.

Reglas:
- Respeta el orden original.
- Respeta las etiquetas completas tal como aparecen.
- No separes palabras que pertenecen a la misma etiqueta.
- Conserva números y signos tal como se ven.
- No resumas.
- No expliques.
- Devuelve solo la transcripción.
"""

class OCRRequest(BaseModel):
    image_url: str

def clean_ocr_text(texto: str) -> str:
    texto = texto.replace("Transaccioacutén", "Transacción")
    texto = texto.replace("Transaccioacute;n", "Transacción")
    texto = texto.replace("IdTransaccion", "ID Transacción")
    texto = texto.replace("ldTransaccion", "ID Transacción")
    texto = texto.replace("Id TTransaccion", "ID Transacción")
    texto = texto.replace("ATM Transacción ID", "ATM Transacción ID")
    texto = texto.replace("RECIBIDO :", "RECIBIDO:")
    texto = texto.replace("\r", "")
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n+", "\n", texto)
    return texto.strip()

def extract_fields(texto: str) -> dict:
    fields = {
        "id_transaccion": None,
        "fecha": None,
        "hora": None,
        "sucursal": None,
        "valor": None
    }

    # ID transacción
    id_match = re.search(
        r"ATM\s*Transacci[oó]n\s*ID[:\s]*([0-9]{6,})",
        texto,
        re.IGNORECASE
    )

    #Loop
    if not id_match:
        id_match = re.search(
            r"(?:^|\n)\s*(?:ID\s*Transacci[oó]n|Id\s*T?Transaccion|Id\s*Transaccion)[:\s]*([0-9]{6,})",
            texto,
            re.IGNORECASE
        )

    if not id_match:
        id_match = re.search(
            r"(?:^|\n)\s*NRO\.\s*TRANSACCION[:\s]*([0-9]{6,})",
            texto,
            re.IGNORECASE
        )

    if id_match:
        fields["id_transaccion"] = id_match.group(1)

    # Fecha y hora
    fecha_hora_match = re.search(
        r"(?:Fecha/Hora|Fecha)[:\s]*([0-9]{2}-[0-9]{2}-[0-9]{4}|[0-9]{2}/[0-9]{2}/[0-9]{4})(?:\s+([0-9]{2}:[0-9]{2}:[0-9]{2}))?",
        texto,
        re.IGNORECASE
    )
    if fecha_hora_match:
        fields["fecha"] = fecha_hora_match.group(1)
        fields["hora"] = fecha_hora_match.group(2) if fecha_hora_match.group(2) else None

    # Sucursal
    sucursal_match = re.search(r"Sucursal[:\s]*(.+)", texto, re.IGNORECASE)
    if sucursal_match:
        fields["sucursal"] = sucursal_match.group(1).strip()

    # Valor = plata que ingresó/entregó el usuario
    valor_ingresado_match = re.search(
        r"Valor\s+Ingresado[:\s]*(Gs\.?\s*[0-9\.\,]+)",
        texto,
        re.IGNORECASE
    )
    if valor_ingresado_match:
        fields["valor"] = valor_ingresado_match.group(1).strip()

    if not fields["valor"]:
        valor_entregado_match = re.search(
            r"Valor\s+Entregado[:\s]*(Gs\.?\s*[0-9\.\,]+)",
            texto,
            re.IGNORECASE
        )
        if valor_entregado_match:
            fields["valor"] = valor_entregado_match.group(1).strip()

    if not fields["valor"]:
        recibido_match = re.search(
            r"RECIBIDO[:\s]*(Gs\.?\s*[0-9\.\,]+)",
            texto,
            re.IGNORECASE
        )
        if recibido_match:
            fields["valor"] = recibido_match.group(1).strip()

    if not fields["valor"]:
        valor_recibido_match = re.search(
            r"Valor\s+recibido[:\s]*(Gs\.?\s*[0-9\.\,]+)",
            texto,
            re.IGNORECASE
        )
        if valor_recibido_match:
            fields["valor"] = valor_recibido_match.group(1).strip()

    if not fields["valor"]:
        valor_simple_match = re.search(
            r"Valor[:\s]*(Gs\.?\s*[0-9\.\,]+)",
            texto,
            re.IGNORECASE
        )
        if valor_simple_match:
            fields["valor"] = valor_simple_match.group(1).strip()

    return fields

def process_image_bytes(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": prompt
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_b64}"
                        }
                    }
                ]
            }
        ],
        temperature=0
    )

    texto = response.choices[0].message.content
    clean_text = clean_ocr_text(texto)
    fields = extract_fields(clean_text)

    return {
    "success": True,
    "id_transaccion": fields["id_transaccion"],
    "fecha": fields["fecha"],
    "hora": fields["hora"],
    "sucursal": fields["sucursal"],
    "valor": fields["valor"],
    "ocr_text": texto,
    "clean_text": clean_text,
    "fields": fields
}

@app.post("/ocr")
async def ocr_image(file: UploadFile = File(...)):
    image_bytes = await file.read()
    content_type = file.content_type or "image/jpeg"
    return process_image_bytes(image_bytes, content_type)

@app.post("/ocr-json")
async def ocr_from_json(data: OCRRequest):
    try:
        image_url = (data.image_url or "").strip()

        if image_url.lower() == "null" or image_url == "":
            return {
                "success": False,
                "error": "image_url vacío o null desde Unify",
                "received_image_url": image_url
            }

        if not image_url.startswith("http://") and not image_url.startswith("https://"):
            return {
                "success": False,
                "error": "image_url no tiene protocolo válido",
                "received_image_url": image_url
            }

        async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client_http:
            img_response = await client_http.get(
                image_url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "*/*"
                }
            )
            img_response.raise_for_status()

            image_bytes = img_response.content
            content_type = img_response.headers.get("content-type", "image/jpeg").split(";")[0]

        return process_image_bytes(image_bytes, content_type)

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
    
    
