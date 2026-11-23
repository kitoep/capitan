#!/usr/bin/env python3
"""Corre el CI local del proyecto y, si pasa, deja constancia del commit.

Uso (desde la raíz del repo):
  python3 ci_local.py

Lee el comando de la fila `| CI local | `<comando>` |` de .claude/capitan.md,
exige el árbol limpio (sin cambios sin commit: lo que se prueba tiene que ser
exactamente lo que se sube) y, si sale 0, escribe el SHA de HEAD en
.git/capitan/ci-ok. `hook_push.py` no deja subir una rama con PR abierto si
su commit no está ahí.

Además guarda en .git/capitan/ci-registro.log, por commit, el comando y las
últimas líneas de su salida: esa es la evidencia del paso 12 del ciclo (el
conteo literal, p. ej. «412 passed»), nunca un «todo verde» de memoria. Y si la
salida trae errores del propio shell (comando no encontrado, error de
sintaxis), no lo da por verde aunque salga 0: parte de la suite no corrió.

Nació el 2026-10-05: el PR de una sesión corrió el CI completo de GitHub tres
veces en una hora; una de ellas falló por un commit de docs subido sin correr
la suite local. Cada corrida se cobra en minutos de Actions.
"""
from __future__ import annotations

import collections
import datetime as dt
import os
import re
import subprocess
import sys

# Mensajes del shell, no de las pruebas: si aparecen, una parte no corrió.
ERROR_SHELL = re.compile(r"^(?:/bin/)?(?:sh|bash|zsh|dash)(?:: line \d+)?: |: command not found\b|: [Ss]yntax error\b")
ULTIMAS = 15


def comando_ci(raiz: str) -> str | None:
    try:
        texto = open(os.path.join(raiz, ".claude", "capitan.md"), encoding="utf-8").read()
    except OSError:
        return None
    m = re.search(r"^\|\s*CI local\s*\|\s*`([^`]+)`", texto, re.MULTILINE)
    return m.group(1).strip() if m else None


def archivo_ok(raiz: str) -> str:
    git_dir = subprocess.run(["git", "rev-parse", "--absolute-git-dir"], cwd=raiz, capture_output=True, text=True).stdout.strip()
    return os.path.join(git_dir, "capitan", "ci-ok")


def correr(cmd: str, raiz: str) -> tuple[int, list[str], list[str]]:
    """Corre el CI mostrando la salida en vivo; devuelve (código, últimas líneas, errores del shell)."""
    proc = subprocess.Popen(cmd, shell=True, cwd=raiz, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    ultimas: collections.deque[str] = collections.deque(maxlen=ULTIMAS)
    errores = []
    for linea in proc.stdout:
        sys.stdout.write(linea)
        sys.stdout.flush()
        linea = linea.rstrip("\n")
        if linea.strip():
            ultimas.append(linea)
        if ERROR_SHELL.search(linea):
            errores.append(linea)
    return proc.wait(), list(ultimas), errores


def registrar(raiz: str, sha: str, cmd: str, ultimas: list[str]) -> str:
    ruta = os.path.join(os.path.dirname(archivo_ok(raiz)), "ci-registro.log")
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(f"== {sha} · {dt.datetime.now():%Y-%m-%d %H:%M} · {cmd}\n" + "\n".join(ultimas) + "\n")
    return ruta


def main() -> int:
    raiz = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
    if not raiz:
        print("ci_local: no estoy dentro de un repo de git.", file=sys.stderr)
        return 2
    cmd = comando_ci(raiz)
    if not cmd:
        print("ci_local: falta la fila `| CI local | `<comando>` |` en .claude/capitan.md.", file=sys.stderr)
        return 2
    # Con archivos sin seguimiento también: un módulo o test nuevo sin `git add`
    # pasa aquí y falla en GitHub (revisión de seguridad, 2026-10-05).
    sucio = subprocess.run(["git", "status", "--porcelain"], cwd=raiz, capture_output=True, text=True).stdout
    if sucio.strip():
        print("ci_local: hay cambios sin commit o archivos sin seguimiento. Haz commit (o agrégalos a .gitignore) "
              "primero: se prueba exactamente lo que se sube.\n" + sucio, file=sys.stderr)
        return 2
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=raiz, capture_output=True, text=True).stdout.strip()
    print(f"ci_local: corriendo `{cmd}` sobre {sha[:10]}…", flush=True)
    codigo, ultimas, errores = correr(cmd, raiz)
    if codigo != 0:
        print(f"ci_local: ROJO (salió {codigo}). No se sube.", file=sys.stderr)
        return codigo
    if errores:
        print("ci_local: ROJO aunque salió 0: la salida trae errores del shell, así que una parte no corrió.\n  "
              + "\n  ".join(errores[:5]), file=sys.stderr)
        return 1
    ahora = subprocess.run(["git", "rev-parse", "HEAD"], cwd=raiz, capture_output=True, text=True).stdout.strip()
    if ahora != sha:
        print("ci_local: HEAD cambió mientras corría; vuelve a correrlo.", file=sys.stderr)
        return 2
    ruta = archivo_ok(raiz)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(sha + "\n")
    registro = registrar(raiz, sha, cmd, ultimas)
    print(f"ci_local: VERDE sobre {sha[:10]}. Ya se puede subir.\n"
          f"ci_local: evidencia del paso 12 (copia el conteo literal de aquí, registrado en {os.path.relpath(registro, raiz)}):\n  "
          + "\n  ".join(ultimas[-5:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
