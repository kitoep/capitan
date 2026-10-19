#!/usr/bin/env python3
"""Hook PreToolUse de Bash (plugin capitan). No deja hacer `git push` a una
rama que tiene un PR abierto si el CI local no pasó sobre ESE commit
(`ci_local.py` lo anota en .git/capitan/ci-ok).

Por qué solo con PR abierto: subir una rama sin PR no dispara el CI de GitHub
(el método sube las ramas de actividad sin PR), así que no gasta. Con PR
abierto, cada push corre el CI completo y se cobra.

Nació el 2026-10-05: el PR de una sesión corrió el CI tres veces en una hora;
una falló por un commit de docs subido sin la suite local.

Reconoce el push en cualquier parte del comando (`a && git push`, saltos de
línea, `git -C dir push`, `/usr/bin/git`, `\\git`, `bash -c '…'`), con
`HEAD:rama`, `+rama`, `refs/heads/rama`, varias ramas y `--all`/`--mirror`.
Si no puede leer el comando, bloquea. Si no puede preguntarle a GitHub qué
PRs hay (sin `gh`, sin red), avisa y deja pasar: es una red contra descuidos,
no contra un atacante, y sin red tampoco hay push."""
import json
import os
import re
import shlex
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ci_local  # noqa: E402

SEPARADORES = r"&&|\|\||;|\||\n|\$\(|`"
GLOBALES_CON_VALOR = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
PUSH_CON_VALOR = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
TODAS = {"--all", "--mirror", "--branches"}
SHELLS = {"bash", "sh", "zsh", "dash"}


class Ilegible(Exception):
    pass


def pushes(comando: str, base: str):
    """Cada `git push` del comando: (directorio del repo, argumentos del push)."""
    for frag in re.split(SEPARADORES, comando):
        if "push" not in frag:
            continue
        try:
            partes = shlex.split(frag, comments=True)
        except ValueError as e:
            raise Ilegible(str(e)) from e
        for i, p in enumerate(partes):
            nombre = os.path.basename(p.lstrip("\\"))
            if nombre in SHELLS and i + 2 < len(partes) and partes[i + 1] == "-c":
                yield from pushes(partes[i + 2], base)
                break
            if nombre != "git":
                continue
            resto, repo, j = partes[i + 1:], base, 0
            while j < len(resto) and resto[j].startswith("-"):
                if resto[j] == "-C" and j + 1 < len(resto):
                    repo = os.path.join(repo, resto[j + 1])
                j += 2 if resto[j] in GLOBALES_CON_VALOR else 1
            if j < len(resto) and resto[j] == "push":
                yield repo, resto[j + 1:]
            break


def destinos(repo: str, args: list[str], abiertas: set[str]):
    """(commit que se sube, rama remota que lo recibe) de un `git push`."""
    banderas, posicionales, k = set(), [], 0
    while k < len(args):
        a = args[k]
        if a in PUSH_CON_VALOR:
            k += 2
            continue
        if a.startswith("-"):
            banderas.add(a.split("=", 1)[0])
        else:
            posicionales.append(a)
        k += 1
    if banderas & {"--delete", "-d"}:
        return []  # borrar una rama no corre el CI
    if banderas & TODAS:
        locales = set(git(repo, "for-each-ref", "--format=%(refname:short)", "refs/heads").split())
        return [(r, r) for r in abiertas & locales]
    refs = posicionales[1:]
    if not refs:
        if "--tags" in banderas:
            return []  # solo etiquetas
        refs = ["HEAD"]
    salida = []
    for ref in refs:
        origen, _, destino = ref.lstrip("+").partition(":")
        origen = origen or "HEAD"
        if not destino:
            destino = git(repo, "rev-parse", "--abbrev-ref", origen) if origen == "HEAD" else origen
        salida.append((origen, destino.removeprefix("refs/heads/")))
    return salida


def git(repo: str, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True).stdout.strip()


def avisar(msg: str) -> None:
    print(json.dumps({"systemMessage": f"capitan: {msg}"}))
    sys.exit(0)


def bloquear(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


def main() -> None:
    try:
        datos = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    cwd = datos.get("cwd") or os.getcwd()
    comando = (datos.get("tool_input") or {}).get("command") or ""
    if datos.get("agent_id") or "push" not in comando or not os.path.exists(os.path.join(cwd, ".claude", "capitan.md")):
        sys.exit(0)
    try:
        lista = list(pushes(comando, cwd))
    except Ilegible as e:
        bloquear(f"capitan: no pude leer este comando para saber qué ramas sube ({e}). Escribe el `git push` solo, sin comillas sueltas.")
    if not lista:
        sys.exit(0)
    try:
        r = subprocess.run(["gh", "pr", "list", "--state", "open", "--limit", "200", "--json", "headRefName", "--jq", ".[].headRefName"],
                           cwd=cwd, capture_output=True, text=True, timeout=25)
    except (OSError, subprocess.TimeoutExpired):
        avisar("no pude saber qué ramas tienen PR abierto (gh no respondió); confirma el CI local antes de subir.")
    if r.returncode != 0:
        avisar(f"no pude saber qué ramas tienen PR abierto ({r.stderr.strip()[:120]}); confirma el CI local antes de subir.")
    abiertas = set(r.stdout.split())
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ci_local.py")
    for repo, args in lista:
        verdes = set()
        try:
            verdes = set(open(ci_local.archivo_ok(repo), encoding="utf-8").read().split())
        except OSError:
            pass
        for origen, rama in destinos(repo, args, abiertas):
            if rama not in abiertas:
                continue  # sin PR: este push no dispara el CI de GitHub
            if not ci_local.comando_ci(git(repo, "rev-parse", "--show-toplevel") or repo):
                avisar(f"`{rama}` tiene PR abierto y .claude/capitan.md no nombra su `| CI local |`; corre el CI-equivalente antes de subir.")
            sha = git(repo, "rev-parse", origen)
            if not sha or sha not in verdes:
                bloquear(
                    f"Bloqueado: `{rama}` tiene un PR abierto, así que este push corre el CI completo de GitHub y se cobra.\n"
                    f"El CI local no ha pasado sobre {sha[:10] or origen}. Corre:\n  python3 \"{script}\"\n"
                    "y vuelve a subir. Si tienes más cambios pendientes (docs, relevo), júntalos ANTES: un solo push, una sola corrida."
                )
    sys.exit(0)


if __name__ == "__main__":
    main()
