# seeds/__init__.py
# Permite que la carpeta seeds funcione como un paquete Python.
# No necesita nada más para el MVP.

from .basic_seed import seed_basic_data

__all__ = ["seed_basic_data"]