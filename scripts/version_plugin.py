"""Aviso de versión del plugin, para hook_inicio.py (separado para poder probarlo)."""
from __future__ import annotations

import json
import os
import subprocess


def _version(texto: str) -> tuple:
    try:
        return tuple(int(x) for x in json.loads(texto)["version"].split("."))
    except Exception:
        return ()


def aviso_version(raiz_plugin: str, marketplaces: str, sello: str, hoy: str) -> str | None:
    """Una vez al día: ¿la versión instalada es menor que la del repo del plugin?

    La copia del marketplace no siempre se actualiza sola (si diverge de su
    remoto, `git pull` falla en silencio) y el plugin se queda viejo sin que
    nadie lo note. Aquí se trae el remoto (solo lectura, con tiempo límite) y se
    compara. Sin red o sin copia, no dice nada."""
    try:
        with open(sello, encoding="utf-8") as f:
            if f.read().strip() == hoy:
                return None
    except OSError:
        pass
    try:
        os.makedirs(os.path.dirname(sello), exist_ok=True)
        with open(sello, "w", encoding="utf-8") as f:
            f.write(hoy)
    except OSError:
        return None
    with open(os.path.join(raiz_plugin, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
        instalada = _version(f.read())
    for nombre in sorted(os.listdir(marketplaces)) if os.path.isdir(marketplaces) else []:
        copia = os.path.join(marketplaces, nombre)
        try:
            with open(os.path.join(copia, ".claude-plugin", "plugin.json"), encoding="utf-8") as f:
                if json.load(f).get("name") != "capitan":
                    continue
        except Exception:
            continue
        try:
            subprocess.run(["git", "-C", copia, "fetch", "-q", "origin"], capture_output=True, timeout=5)
        except Exception:
            return None
        remoto = subprocess.run(["git", "-C", copia, "show", "origin/HEAD:.claude-plugin/plugin.json"],
                                capture_output=True, text=True)
        if remoto.returncode != 0:
            remoto = subprocess.run(["git", "-C", copia, "show", "origin/main:.claude-plugin/plugin.json"],
                                    capture_output=True, text=True)
        ultima = _version(remoto.stdout)
        if not instalada or not ultima or instalada >= ultima:
            return None
        diverge = subprocess.run(["git", "-C", copia, "merge-base", "--is-ancestor", "HEAD", "origin/main"],
                                 capture_output=True).returncode != 0
        texto = (f"Capitán instalado: {'.'.join(map(str, instalada))}; la última es {'.'.join(map(str, ultima))}. "
                 "Actualízalo con `claude plugin update capitan@capitan` y reinicia.")
        if diverge:
            texto += (f" Ojo: la copia del marketplace ({copia.replace(os.path.expanduser('~'), '~')}) divergió de su "
                      "remoto y no se actualiza sola; si no tiene cambios tuyos, déjala igual al remoto con "
                      "`git -C <esa carpeta> reset --hard origin/main` antes de actualizar.")
        return texto
    return None

