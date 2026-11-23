#!/usr/bin/env python3
"""Corre el CI local del proyecto y, si pasa, deja constancia del commit.

Uso (desde la raíz del repo):
  python3 ci_local.py                    el CI completo
  python3 ci_local.py --areas [--base R] solo las áreas que toca la rama (paso 12)

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

Con `--areas` lee la tabla `## CI por área` de la config (área · rutas ·
comando) y corre solo las áreas cuyas rutas toca la rama desde que salió de la
principal (o de --base). Si un archivo tocado no cae en ningún área, corre el
CI completo: lo que no se sabe dónde va, se prueba todo. Lo que cae en docs/
no cuenta. Una corrida por área queda en el registro (evidencia del paso 12)
pero NO en ci-ok: el CI completo corre una vez sobre la rama de sesión antes
del PR, y eso es lo que exigen hook_push.py y hook_ciclo.py.

Nació el 2026-10-05: el PR de una sesión corrió el CI completo de GitHub tres
veces en una hora; una de ellas falló por un commit de docs subido sin correr
la suite local. Cada corrida se cobra en minutos de Actions.
"""
from __future__ import annotations

import argparse
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


def areas_ci(raiz: str) -> list[tuple[str, list[str], str]]:
    """Las filas de `## CI por área`: (área, rutas, comando)."""
    try:
        texto = open(os.path.join(raiz, ".claude", "capitan.md"), encoding="utf-8").read()
    except OSError:
        return []
    m = re.search(r"^## CI por área\s*$(.*?)(?=^## |\Z)", texto, re.M | re.S)
    filas = []
    for l in (m.group(1) if m else "").splitlines():
        celdas = [c.strip() for c in l.strip().strip("|").split("|")]
        if len(celdas) >= 3 and "`" in celdas[2]:
            rutas = re.findall(r"`([^`]+)`", celdas[1])
            cmd = re.search(r"`([^`]+)`", celdas[2]).group(1).strip()
            if rutas:
                filas.append((celdas[0], [r.rstrip("/") for r in rutas], cmd))
    return filas


def principal(raiz: str) -> str | None:
    for ref in ("origin/HEAD", "origin/main", "main", "origin/master", "master"):
        if subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref], cwd=raiz, capture_output=True).returncode == 0:
            return ref
    return None


def tocados(raiz: str, base: str) -> list[str] | None:
    """Los archivos de código que cambió la rama desde que salió de base. None si no se puede saber."""
    mb = subprocess.run(["git", "merge-base", "HEAD", base], cwd=raiz, capture_output=True, text=True)
    if mb.returncode != 0 or not mb.stdout.strip():
        return None
    d = subprocess.run(["git", "diff", "--no-renames", "--name-only", f"{mb.stdout.strip()}..HEAD"], cwd=raiz,
                       capture_output=True, text=True)
    if d.returncode != 0:
        return None
    return [f for f in d.stdout.splitlines() if f and not f.startswith("docs/")]


def elegir(filas, archivos: list[str]) -> tuple[list[tuple[str, list[str], str]], list[str]]:
    """(áreas tocadas, archivos que no caen en ningún área)."""
    elegidas, sueltos = [], []
    for f in archivos:
        cae = [a for a in filas if any(f == r or f.startswith(r + "/") for r in a[1])]
        if not cae:
            sueltos.append(f)
        for a in cae:
            if a not in elegidas:
                elegidas.append(a)
    return elegidas, sueltos


def dir_capitan(raiz: str) -> str:
    """En el directorio común de git: lo comparten todos los worktrees del repo."""
    comun = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=raiz,
                           capture_output=True, text=True).stdout.strip()
    return os.path.join(comun, "capitan")


def archivo_ok(raiz: str) -> str:
    return os.path.join(dir_capitan(raiz), "ci-ok")


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


def registrar(raiz: str, sha: str, cmd: str, ultimas: list[str], alcance: str = "completo") -> str:
    ruta = os.path.join(dir_capitan(raiz), "ci-registro.log")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(f"== {sha} · {dt.datetime.now():%Y-%m-%d %H:%M} · {alcance} · {cmd}\n" + "\n".join(ultimas) + "\n")
    return ruta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ci_local.py")
    ap.add_argument("--areas", action="store_true", help="solo las áreas que toca la rama (paso 12)")
    ap.add_argument("--base", help="desde dónde se cuentan los cambios (por omisión, la principal)")
    args = ap.parse_args(argv)
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
    corridas, alcance = [cmd], "completo"
    if args.areas:
        filas, base = areas_ci(raiz), args.base or principal(raiz)
        archivos = tocados(raiz, base) if base else None
        if not filas:
            print("ci_local: la config no trae `## CI por área`; corro el CI completo.", flush=True)
        elif not base:
            print("ci_local: no encuentro la rama principal para saber qué tocó esta rama; corro el CI completo.", flush=True)
        elif archivos is None:
            print(f"ci_local: no pude saber qué tocó esta rama desde `{base}` (¿existe? ¿comparten historia?); "
                  "corro el CI completo.", flush=True)
        else:
            elegidas, sueltos = elegir(filas, archivos)
            if sueltos:
                print("ci_local: estos archivos no caen en ningún área, así que corro el CI completo:\n  "
                      + "\n  ".join(sueltos[:10]), flush=True)
            elif not elegidas:
                corridas, alcance = [], "sin código (solo docs/)"
            else:
                corridas = [a[2] for a in elegidas]
                alcance = "áreas: " + ", ".join(a[0] for a in elegidas)
    ultimas: list[str] = []
    for c in corridas:
        print(f"ci_local: corriendo `{c}` sobre {sha[:10]}…", flush=True)
        codigo, salida, errores = correr(c, raiz)
        ultimas += salida
        if codigo != 0:
            print(f"ci_local: ROJO (salió {codigo}). No se sube.", file=sys.stderr)
            return codigo
        if errores:
            print("ci_local: ROJO aunque salió 0: la salida trae errores del shell, así que una parte no corrió.\n  "
                  + "\n  ".join(errores[:5]), file=sys.stderr)
            return 1
    if not corridas:
        ultimas = ["sin cambios de código desde la principal: no hay suite que correr"]
    ahora = subprocess.run(["git", "rev-parse", "HEAD"], cwd=raiz, capture_output=True, text=True).stdout.strip()
    if ahora != sha:
        print("ci_local: HEAD cambió mientras corría; vuelve a correrlo.", file=sys.stderr)
        return 2
    if alcance == "completo":
        ruta = archivo_ok(raiz)
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(sha + "\n")
    registro = registrar(raiz, sha, " && ".join(corridas) or "-", ultimas[-ULTIMAS:], alcance)
    listo = "Ya se puede subir." if alcance == "completo" else "El CI completo corre una vez sobre la rama de sesión, antes del PR."
    print(f"ci_local: VERDE ({alcance}) sobre {sha[:10]}. {listo}\n"
          f"ci_local: evidencia del paso 12 (copia el conteo literal de aquí, registrado en {os.path.relpath(registro, raiz)}):\n  "
          + "\n  ".join(ultimas[-5:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
