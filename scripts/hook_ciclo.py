#!/usr/bin/env python3
"""Hook PreToolUse de Bash (plugin capitan). Lee el checklist del ciclo
(ciclo.py) en dos puertas, para que no dependa de la memoria del agente:

  `git merge <rama de actividad>` a la rama de sesión (paso 13):
      los pasos 1–12 cerrados, y el probador (10), la seguridad del diff (11)
      y el CI (12) sobre el último commit de código de la rama.

  `gh pr create` (al cerrar la sesión):
      cada actividad mergeada en la rama de sesión con su checklist 16/16 y su
      copia en docs/capitan/ciclo/ dentro del commit, y el CI COMPLETO pasado
      sobre ese commit (ci_local.py sin --areas).

Si no puede leer un checklist que existe, avisa y no bloquea. Un checklist que
no existe sí bloquea: crearlo es el paso 2."""
from __future__ import annotations

import json
import os
import re
import shlex
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ciclo  # noqa: E402
import ci_local  # noqa: E402

RAMA_ACT = re.compile(r"(?:^|[-_/])act-?(\d+)(?:[-_/]|$)", re.I)
SEPARADORES = re.compile(r"&&|\|\||;|\||\n")
HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?\n\s*\1\s*(?=\n|$)", re.S)
GLOBALES_CON_VALOR = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
MERGE_CON_VALOR = {"-m", "-F", "--file", "-s", "--strategy", "-X", "--strategy-option"}
SHELLS = {"bash", "sh", "zsh", "dash"}


def avisar(msg: str) -> None:
    print(json.dumps({"systemMessage": f"capitan: {msg}"}, ensure_ascii=False))
    sys.exit(0)


