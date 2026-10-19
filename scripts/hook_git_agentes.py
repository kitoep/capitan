#!/usr/bin/env python3
"""Hook PreToolUse del tool Bash (plugin capitan). En un proyecto que usa el
método (tiene .claude/capitan.md), un SUBAGENTE no puede correr git que cambie estado: commits, merges y
ramas los hace la sesión principal. Nació el 2026-10-02: un probador aplicó un
stash viejo de otra sesión y dejó el repo en conflicto.

Claude Code marca las llamadas de un subagente con `agent_id`; las de la
sesión principal no lo traen (verificado el 2026-10-02)."""
import json
import os
import re
import shlex
import sys

PELIGROSOS = {
    "stash", "checkout", "switch", "reset", "restore", "merge", "rebase",
    "commit", "push", "pull", "clean", "worktree", "cherry-pick", "revert",
    "am", "apply", "tag", "rm", "mv", "gc", "prune", "update-ref", "filter-branch",
}
# `git branch` solo para leer.
BRANCH_LECTURA = {"--show-current", "-a", "-r", "--list", "-v", "-vv", "--all", "--remotes", "--contains", "--merged", "--no-merged"}

try:
    datos = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if not datos.get("agent_id"):
    sys.exit(0)  # la sesión principal sí puede
cwd = datos.get("cwd") or os.getcwd()
if not os.path.exists(os.path.join(cwd, ".claude", "capitan.md")):
    sys.exit(0)
comando = (datos.get("tool_input") or {}).get("command") or ""


def subcomando_git(fragmento: str):
    try:
        partes = shlex.split(fragmento)
    except ValueError:
        partes = fragmento.split()
    for i, p in enumerate(partes):
        if os.path.basename(p) == "git":
            resto = partes[i + 1 :]
            # saltar opciones globales: -C <dir>, -c <k=v>, --no-pager, etc.
            j = 0
            while j < len(resto) and resto[j].startswith("-"):
                j += 2 if resto[j] in ("-C", "-c", "--git-dir", "--work-tree") else 1
            if j < len(resto):
                return resto[j], resto[j + 1 :]
    return None, []


for fragmento in re.split(r"&&|\|\||;|\||\n|\$\(|`", comando):
    sub, args = subcomando_git(fragmento)
    if sub is None:
        continue
    if sub == "stash" and args[:1] in (["list"], ["show"]):
        continue  # solo leen
    if sub in PELIGROSOS or (sub == "branch" and any(a not in BRANCH_LECTURA for a in args)):
        print(
            f"Bloqueado: un subagente no puede correr `git {sub}` (cambia el estado del repo). "
            "Para comparar contra otra versión: copia de respaldo en /tmp, "
            "`git show <ref>:<ruta> > <ruta>`, corre, y restaura con `cp`. "
            "Commits, merges y ramas los hace la sesión principal.",
            file=sys.stderr,
        )
        sys.exit(2)
sys.exit(0)
