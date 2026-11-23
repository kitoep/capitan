"""Un repo de git temporal con una actividad de verdad, para probar el checklist
mecánico: rama de actividad, rama de sesión, commits, plan de pruebas, registro
del CI local, merge y relevo. Cada paso del ciclo recibe evidencia válida."""
from __future__ import annotations

import json
import os
import subprocess
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(RAIZ, "scripts")
sys.path.insert(0, SCRIPTS)
import ci_local  # noqa: E402
import ciclo  # noqa: E402

CLAVE = "ACT-001"
RAMA = "mi-proyecto-act-001-mejora"
SESION = "mi-proyecto-sesion-2026-01-01"
PLAN = "docs/capitan/pruebas/ACT-001.md"
CONFIG = """# Capitán · mi-proyecto

| Campo | Valor |
|---|---|
| Tracker | local |
| CI local | `true` |
"""


def sh(cwd, *args):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, f"{args}: {r.stderr}"
    return r.stdout.strip()


class RepoActividad:
    def __init__(self, carpeta: str):
        self.dir = carpeta
        self.env = {**os.environ, "HOME": carpeta, "USERPROFILE": carpeta, "PYTHONUTF8": "1"}
        sh(carpeta, "git", "init", "-q", "-b", "main")
        sh(carpeta, "git", "config", "user.email", "prueba@example.com")
        sh(carpeta, "git", "config", "user.name", "prueba")
        self.escribir(".claude/capitan.md", CONFIG)
        self.escribir(PLAN, "# Plan de pruebas\n- adversarial: entrada vacía\n")
        self.escribir("app/base.py", "x = 1\n")
        self.commit("base")
        sh(carpeta, "git", "branch", SESION)
        sh(carpeta, "git", "checkout", "-q", "-b", RAMA)
        self.sha = self.cambio("app/algo.py", "def algo():\n    return 1\n", f"feat: algo ABC-001/{CLAVE}")
        self.merge_sha = None

    # --- git ---
    def escribir(self, ruta, texto):
        completa = os.path.join(self.dir, ruta)
        os.makedirs(os.path.dirname(completa), exist_ok=True)
        with open(completa, "w", encoding="utf-8") as f:
            f.write(texto)

    def commit(self, msg):
        sh(self.dir, "git", "add", "-A")
        sh(self.dir, "git", "commit", "-q", "-m", msg)
        return sh(self.dir, "git", "rev-parse", "HEAD")

    def cambio(self, ruta, texto, msg):
        """Un commit en la rama de la actividad (sin moverse de donde esté)."""
        actual = sh(self.dir, "git", "branch", "--show-current")
        if actual != RAMA:
            sh(self.dir, "git", "checkout", "-q", RAMA)
        self.escribir(ruta, texto)
        sha = self.commit(msg)
        if actual != RAMA:
            sh(self.dir, "git", "checkout", "-q", actual)
        return sha

    def registrar_ci(self, sha=None, alcance="áreas: app"):
        ci_local.registrar(self.dir, sha or sh(self.dir, "git", "rev-parse", RAMA), "pytest app", ["3 passed, 0 failed"], alcance)

    def mergear(self):
        sh(self.dir, "git", "checkout", "-q", SESION)
        sh(self.dir, "git", "merge", "-q", "--no-ff", "-m", f"Merge ABC-001/{CLAVE} mejora", RAMA)
        self.merge_sha = sh(self.dir, "git", "rev-parse", "HEAD")
        return self.merge_sha

    def relevo(self, despues_del_merge=True):
        self.escribir("docs/capitan/estado.md", "# Estado\n\n## Dónde quedó\n"
                      f"{CLAVE} · En curso · {RAMA} · 10:05 → 11:40 · uso 5 h +6 · semana +1\n")
        cuando = int(sh(self.dir, "git", "log", "-1", "--format=%ct", self.merge_sha))
        t = cuando + 5 if despues_del_merge else cuando - 3600
        os.utime(os.path.join(self.dir, "docs", "capitan", "estado.md"), (t, t))

    # --- el ciclo ---
    def evidencia(self, n: int) -> tuple[str, str]:
        """La forma válida de cerrar el paso n (prepara lo que haga falta)."""
        if n == 1:
            return "--hecho", f"rama {RAMA}"
        if n == 5:
            return "--hecho", f"plan en {PLAN}: 6 casos"
        if n in (6, 8, 9, 14):
            return "--no-aplica", {6: "es mejora, no bug", 8: "sin UI", 9: "sin desvíos", 14: "sin hallazgos"}[n]
        if n == 7:
            return "--hecho", f"commit {self.sha[:9]}"
        if n in (10, 11):
            return "--hecho", f"opus: sin hallazgos, revisó {sh(self.dir, 'git', 'rev-parse', RAMA)[:9]}"
        if n == 12:
            self.registrar_ci()
            return "--hecho", "CI por área"
        if n == 13:
            return "--hecho", f"merge {self.mergear()[:9]}"
        if n == 15:
            self.relevo()
            return "--hecho", "estado.md reescrito"
        if n == 16:
            return "--hecho", "comentario de cierre publicado 2026-01-01 10:00"
        return "--hecho", f"evidencia del paso {n}"

    def ciclo(self, *args):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, "ciclo.py"), *args], cwd=self.dir, env=self.env,
                              capture_output=True, text=True, encoding="utf-8")

    def cerrar(self, n, runner=None):
        bandera, texto = self.evidencia(n)
        r = (runner or self.ciclo)("paso", CLAVE, str(n), bandera, texto)
        assert r.returncode == 0, f"paso {n}: {r.stderr}"
        return r

    def cerrar_hasta(self, n, runner=None):
        for i in range(1, n + 1):
            self.cerrar(i, runner)

    def leer(self) -> dict:
        return ciclo.leer(self.dir, CLAVE)


def escribir_checklist(carpeta: str, clave: str, cerrados: dict[int, dict]) -> None:
    """Un checklist con los pasos dados ya cerrados (para probar hooks que solo lo leen)."""
    c = {"clave": clave, "pasos": []}
    for n, t in ciclo.pasos_del_ciclo():
        p = {"n": n, "titulo": t, "estado": "pendiente"}
        if n in cerrados:
            p.update(estado="hecha", nota=f"paso {n}", dato=cerrados[n])
        c["pasos"].append(p)
    ciclo.escribir(ciclo.ruta_viva(carpeta, clave), c)