def bloquear(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


def comandos(comando: str, cwd: str):
    """(directorio, programa, argumentos) de cada `git` y `gh` que de verdad corre el comando.
    Sigue `cd` y `git -C`; el texto de mensajes, comillas y heredocs no cuenta."""
    actual = cwd
    for frag in SEPARADORES.split(HEREDOC.sub("", comando)):
        try:
            partes = shlex.split(frag, comments=True)
        except ValueError:
            continue  # un pedazo de texto entre comillas, no un comando
        while partes and re.match(r"^[A-Za-z_]\w*=", partes[0]):
            partes.pop(0)  # VAR=valor delante del comando
        if not partes:
            continue
        prog = os.path.basename(partes[0].lstrip("\\"))
        if prog == "cd" and len(partes) > 1:
            actual = os.path.join(actual, os.path.expanduser(partes[1]))
        elif prog in SHELLS and len(partes) > 2 and partes[1] == "-c":
            yield from comandos(partes[2], actual)
        elif prog == "git":
            resto, d, k = partes[1:], actual, 0
            while k < len(resto) and resto[k].startswith("-"):
                if resto[k] == "-C" and k + 1 < len(resto):
                    d = os.path.join(d, os.path.expanduser(resto[k + 1]))
                k += 2 if resto[k] in GLOBALES_CON_VALOR else 1
            if k < len(resto):
                yield d, "git", resto[k:]
        elif prog == "gh":
            yield actual, "gh", partes[1:]


def ramas_y_mensaje(args: list[str]) -> tuple[list[str], str]:
    """De los argumentos de `git merge …`: las ramas y el mensaje (-m)."""
    ramas, mensaje, k = [], "", 0
    while k < len(args):
        a = args[k]
        if a in MERGE_CON_VALOR:
            if a == "-m" and k + 1 < len(args):
                mensaje = args[k + 1]
            k += 2
            continue
        if a.startswith("-m") and len(a) > 2:
            mensaje = a[2:]
        elif not a.startswith("-"):
            ramas.append(a)
        k += 1
    return ramas, mensaje


def clave_de(cwd: str, rama: str, mensaje: str) -> str | None:
    """La actividad de una rama: la que registró esa rama en el paso 1 de su checklist; si no, el
    número del nombre (comparado como número); si no, la clave del mensaje del merge."""
    try:
        carpeta = ciclo.dir_vivo(cwd)
        archivos = sorted(f for f in os.listdir(carpeta) if f.endswith(".json"))
    except (OSError, ciclo.Rechazo):
        archivos = []
    for f in archivos:
        try:
            with open(os.path.join(carpeta, f), encoding="utf-8") as h:
                c = json.load(h)
            if (ciclo.paso_de(c, 1).get("dato") or {}).get("rama") == rama:
                return c["clave"]
        except (OSError, ValueError, KeyError, ciclo.Rechazo):
            continue
    m = RAMA_ACT.search(rama)
    if m:
        numero = int(m.group(1))
        for f in archivos:
            if re.fullmatch(r"ACT-\d+\.json", f) and int(f[4:-5]) == numero:
                return f[:-5]
        return f"ACT-{numero:03d}"
    m = ciclo.CLAVE.search(mensaje or "")
    return m.group(1) if m else None


def checklist(cwd: str, clave: str, para: str) -> dict:
    try:
        c = ciclo.leer(cwd, clave)
    except (OSError, ValueError) as e:
        avisar(f"no pude leer el checklist de {clave} ({e}); revisa a mano que esté al día antes de {para}, "
               "y anótalo en docs/capitan/aprendizajes.md.")
    if c is None:
        bloquear(f"Bloqueado: {clave} no tiene checklist del ciclo (`ciclo.py crear {clave}`, paso 2). "
                 f"Sin checklist no hay {para}. Si es una actividad anterior a la 0.9.0, créalo y cierra los pasos "
                 "que ya pasaron con su evidencia, o como omitidos con el permiso escrito del dueño.")
    return c


def revisar_merge(cwd: str, args: list[str]) -> None:
    actual = ciclo.sale(cwd, "branch", "--show-current")
    if "-sesion-" not in actual:
        return  # solo el merge de una actividad a la rama de sesión
    ramas, mensaje = ramas_y_mensaje(args)
    prin = (ciclo.principal(cwd) or "").removeprefix("origin/")
    for rama in ramas:
        punta = ciclo.commit(cwd, rama)
        if not punta or rama.removeprefix("origin/") in (prin, "main", "master"):
            continue
        clave = clave_de(cwd, rama, mensaje if len(ramas) == 1 else "")
        if not clave:
            avisar(f"vas a mergear `{rama}` a la rama de sesión y no sé de qué actividad es (ni su checklist ni su "
                   "nombre ni el mensaje traen la clave); revisa a mano su checklist.")
        c = checklist(cwd, clave, "merge")
        abiertos = ciclo.abiertos_hasta(c, 12)
        problemas = ([f"pasos abiertos: {', '.join(map(str, abiertos))} (antes del merge van cerrados del 1 al 12)."]
                     if abiertos else [])
        problemas += ciclo.faltan_revisiones(cwd, c, punta)
        if problemas:
            bloquear(f"Bloqueado: el merge de {clave} a la rama de sesión.\n- " + "\n- ".join(problemas)
                     + "\nSi un revisor provoca un cambio, el otro revisa ese cambio antes de cerrar su paso. "
                       f"`ciclo.py ver {clave}` muestra el checklist.")


def revisar_pr(cwd: str) -> None:
    base = ciclo.principal(cwd)
    if not base:
        avisar("no encuentro la rama principal para revisar los checklists antes del PR; revísalos a mano.")
    problemas = []
    claves = []
    # --first-parent: solo los merges de ESTA sesión, aunque la principal local esté atrasada.
    for asunto in ciclo.sale(cwd, "log", "--first-parent", "--merges", "--format=%s", f"{base}..HEAD").splitlines():
        m = ciclo.CLAVE.search(asunto)
        if m and m.group(1) not in claves:
            claves.append(m.group(1))
    for clave in claves:
        c = checklist(cwd, clave, "PR")
        abiertos = ciclo.abiertos_hasta(c, len(c["pasos"]))
        if abiertos:
            problemas.append(f"{clave}: pasos abiertos {', '.join(map(str, abiertos))}.")
        elif ciclo.git(cwd, "cat-file", "-e", f"HEAD:docs/capitan/ciclo/{clave}.json").returncode:
            problemas.append(f"{clave}: falta docs/capitan/ciclo/{clave}.json en el commit (ciclo.py la escribe al "
                             "cerrar el 16; súmala al commit del relevo).")
    sha = ciclo.commit(cwd, "HEAD")
    if not ci_local.comando_ci(ciclo.raiz(cwd)):
        if problemas:
            bloquear("Bloqueado: el PR de la sesión.\n- " + "\n- ".join(problemas))
        avisar("la config no nombra su `| CI local |`: corre el CI completo a mano antes del PR.")
    try:
        with open(ci_local.archivo_ok(cwd), encoding="utf-8") as f:
            verdes = set(f.read().split())
    except OSError:
        verdes = set()
    if sha not in verdes:
        problemas.append(f"el CI completo no ha pasado sobre {sha[:9]}: corre `ci_local.py` (sin --areas) en la rama "
                         "de sesión. Es la única corrida completa de la sesión.")
    if problemas:
        bloquear("Bloqueado: el PR de la sesión.\n- " + "\n- ".join(problemas))


def main() -> None:
    try:
        datos = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    cwd = datos.get("cwd") or os.getcwd()
    comando = (datos.get("tool_input") or {}).get("command") or ""
    for d, prog, args in comandos(comando, cwd):
        if not os.path.exists(os.path.join(ciclo.raiz(d), ".claude", "capitan.md")):
            continue  # el repo donde corre (con -C o cd) no usa el método
        if prog == "git" and args[0] == "merge" and not {"--abort", "--continue", "--quit"} & set(args):
            revisar_merge(d, args[1:])
        elif prog == "gh" and args[:2] == ["pr", "create"]:
            revisar_pr(d)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        avisar(f"el candado del checklist no pudo correr ({e}); revisa a mano el checklist antes de seguir, "
               "y anótalo en docs/capitan/aprendizajes.md.")
