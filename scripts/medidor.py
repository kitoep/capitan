#!/usr/bin/env python3
"""Medidor de uso del método Capitán, alimentado por la barra de estado de Claude Code.

Claude Code le pasa a la barra de estado un JSON por stdin con los límites de uso
de la cuenta (`rate_limits`) y el costo de la conversación (`cost`). Este script
lo lee y escribe dos archivos:

  ~/.claude/usage-now.json
      Uso de TODA la cuenta (5 h y semanal). Lo lee el colchón de uso de
      /capitan:trabajar para detenerse antes de agotar el plan.

  ~/.claude/capitan-sesiones/<ruta-del-proyecto>.json
      Consumo de ESTA conversación en ese proyecto: costo y duración exactos
      (los da Claude Code por sesión) y cuánto subió el % semanal desde que
      empezó (aproximado: incluye lo que se haga en paralelo en otra
      conversación). Lo lee el tablero local para medir sesiones y actividades.

Uso como envoltura de la barra de estado que ya tengas (no la reemplaza):
  statusLine.command = python3 ~/.claude/capitan/medidor.py -- <tu comando de barra>
Sin `--`, no imprime nada. Nunca falla: un error del medidor jamás rompe la barra.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys

CLAUDE = os.path.join(os.path.expanduser("~"), ".claude")
SESIONES = os.path.join(CLAUDE, "capitan-sesiones")
BASES = os.path.join(SESIONES, "_bases.json")
INACTIVA_S = 5 * 3600  # sin consumo por 5 h: la sesión retomada cuenta desde cero
MAX_BASES = 50


def _iso(ts) -> str | None:
    try:
        return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).isoformat()
    except Exception:
        return None


def _escribir(ruta: str, datos: dict) -> None:
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ruta)


def clave_proyecto(ruta: str) -> str:
    """La misma clave que calcula tablero.py desde el directorio del proyecto."""
    return re.sub(r"[^a-z0-9]+", "-", ruta.lower()).strip("-")


def delta_semanal(sid: str, semana: float | None) -> float | None:
    """Cuánto subió el % semanal desde que esta sesión empezó a consumir."""
    if semana is None:
        return None
    try:
        bases = json.load(open(BASES, encoding="utf-8"))
    except Exception:
        bases = {}
    ahora = dt.datetime.now(dt.timezone.utc).timestamp()
    b = bases.get(sid)
    if not b or ahora - b.get("visto", 0) > INACTIVA_S or semana < b.get("base", semana):
        b = {"base": semana, "previo": semana, "visto": ahora}  # nueva, retomada o reinicio semanal
    if semana != b.get("previo"):
        b["previo"], b["visto"] = semana, ahora
    bases[sid] = b
    if len(bases) > MAX_BASES:
        for viejo in sorted(bases, key=lambda k: bases[k].get("visto", 0))[: len(bases) - MAX_BASES]:
            bases.pop(viejo, None)
    _escribir(BASES, bases)
    return semana - b["base"]


def medir(j: dict) -> None:
    ahora = dt.datetime.now(dt.timezone.utc).isoformat()
    rl = j.get("rate_limits") or {}
    h5 = (rl.get("five_hour") or {}).get("used_percentage")
    wk = (rl.get("seven_day") or {}).get("used_percentage")
    if h5 is not None or wk is not None:
        _escribir(os.path.join(CLAUDE, "usage-now.json"), {
            "five_hour_pct": h5,
            "seven_day_pct": wk,
            "five_hour_resets_at": _iso((rl.get("five_hour") or {}).get("resets_at")),
            "seven_day_resets_at": _iso((rl.get("seven_day") or {}).get("resets_at")),
            "written_at": ahora,
        })
    sid = j.get("session_id")
    ws = j.get("workspace") or {}
    proyecto = ws.get("project_dir") or ws.get("current_dir") or j.get("cwd")
    if sid and proyecto:
        costo = j.get("cost") or {}
        _escribir(os.path.join(SESIONES, clave_proyecto(proyecto) + ".json"), {
            "session_id": sid,
            "project_dir": proyecto,
            "cost_usd": costo.get("total_cost_usd"),
            "duration_ms": costo.get("total_duration_ms"),
            "api_duration_ms": costo.get("total_api_duration_ms"),
            "week_delta_pct": delta_semanal(sid, wk),
            "written_at": ahora,
        })


def main() -> None:
    crudo = sys.stdin.buffer.read()
    try:
        medir(json.loads(crudo.decode("utf-8-sig")))
    except Exception:
        pass  # el medidor jamás rompe la barra de estado
    if "--" in sys.argv:
        comando = sys.argv[sys.argv.index("--") + 1:]
        if comando:
            r = subprocess.run(comando if len(comando) > 1 else comando[0], input=crudo,
                               capture_output=True, shell=len(comando) == 1)
            sys.stdout.buffer.write(r.stdout)


if __name__ == "__main__":
    main()
