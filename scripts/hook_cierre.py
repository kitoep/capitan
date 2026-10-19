#!/usr/bin/env python3
"""Hook PreToolUse de Bash (plugin capitan). Antes de cerrar una actividad
(`git merge` en la sesión principal) o la sesión (`gh pr create`), corre el
juez de decisiones: si el dueño dijo algo que no está en
docs/capitan/decisiones.md, bloquea hasta que se registre.

Si el juez no puede correr (sin red, sin `claude`), NO bloquea: avisa al dueño
en pantalla. Un registro de documentación no debe detener la entrega."""
import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import juez_decisiones  # noqa: E402

try:
    datos = json.load(sys.stdin)
except Exception:
    sys.exit(0)
cwd = datos.get("cwd") or os.getcwd()
comando = (datos.get("tool_input") or {}).get("command") or ""
if datos.get("agent_id") or not os.path.exists(os.path.join(cwd, ".claude", "capitan.md")):
    sys.exit(0)
if not re.search(r"(^|[;&|(\s])(git\s+merge\b(?!\s+--abort)|gh\s+pr\s+create\b)", comando):
    sys.exit(0)
transcript, sesion = datos.get("transcript_path"), datos.get("session_id")
if not transcript or not sesion or not os.path.exists(transcript):
    sys.exit(0)
try:
    # Las ramas que se mergean: sus decisiones llegan con el merge.
    ramas: list[str] = []
    m = re.search(r"git\s+merge\b(.*)", comando, re.DOTALL)
    args = []
    if m:
        lex = shlex.shlex(m.group(1), posix=True, punctuation_chars=True)
        try:
            for tok in lex:
                if tok in ("&&", "||", ";", "|", "&") or tok.startswith((">", "<")):
                    if args and args[-1].isdigit():
                        args.pop()  # el «2» de «2>&1»
                    break
                args.append(tok)
        except ValueError:
            args = []
    k = 0
    while k < len(args):
        if args[k] in ("-m", "-F", "--file", "-s", "--strategy", "-X", "--strategy-option"):
            k += 2
            continue
        if not args[k].startswith("-"):
            ramas.append(args[k])
        k += 1
    faltan = juez_decisiones.revisar(cwd, transcript, sesion, ramas)
except Exception as e:  # noqa: BLE001
    print(json.dumps({"systemMessage": f"capitan: el juez de decisiones no pudo correr ({e}); revisa a mano que docs/capitan/decisiones.md esté al día."}))
    sys.exit(0)
if not faltan:
    sys.exit(0)
lineas = "\n".join(f"- {f.get('decision')}  (el dueño: «{f.get('cita')}»)" for f in faltan)
print(
    "Bloqueado por el juez de decisiones: el dueño decidió esto y no está en docs/capitan/decisiones.md.\n"
    f"{lineas}\n"
    "Regístralas (fecha, qué, por qué, a qué aplica) — o, si el juez se equivocó y no es una decisión, "
    "anótalo en docs/capitan/aprendizajes.md como falso positivo — y vuelve a correr el comando.",
    file=sys.stderr,
)
sys.exit(2)
