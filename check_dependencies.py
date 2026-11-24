#!/usr/bin/env python3
"""
Script de verificación de dependencias para el proyecto Gemma4
"""

import sys
from pathlib import Path

def check_imports():
    """Verificar que todos los módulos se importan correctamente"""
    
    print("=" * 70)
    print("VERIFICACION DE DEPENDENCIAS - Gemma4")
    print("=" * 70)
    
    print(f"\nPython: {sys.version}")
    print(f"Ejecutable: {sys.executable}")
    
    modules = {
        "Librerías Estándar": [
            ("base64", "Codificación de datos"),
            ("json", "Procesamiento JSON"),
            ("math", "Funciones matemáticas"),
            ("os", "Operaciones del SO"),
            ("re", "Expresiones regulares"),
            ("subprocess", "Ejecución de procesos"),
            ("tempfile", "Archivos temporales"),
            ("pathlib", "Manipulación de rutas"),
        ],
        "Dependencias Externas": [
            ("gradio", "Interfaz web interactiva"),
            ("requests", "Cliente HTTP"),
        ],
    }
    
    all_ok = True
    
    for category, libs in modules.items():
        print(f"\n{category}:")
        print("-" * 70)
        
        for lib, description in libs:
            try:
                __import__(lib)
                print(f"  [OK] {lib:20} - {description}")
            except ImportError as e:
                print(f"  [FAIL] {lib:20} - {description}")
                print(f"     Error: {e}")
                all_ok = False
    
    print("\n" + "=" * 70)
    if all_ok:
        print("[OK] TODAS LAS DEPENDENCIAS ESTAN DISPONIBLES")
        return 0
    else:
        print("[FAIL] FALTA INSTALAR ALGUNAS DEPENDENCIAS")
        print("   Ejecuta: pip install -r requirements.txt")
        return 1
    print("=" * 70)

if __name__ == "__main__":
    sys.exit(check_imports())
