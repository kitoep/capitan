#!/usr/bin/env python3
"""Hook PreToolUse del tool Agent (plugin capitan). En un proyecto que usa el
método (tiene .claude/capitan.md), bloquea cualquier encargo a un
agente que pueda escribir si no trae el brief base (brief-agente.md). Así no
depende de que alguien se acuerde de pegarlo."""
import json
import os
import sys

MARCA = "Reglas que no se negocian en este encargo"
SOLO_LECTURA = {"Explore", "Plan", "claude-code-guide", "statusline-setup"}

try:
    datos = json.load(sys.stdin)
except Exception:
    sys.exit(0)
entrada = datos.get("tool_input") or {}
tipo = entrada.get("subagent_type") or "general-purpose"
cwd = datos.get("cwd") or os.getcwd()
if tipo in SOLO_LECTURA or not os.path.exists(os.path.join(cwd, ".claude", "capitan.md")):
    sys.exit(0)
if MARCA in (entrada.get("prompt") or ""):
    sys.exit(0)
ruta = os.path.join(os.environ.get("CLAUDE_PLUGIN_ROOT", "<plugin capitan>"), "plantillas", "brief-agente.md")
print(
    f"Encargo bloqueado: falta el brief base. Pega TAL CUAL el contenido de {ruta} "
    "al inicio del prompt (incluye «" + MARCA + "») y debajo lo propio de la tarea.",
    file=sys.stderr,
)
sys.exit(2)
