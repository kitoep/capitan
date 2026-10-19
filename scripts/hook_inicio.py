#!/usr/bin/env python3
"""Hook SessionStart (plugin capitan). Al abrir una conversación en un
proyecto que usa el método, inyecta el relevo (docs/capitan/estado.md) y las
decisiones vigentes (docs/capitan/decisiones.md). Así una conversación nueva
sabe dónde quedó todo sin depender de la anterior."""
import json
import os
import sys

# Claude Code guarda en un archivo y deja solo una vista previa de lo que un
# hook inyecta si pasa de 10,000 caracteres (docs de hooks, «Important
# limits»). No cortamos nada: si no cabe, se inyecta lo que cabe y se ordena
# leer el resto completo, y se pide podar.
LIMITE = 9500

try:
    datos = json.load(sys.stdin)
except Exception:
    datos = {}
cwd = datos.get("cwd") or os.getcwd()

# Si el dueño ya instaló el medidor (configurar lo copia a ~/.claude/capitan/,
# fuera de la carpeta versionada del plugin para que la barra de estado no se
# rompa al actualizar), se mantiene al día con la versión del plugin. Nunca se
# instala solo: sin la copia previa, no se hace nada.
try:
    import shutil
    nuevo = os.path.join(os.path.dirname(os.path.abspath(__file__)), "medidor.py")
    instalado = os.path.join(os.path.expanduser("~"), ".claude", "capitan", "medidor.py")
    if os.path.exists(instalado) and open(nuevo, "rb").read() != open(instalado, "rb").read():
        shutil.copyfile(nuevo, instalado)
except Exception:
    pass

if not os.path.exists(os.path.join(cwd, ".claude", "capitan.md")):
    sys.exit(0)

intro = (
    "Este proyecto usa el método Capitán (plugin capitan). Antes de trabajar, "
    "lo que sigue es el relevo de la sesión anterior y las decisiones vigentes del dueño. "
    "Para avanzar el plan: /capitan:trabajar. La configuración está en .claude/capitan.md."
)
partes, por_leer = [intro], []
for nombre in ("estado.md", "decisiones.md"):
    ruta = os.path.join("docs", "capitan", nombre)
    completa = os.path.join(cwd, ruta)
    if not os.path.exists(completa):
        partes.append(f"(No existe {ruta} todavía.)")
        continue
    bloque = f"--- {ruta} ---\n" + open(completa, encoding="utf-8").read()
    if len("\n\n".join(partes + [bloque])) + 600 > LIMITE:
        por_leer.append(ruta)
    else:
        partes.append(bloque)
if por_leer:
    partes.append(
        "OBLIGATORIO antes de cualquier otra cosa: lee COMPLETOS con la herramienta Read "
        + ", ".join(por_leer)
        + " — no cupieron aquí. Y pódalos: estado.md es un relevo corto (el detalle va en "
        "docs/capitan/sesiones/); de decisiones.md, lo reemplazado pasa a "
        "docs/capitan/decisiones-historial.md."
    )

print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "\n\n".join(partes)}}))
