#!/usr/bin/env python3
"""Juez de decisiones (plugin capitan). Lee lo que el dueño escribió en la
conversación desde la última revisión y le pregunta a un modelo (Sonnet)
si dijo alguna decisión que no esté en docs/capitan/decisiones.md.

Corre al cerrar una actividad (antes del `git merge` a la rama de sesión) y al
cerrar la sesión (antes de `gh pr create`), llamado por hook_cierre.py. No
corre en cada mensaje: cada llamada gasta uso del dueño.

Sale con la lista de decisiones faltantes (vacía = todo registrado). Solo
avanza su marca cuando no falta nada: si faltan, la siguiente revisión vuelve a
ver los mismos mensajes y comprueba que ya quedaron escritas.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile

TOPE_RESPUESTA = 5000  # lo que se toma de la respuesta previa: da contexto al «sí, así»
TOPE_MENSAJES = 40000  # tamaño de cada parte que se manda al juez
# Sonnet y no Haiku: con la conversación del 2026-10-02 Haiku dejó pasar dos
# aprobaciones cortas («sí, así», «va») y Sonnet atrapó las seis (15 s contra
# 6 s). Corre pocas veces por sesión, así que vale la diferencia.
MODELO = os.environ.get("CAPITAN_JUEZ_MODELO", "sonnet")

INSTRUCCIONES = """Eres el registrador de decisiones de un proyecto de software. El DUEÑO del
proyecto conversa con un asistente. Una DECISIÓN es algo que el dueño
establece y que cambia cómo se trabaja o cómo debe ser el producto DE AQUÍ EN
ADELANTE: una regla, un criterio, un nombre, un alcance, una prioridad, un
«esto no», una corrección de cómo se entendió algo («no apaga el sistema,
apaga la key»). Cuenta también cuando el dueño aprueba una propuesta del
asistente («sí, así», «adelante con eso»): la decisión es lo aprobado, que se
lee en la respuesta previa (una aprobación corta como «va», «sí, así»,
«adelante» sobre una propuesta de cómo trabajar o construir algo ES una
decisión: regístrala con el contenido de la propuesta).

Revisa los mensajes UNO POR UNO; no te detengas en el primero que encuentres.

Solo cuentan las decisiones sobre ESTE proyecto ({proyecto}). Las que son
sobre otro proyecto o sobre las herramientas de trabajo (el método o plugin
«Capitán», skills, hooks, la configuración de Claude) NO van en este archivo:
no las cuentes.

NO son decisiones: preguntas, peticiones de una tarea puntual («crea una api
key y prueba»), quejas sin regla, saludos, ni ajustes cosméticos de un solo
uso («ponle azul» a un botón ya hecho).

