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
