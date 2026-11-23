#!/usr/bin/env python3
"""Hook PreToolUse del tool Agent (plugin capitan). En un proyecto que usa el
método (tiene .claude/capitan.md):

1. Bloquea cualquier encargo a un agente que pueda escribir si no trae el
   brief base (brief-agente.md). Así no depende de que alguien se acuerde de
   pegarlo.
2. Cada encargo de un agente que puede escribir declara a qué paso del ciclo
   pertenece («Paso 10 de ACT-012») o que va fuera del ciclo («Fuera del
   ciclo: <motivo>»).
3. Si el encargo declara un paso, el checklist (ciclo.py) tiene que tener
   cerrados los anteriores, salvo su par en paralelo. Un agente no arranca un
   paso que todavía no toca."""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MARCA = "Reglas que no se negocian en este encargo"
SOLO_LECTURA = {"Explore", "Plan", "claude-code-guide", "statusline-setup"}
# La declaración va al principio de una línea (la primera de lo propio, debajo del brief):
# una mención de otro paso a media frase, o el ejemplo de la plantilla, no cuentan.
DECLARA = re.compile(r"^[ \t>*«\"]*paso\s+(\d+)\s+de\s+(?:[A-Z][A-Z0-9]*-\d+/)?(ACT-\d+)\b", re.I | re.M)
FUERA = re.compile(r"^[ \t>*«\"]*fuera del ciclo\s*:\s*\S", re.I | re.M)


def bloquear(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


def avisar(msg: str) -> None:
    print(json.dumps({"systemMessage": f"capitan: {msg}"}, ensure_ascii=False))
    sys.exit(0)


def main() -> None:
    try:
        datos = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    entrada = datos.get("tool_input") or {}
    tipo = entrada.get("subagent_type") or "general-purpose"
    prompt = entrada.get("prompt") or ""
    cwd = datos.get("cwd") or os.getcwd()
    if not os.path.exists(os.path.join(cwd, ".claude", "capitan.md")):
        sys.exit(0)
    escribe = tipo not in SOLO_LECTURA

    if escribe and MARCA not in prompt:
        ruta = os.path.join(os.environ.get("CLAUDE_PLUGIN_ROOT", "<plugin capitan>"), "plantillas", "brief-agente.md")
        bloquear(f"Encargo bloqueado: falta el brief base. Pega TAL CUAL el contenido de {ruta} "
                 "al inicio del prompt (incluye «" + MARCA + "») y debajo lo propio de la tarea.")

    m = DECLARA.search(prompt)
    if not m:
        if escribe and not FUERA.search(prompt):
            bloquear("Encargo bloqueado: di a qué paso del ciclo pertenece («Paso 10 de ACT-012») para que el "
                     "checklist lo revise, o «Fuera del ciclo: <motivo>» si no es parte de una actividad.")
        sys.exit(0)

    import ciclo
    n, clave = int(m.group(1)), m.group(2).upper()
    try:
        c = ciclo.leer(cwd, clave)
    except (OSError, ValueError) as e:
        avisar(f"no pude leer el checklist de {clave} ({e}); revisa a mano que los pasos antes del {n} estén "
               "cerrados, y anótalo en docs/capitan/aprendizajes.md.")
    except ciclo.Rechazo:
        sys.exit(0)  # fuera de un repo de git: no hay checklist que leer
    if c is None:
        if n > 2:
            bloquear(f"Encargo bloqueado: {clave} no tiene checklist del ciclo y este es el paso {n}. "
                     f"Créalo (`ciclo.py crear {clave}`, paso 2) y cierra los pasos que ya pasaron.")
        sys.exit(0)
    abiertos = ciclo.abiertos_antes(c, n)
    if abiertos:
        bloquear(f"Encargo bloqueado: es el paso {n} de {clave} y siguen abiertos los pasos "
                 f"{', '.join(map(str, abiertos))}. El checklist manda el orden: ciérralos con "
                 f"`ciclo.py paso {clave} <n> …` y vuelve a lanzarlo.")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        avisar(f"el candado de los encargos no pudo correr ({e}); revisa a mano el brief y el checklist.")