Abajo vienen (1) el archivo de decisiones ya registradas y (2) los mensajes
nuevos del dueño, cada uno con la respuesta del asistente que lo precedió.
Devuelve SOLO un JSON, sin texto alrededor:
{"faltan": [{"decision": "<la decisión en una línea, en español llano>", "cita": "<las palabras del dueño, textuales y cortas>"}]}
Una decisión que ya está registrada, aunque con otras palabras, NO falta. Si
no falta nada: {"faltan": []}."""


def _texto(contenido) -> str:
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, list):
        return "\n".join(x.get("text", "") for x in contenido if isinstance(x, dict) and x.get("type") == "text")
    return ""


def mensajes_del_dueño(transcript: str, desde: str | None) -> tuple[list[dict], str | None]:
    """Los mensajes que escribió una persona (no los de herramientas, sistema,
    resúmenes ni subagentes), con la última respuesta del asistente previa."""
    pares, previa, ultimo = [], "", desde
    with open(transcript, encoding="utf-8") as f:
        for linea in f:
            try:
                d = json.loads(linea)
            except ValueError:
                continue
            if d.get("isSidechain"):
                continue
            tipo, ts = d.get("type"), d.get("timestamp") or ""
            contenido = (d.get("message") or {}).get("content")
            if tipo == "assistant":
                t = _texto(contenido).strip()
                if t:
                    previa = t
                continue
            if tipo != "user" or d.get("isMeta") or d.get("isCompactSummary"):
                continue
            if isinstance(contenido, list) and any(isinstance(x, dict) and x.get("type") == "tool_result" for x in contenido):
                continue
            t = _texto(contenido).strip()
            if not t or t.startswith("<") or (desde and ts <= desde):
                continue
            pares.append({"cuando": ts, "previa": previa[-TOPE_RESPUESTA:], "dueño": t})
            ultimo = max(ultimo or "", ts)
    return pares, ultimo


def marca_path(session_id: str) -> str:
    base = os.environ.get("CLAUDE_PLUGIN_DATA") or os.path.join(os.path.expanduser("~"), ".cache", "capitan")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, f"juez-{session_id}.json")


def _preguntar(prompt: str) -> list[dict]:
    # Corre fuera del repo: sin .claude/capitan.md los hooks del plugin no se
    # encienden en la llamada interna (no hay recursión ni relevo inyectado).
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run(
            # shutil.which: en Windows `claude` es claude.cmd y subprocess no lo
            # encuentra por nombre pelón.
            [shutil.which("claude") or "claude", "-p", "--model", MODELO, "--output-format", "json"],
            input=prompt, capture_output=True, text=True, encoding="utf-8", timeout=150, cwd=tmp,
        )
    if r.returncode != 0:
        raise RuntimeError(f"claude -p salió con {r.returncode}: {r.stderr.strip()[:300]}")
    salida = json.loads(r.stdout).get("result", "")
    inicio, fin = salida.find("{"), salida.rfind("}")
    return json.loads(salida[inicio:fin + 1]).get("faltan", [])


def revisar(cwd: str, transcript: str, session_id: str, otras_ramas: list[str] | None = None) -> list[dict]:
    """Devuelve las decisiones faltantes. Lanza RuntimeError si el juez no pudo correr.

    `otras_ramas`: las que el comando está mergeando. Sus decisiones cuentan
    como registradas: llegan con el merge (falso positivo del 2026-10-05)."""
    marca = marca_path(session_id)
    desde = json.load(open(marca)).get("hasta") if os.path.exists(marca) else None
    pares, hasta = mensajes_del_dueño(transcript, desde)
    if not pares:
        return []
    ruta_dec = os.path.join(cwd, "docs", "capitan", "decisiones.md")
    registradas = open(ruta_dec, encoding="utf-8").read() if os.path.exists(ruta_dec) else "(vacío)"
    for rama in otras_ramas or []:
        r = subprocess.run(["git", "show", f"{rama}:docs/capitan/decisiones.md"], cwd=cwd, capture_output=True, text=True)
        if r.returncode == 0:
            registradas += f"\n\n=== decisiones.md de la rama que se mergea ({rama}) ===\n" + r.stdout
    bloques = [f"--- Respuesta previa del asistente ---\n{p['previa']}\n--- El dueño ({p['cuando']}) ---\n{p['dueño']}" for p in pares]
    # En partes, nunca recortado: un tramo largo (muchos mensajes desde la
    # última revisión) se revisa completo, una llamada por parte.
    partes, actual = [], ""
    for b in bloques:
        if actual and len(actual) + len(b) > TOPE_MENSAJES:
            partes.append(actual)
            actual = ""
        actual += b[-TOPE_MENSAJES:] + "\n\n"
    partes.append(actual)
    instrucciones = INSTRUCCIONES.replace("{proyecto}", os.path.basename(os.path.abspath(cwd)))
    faltan: list[dict] = []
    for nuevos in partes:
        faltan += _preguntar(f"{instrucciones}\n\n=== (1) decisiones.md ===\n{registradas}\n\n=== (2) mensajes nuevos ===\n{nuevos}")
    if not faltan:
        json.dump({"hasta": hasta}, open(marca, "w"))
    return faltan
