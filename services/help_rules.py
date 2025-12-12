from __future__ import annotations

# Penalizaciones por cada ayuda según su intensidad
HELP_PENALTIES = {
    "BAJA": 5,
    "MEDIA": 10,
    "ALTA": 15,
}

# Orden para determinar la intensidad dominante (se prioriza la más alta usada)
HELP_LEVEL_PRIORITY = ("ALTA", "MEDIA", "BAJA")

# Estilos de aprendizaje soportados en la UI del alumno
VALID_LEARNING_STYLES = ("VISUAL", "ANALITICA", "AUDIO")

# Puntaje base si la tarea no tiene max_points definido
DEFAULT_MAX_POINTS = 100

# Labels y textos auxiliares para componer ayudas
HELP_LEVEL_LABELS = {
    "BAJA": "Ayuda baja",
    "MEDIA": "Ayuda media",
    "ALTA": "Ayuda alta",
}

HELP_LEVEL_DEFAULTS = {
    "BAJA": "Identifica los conceptos clave de la consigna y escribí dos ejemplos o preguntas que conecten con lo que ya aprendiste.",
    "MEDIA": "Dividí la resolución en pasos cortos: repasa el material, extrae los datos importantes y plasmá un borrador antes de desarrollarlo.",
    "ALTA": "Repasa el procedimiento completo explicando cada paso: qué datos usás, cómo los transformás y qué conclusión deberías obtener.",
}

STYLE_LABELS = {
    "VISUAL": "Visual",
    "ANALITICA": "Analítica",
    "AUDIO": "Audio",
}

STYLE_HINTS = {
    "VISUAL": "Convertí «{topic}» en un esquema o mapa mental con colores o flechas que conecten ideas.",
    "ANALITICA": "Justificá cada paso con un dato o regla. Redactá conclusiones cortas del tipo \"Si ocurre A, entonces pasa B\".",
    "AUDIO": "Explicá el procedimiento como si grabaras un breve podcast; enfatizá palabras clave y ejemplos concretos.",
}

HELP_DETAIL_MODE_ORDER = ("BREVE", "GUIADA", "COMPLETA")
DEFAULT_HELP_DETAIL_MODE = "GUIADA"
HELP_DETAIL_MODES = {
    "BREVE": {
        "label": "Breve",
        "description": "2–3 frases concretas para encaminar la resolución sin revelar la respuesta.",
        "structure": [
            "Resume en una frase qué se espera lograr con {topic}.",
            "Plantea una pregunta guía que ayude a comprobar tu idea principal.",
            "Verificá que cites un dato (fecha, paso o ejemplo) antes de cerrar.",
        ],
    },
    "GUIADA": {
        "label": "Guiada",
        "description": "Introducción corta más 2-3 pasos para que el alumno avance con seguridad.",
        "structure": [
            "Describe por qué este contenido es importante para {topic}.",
            "Propone un paso a paso (revisa material, organiza ideas, contrasta con ejemplos).",
            "Incluye una recomendación ligada al estilo preferido: {style_tip}.",
            "Cierra con un recordatorio sobre cómo validar la respuesta (rubrica o criterios).",
        ],
    },
    "COMPLETA": {
        "label": "Completa",
        "description": "Mini guía que repasa el procedimiento completo con checklist final.",
        "structure": [
            "Arranca contextualizando {topic} y conecta con lo visto en clase.",
            "Detalla tres acciones consecutivas (investigar, organizar, producir/explicar).",
            "Incluye un ejemplo o comparación que ilustre el resultado esperado.",
            "Finaliza con una lista de verificación de 3 ítems para revisar antes de entregar.",
        ],
    },
}
