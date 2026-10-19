#!/usr/bin/env python3
"""Hook UserPromptSubmit (plugin capitan). En cada mensaje del dueño recuerda
registrar sus decisiones. Casi gratis (unas palabras); el que obliga es el juez
de hook_cierre.py."""
import json
import os
import sys

try:
    datos = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if not os.path.exists(os.path.join(datos.get("cwd") or os.getcwd(), ".claude", "capitan.md")):
    sys.exit(0)
print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext":
    "capitan: si este mensaje trae una decisión del dueño (regla, criterio, nombre, alcance, corrección, "
    "o aprueba una propuesta), regístrala ya en docs/capitan/decisiones.md con fecha y porqué. "
    "Si la decisión es sobre el método Capitán y no sobre este proyecto, no va en este proyecto: propónla al dueño como cambio al plugin."}}))
