"""Cohere Vision: una foto -> estado exterior + justificación breve."""
import base64
import cohere
import json
import os
import re
from .config import ESTADOS

MODELO_VISION = "command-a-vision-07-2025"
# TODO C1-A (autoría propia): diseñad y escribid el prompt del modelo visual.
# El texto NO se proporciona. Revisad GUIA_ALUMNADO.md, etapa 5.
# Debe describir tarea, reglas, 4 estados, unknown y formato de respuesta.
PROMPT = """Eres un perito de tasación de vehículos usados. Analiza la fotografía adjunta y evalúa ÚNICAMENTE el estado EXTERIOR visible del coche (carrocería, pintura, cristales, faros, llantas y neumáticos). Elige un único estado.

ESTADOS PERMITIDOS (usa exactamente uno de estos valores, en inglés y en minúsculas):
- "like new": como nuevo; sin arañazos, golpes ni desgaste apreciable.
- "excellent": excelente; desgaste mínimo, apenas perceptible.
- "good": bueno; pequeñas marcas, arañazos leves o desgaste normal de uso.
- "fair": aceptable; daños o desgaste claramente visibles (abolladuras, óxido, pintura deteriorada, piezas dañadas).
- "unknown": úsalo si la imagen no muestra claramente un coche, si solo se ve una parte pequeña (por ejemplo, una rueda), si está borrosa, oscura o demasiado lejos, o si no hay evidencia visual suficiente. No adivines: ante la duda, responde "unknown".

REGLAS:
- Basa tu decisión solo en lo que se ve en la imagen.
- No hagas afirmaciones sobre el motor, el funcionamiento mecánico, averías, el kilometraje real ni el historial de accidentes: no se pueden saber por una foto.
- No inventes puntuaciones, porcentajes ni niveles de confianza.

FORMATO DE RESPUESTA:
Responde SOLO con un objeto JSON válido, sin texto antes ni después y sin bloques de código Markdown. Debe tener exactamente estas dos claves y ninguna más:
- "condition": uno de los valores permitidos ("like new", "excellent", "good", "fair" o "unknown").
- "reason": una frase breve en español (máximo 30 palabras) que cite detalles visibles de la foto que justifiquen el estado.

Ejemplo del formato (no copies su contenido):
{"condition": "good", "reason": "Se aprecian arañazos leves en el paragolpes delantero; la pintura conserva el brillo."}"""


class VisionError(Exception):
    """Error de proveedor o de respuesta no interpretable."""


def parsear_respuesta(texto: str) -> tuple[str, str]:
    """Helper ya implementado: valida el JSON que responde la IA."""
    limpio = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto.strip(), flags=re.I)
    if not limpio.startswith("{"):
        a, b = limpio.find("{"), limpio.rfind("}")
        if a >= 0 and b > a:
            limpio = limpio[a:b+1]
    try:
        obj = json.loads(limpio)
    except (ValueError, TypeError) as exc:
        raise VisionError("Cohere no devolvió un JSON interpretable.") from exc
    estado = str(obj.get("condition", "")).strip().lower()
    razon = str(obj.get("reason", "")).strip()[:350]
    if estado not in (*ESTADOS, "unknown"):
        raise VisionError(f"Cohere devolvió una categoría inesperada: {estado!r}")
    return estado, razon or "Sin justificación visible."


def clasificar_estado(contenido: bytes, mimetype: str) -> tuple[str, str, str]:
    """C1: devuelve (condition, reason, fuente)."""
    if os.getenv("VISION_MOCK", "0") == "1":
        return "good", "Modo demostración: estado fijo, sin analizar la fotografía.", "MOCK"
    token = os.getenv("COHERE_API_KEY", "").strip()
    if not token:
        raise VisionError("Falta COHERE_API_KEY en el archivo .env")
    if not PROMPT.strip():
        raise VisionError("Falta redactar el prompt visual: tarea C1-A.")

    # 1. Bytes -> Base64 -> data URL (respetando el MIME real de la foto)
    imagen_b64 = base64.b64encode(contenido).decode("utf-8")
    data_url = f"data:{mimetype};base64,{imagen_b64}"

    # 2. Llamada multimodal: texto (PROMPT) + imagen en el mismo mensaje de usuario
    try:
        cliente = cohere.ClientV2(api_key=token)
        respuesta = cliente.chat(
            model=MODELO_VISION,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }],
            temperature=0,
        )
    except Exception as exc:  # red, autenticación (401), límite de uso (429), etc.
        raise VisionError(f"No se pudo consultar Cohere Vision: {exc}") from exc

    # 3. Extraer el texto devuelto
    try:
        texto = "".join(
            bloque.text
            for bloque in (respuesta.message.content or [])
            if getattr(bloque, "type", "text") == "text" and getattr(bloque, "text", None)
        ).strip()
    except AttributeError as exc:
        raise VisionError("Cohere devolvió una respuesta con un formato inesperado.") from exc

    if not texto:
        raise VisionError("Cohere no devolvió ningún texto.")

    # 4. Validar el JSON con el comprobador proporcionado
    try:
        estado, razon = parsear_respuesta(texto)
    except VisionError:
        raise
    except Exception as exc:
        raise VisionError(f"La respuesta de Cohere no es un JSON válido: {texto[:200]}") from exc

    return estado, razon, "COHERE"
