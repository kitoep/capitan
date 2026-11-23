#!/usr/bin/env python3
"""Hook PreToolUse de las herramientas MCP (plugin capitan). Con un tracker
externo, el checklist del ciclo no tiene candado propio: este lo pone en el
momento en que más importa, cuando una tarjeta pasa a Revisión de código.

Lee de la sección `## Tracker` de .claude/capitan.md cuál herramienta es
«Mover» y qué valor tiene la columna «Revisión de código». Si la llamada es
esa herramienta con ese destino, exige que el relevo esté al día:

  1. docs/capitan/estado.md se modificó DESPUÉS del merge de la actividad a la
     rama de sesión (paso 13): el relevo (paso 15) va antes de documentar.
  2. su línea de la actividad trae la hora de inicio y de cierre
     (HH:MM → HH:MM) y el uso gastado: la medición se hace con el reloj, no
     se reconstruye de los commits.
  3. el checklist del ciclo (ciclo.py) tiene cerrados los pasos 1 al 15: el
     hook no puede leer las subtareas del tracker, pero sí el checklist local
     del que el tracker es espejo.

Nació de una sesión real: de tres actividades, ninguna tuvo hora ni uso
medidos y el relevo solo se escribió al final.

Si no puede leer la config, o no encuentra el merge de la actividad, NO
bloquea: avisa en pantalla. Lo que no puede comprobar no lo inventa."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

CLAVE = re.compile(r"\b(?:[A-Z][A-Z0-9]*-\d+/)?(ACT-\d+)\b")
RANGO = re.compile(r"\b\d{1,2}:\d{2}\s*(?:→|->)\s*\d{1,2}:\d{2}\b")


def seccion_tracker(texto: str) -> str | None:
    m = re.search(r"^## Tracker\s*$(.*?)(?=^## |\Z)", texto, re.M | re.S)
    return m.group(1) if m else None


def celda(seccion: str, primera: str) -> str | None:
    """El valor entre backticks de la fila cuya primera celda empieza con `primera`."""
    m = re.search(rf"^\|\s*{primera}[^|]*\|\s*`([^`]+)`", seccion, re.M | re.I)
    return m.group(1).strip() if m else None


def textos(x) -> list[str]:
    if isinstance(x, str):
        return [x]
    if isinstance(x, dict):
        return [t for v in x.values() for t in textos(v)]
    if isinstance(x, list):
        return [t for v in x for t in textos(v)]
    return [str(x)] if isinstance(x, (int, float)) else []


def git(cwd: str, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True).stdout.strip()


def merge_de(cwd: str, clave: str | None) -> tuple[str, int] | None:
    """El merge más reciente de la rama actual (el de `clave` si se sabe): (clave, segundos)."""
    for linea in git(cwd, "log", "--merges", "-n", "200", "--format=%ct%x09%s").splitlines():
        ct, _, asunto = linea.partition("\t")
        m = CLAVE.search(asunto)
        if m and (clave is None or m.group(1) == clave):
            return m.group(1), int(ct)
    return None


def linea_de(estado: str, clave: str) -> str | None:
    m = re.search(r"^## Dónde quedó\s*$(.*?)(?=^## |\Z)", estado, re.M | re.S)
    for l in (m.group(1) if m else estado).splitlines():
        if re.search(rf"\b{re.escape(clave)}\b", l):
            return l
    return None


def aviso_config(texto: str) -> str | None:
    """Si `## Tracker` existe pero no trae la forma que este candado lee, el candado
    queda apagado sin hacer ruido: hook_inicio lo dice al abrir la sesión."""
    sec = seccion_tracker(texto)
    if sec is None:
        return None  # tablero local: el candado es el de tablero.py
    faltan = [f"«{n}»" for n in ("Mover", "Revisión de código") if not celda(sec, n)]
    if not faltan:
        return None
    return ("el candado del tracker está APAGADO en este proyecto: la sección `## Tracker` de "
            f".claude/capitan.md no trae {' ni '.join(faltan)} con la herramienta o el valor entre "
            "backticks, así que nada revisa el relevo y la medición antes de pasar una tarjeta a "
            "Revisión de código. Corre el Paso 2 de /capitan:configurar para dejarla en forma.")


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
    cwd = datos.get("cwd") or os.getcwd()
    herramienta = datos.get("tool_name") or ""
    config = os.path.join(cwd, ".claude", "capitan.md")
    if not herramienta.startswith("mcp__") or not os.path.exists(config):
        sys.exit(0)
    try:
        sec = seccion_tracker(open(config, encoding="utf-8").read())
    except OSError:
        sys.exit(0)
    if sec is None:
        sys.exit(0)  # tablero local o config vieja: trabajar ya se detiene sin ## Tracker
    mover = celda(sec, "Mover")
    if not mover or not (herramienta == mover or herramienta.endswith("__" + mover)):
        sys.exit(0)
    revision = celda(sec, "Revisión de código")
    if not revision:
        avisar("no encuentro el valor de «Revisión de código» en ## Tracker de .claude/capitan.md; "
               "no puedo revisar el relevo antes de mover. Corre el Paso 2 de /capitan:configurar.")
    entrada = textos(datos.get("tool_input") or {})
    if not any(t.strip().lower() == revision.lower() for t in entrada):
        sys.exit(0)

    claves = sorted({m.group(1) for t in entrada for m in CLAVE.finditer(t)})
    merge = merge_de(cwd, claves[0] if len(claves) == 1 else None)
    if not merge:
        avisar("vas a pasar una tarjeta a Revisión de código y no encuentro el merge de su actividad en esta rama "
               "(`Merge …/ACT-0xx`); revisa a mano que estado.md y la medición estén al día.")
    clave, cuando = merge
    ruta = os.path.join(cwd, "docs", "capitan", "estado.md")
    if not os.path.exists(ruta):
        bloquear(f"Bloqueado: no existe docs/capitan/estado.md. El relevo (paso 15) va antes de pasar {clave} "
                 "a Revisión de código (paso 16).")
    if os.path.getmtime(ruta) < cuando:
        bloquear(f"Bloqueado: docs/capitan/estado.md no se reescribió después del merge de {clave}. "
                 "El relevo (paso 15) va antes de documentar en el tracker (paso 16): reescríbelo y vuelve a mover.")
    linea = linea_de(open(ruta, encoding="utf-8").read(), clave)
    if not linea or not RANGO.search(linea) or "uso" not in linea.lower():
        bloquear(f"Bloqueado: en docs/capitan/estado.md («## Dónde quedó») la línea de {clave} debe traer la hora "
                 "de inicio y de cierre (HH:MM → HH:MM) y el uso gastado, medidos con el reloj y el medidor, "
                 "no reconstruidos de los commits. Agrégala y vuelve a mover.")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ciclo
    try:
        c = ciclo.leer(cwd, clave)
    except (OSError, ValueError) as e:
        avisar(f"no pude leer el checklist de {clave} ({e}); revisa a mano que los pasos 1 al 15 estén cerrados, "
               "y anótalo en docs/capitan/aprendizajes.md.")
    if c is None:
        bloquear(f"Bloqueado: {clave} no tiene checklist del ciclo (`ciclo.py crear {clave}`, paso 2), así que nada "
                 "dice que sus pasos se hicieron. Créalo y ciérralos antes de pasarla a Revisión de código.")
    abiertos = ciclo.abiertos_hasta(c, len(c["pasos"]) - 1)
    if abiertos:
        bloquear(f"Bloqueado: el checklist de {clave} tiene abiertos los pasos {', '.join(map(str, abiertos))}. "
                 f"Pasar a Revisión de código es el último paso: antes van cerrados los demás (`ciclo.py ver {clave}`).")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        avisar(f"el candado del tracker no pudo correr ({e}); revisa a mano el relevo antes de mover.")
