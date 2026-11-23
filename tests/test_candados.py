"""Pruebas de los candados de la 0.8.1: hook_tracker.py, ci_local.py y el aviso de versión.

Corren los scripts de verdad sobre repos de git temporales:
    python3 -m unittest discover -s tests
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(RAIZ, "scripts")
sys.path.insert(0, SCRIPTS)
from version_plugin import aviso_version  # noqa: E402

CONFIG = """# Capitán · mi-proyecto

| Campo | Valor |
|---|---|
| Tracker | mcp tracker-de-ejemplo ABC-001 |
| CI local | `{ci}` |

## Tracker

| Operación | Herramienta | Notas |
|---|---|---|
| Ver el tablero | `listar-cosas` | |
| Mover (solo a la contigua) | `cambiar-columna` | |

| Columna de Capitán | Valor | Cómo se ve |
|---|---|---|
| En curso | `doing` | En curso |
| Revisión de código | `review` | Revisión |
"""

ESTADO_OK = """# Estado del proyecto

## Dónde quedó
ACT-012 · En curso · mi-proyecto-act-012-algo · 10:05 → 11:40 · uso 5 h +6 · semana +1

## Lo que sigue
"""


def sh(cwd, *args):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


class Repo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        sh(self.dir, "git", "init", "-q", "-b", "principal")
        sh(self.dir, "git", "config", "user.email", "prueba@example.com")
        sh(self.dir, "git", "config", "user.name", "prueba")
        os.makedirs(os.path.join(self.dir, ".claude"))
        os.makedirs(os.path.join(self.dir, "docs", "capitan"))

    def tearDown(self):
        self.tmp.cleanup()

    def escribir(self, ruta, texto):
        with open(os.path.join(self.dir, ruta), "w", encoding="utf-8") as f:
            f.write(texto)

    def commit(self, msg="c"):
        sh(self.dir, "git", "add", "-A")
        sh(self.dir, "git", "commit", "-q", "-m", msg)


class HookTracker(Repo):
    def setUp(self):
        super().setUp()
        self.escribir(".claude/capitan.md", CONFIG.format(ci="true"))
        self.commit("base")
        # paso 13: la actividad se mergea a la rama de sesión
        sh(self.dir, "git", "checkout", "-q", "-b", "mi-proyecto-act-012-algo")
        self.escribir("algo.txt", "x")
        self.commit("feat: algo ABC-001/ACT-012")
        sh(self.dir, "git", "checkout", "-q", "principal")
        sh(self.dir, "git", "merge", "-q", "--no-ff", "-m", "Merge ABC-001/ACT-012 algo", "mi-proyecto-act-012-algo")

    def hook(self, herramienta="mcp__tracker__cambiar-columna", entrada=None):
        datos = {"cwd": self.dir, "tool_name": herramienta,
                 "tool_input": entrada if entrada is not None else {"actividad": "ACT-012", "columna": "review"}}
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, "hook_tracker.py")], input=json.dumps(datos),
                              capture_output=True, text=True)

    def estado(self, texto, despues_del_merge=True):
        ruta = os.path.join(self.dir, "docs", "capitan", "estado.md")
        self.escribir("docs/capitan/estado.md", texto)
        merge = int(sh(self.dir, "git", "log", "-1", "--merges", "--format=%ct").strip())
        t = merge + 5 if despues_del_merge else merge - 3600
        os.utime(ruta, (t, t))

    def test_deja_pasar_con_el_relevo_al_dia(self):
        self.estado(ESTADO_OK)
        r = self.hook()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_bloquea_si_estado_no_se_reescribio_tras_el_merge(self):
        self.estado(ESTADO_OK, despues_del_merge=False)
        r = self.hook()
        self.assertEqual(r.returncode, 2)
        self.assertIn("no se reescribió después del merge de ACT-012", r.stderr)

    def test_bloquea_sin_hora_ni_uso(self):
        self.estado(ESTADO_OK.replace(" · 10:05 → 11:40 · uso 5 h +6 · semana +1", ""))
        r = self.hook()
        self.assertEqual(r.returncode, 2)
        self.assertIn("HH:MM → HH:MM", r.stderr)

    def test_bloquea_sin_linea_de_la_actividad(self):
        self.estado(ESTADO_OK.replace("ACT-012", "ACT-011"))
        self.assertEqual(self.hook().returncode, 2)

    def test_bloquea_sin_estado(self):
        self.assertEqual(self.hook().returncode, 2)

    def test_otra_columna_no_se_revisa(self):
        r = self.hook(entrada={"actividad": "ACT-012", "columna": "doing"})
        self.assertEqual(r.returncode, 0)

    def test_otra_herramienta_no_se_revisa(self):
        r = self.hook(herramienta="mcp__tracker__listar-cosas")
        self.assertEqual(r.returncode, 0)

    def test_sin_merge_avisa_y_no_bloquea(self):
        r = self.hook(entrada={"actividad": "ACT-099", "columna": "review"})
        self.assertEqual(r.returncode, 0)
        self.assertIn("no encuentro el merge", r.stdout)

    def test_sin_seccion_tracker_no_hace_nada(self):
        self.escribir(".claude/capitan.md", "| Tracker | local |\n")
        self.assertEqual(self.hook().returncode, 0)

    def test_sin_valor_de_revision_avisa_y_no_bloquea(self):
        self.escribir(".claude/capitan.md", CONFIG.format(ci="true").replace("| Revisión de código | `review` | Revisión |\n", ""))
        r = self.hook()
        self.assertEqual(r.returncode, 0)
        self.assertIn("Revisión de código", r.stdout)


class CiLocal(Repo):
    def ci(self, comando):
        self.escribir(".claude/capitan.md", CONFIG.format(ci=comando))
        self.commit()
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, "ci_local.py")], cwd=self.dir,
                              capture_output=True, text=True)

    def registro(self):
        ruta = os.path.join(self.dir, ".git", "capitan", "ci-registro.log")
        if not os.path.exists(ruta):
            return ""
        with open(ruta, encoding="utf-8") as f:
            return f.read()

    def test_verde_registra_la_salida_literal(self):
        r = self.ci("echo '412 passed, 0 failed'")
        self.assertEqual(r.returncode, 0, r.stderr)
        sha = sh(self.dir, "git", "rev-parse", "HEAD").strip()
        self.assertIn(sha, self.registro())
        self.assertIn("412 passed, 0 failed", self.registro())
        self.assertIn("412 passed, 0 failed", r.stdout)

    def test_error_del_shell_no_es_verde_aunque_salga_cero(self):
        r = self.ci("comando-que-no-existe-xyz; echo '10 passed'")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("errores del shell", r.stderr)
        self.assertEqual(self.registro(), "")
        self.assertFalse(os.path.exists(os.path.join(self.dir, ".git", "capitan", "ci-ok")))

    def test_rojo_no_registra(self):
        r = self.ci("echo '3 failed'; exit 1")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.registro(), "")


class AvisoVersion(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.plugin = os.path.join(d, "instalado")
        self.mk = os.path.join(d, "marketplaces")
        self.sello = os.path.join(d, "sello")
        self.remoto = os.path.join(d, "remoto")
        os.makedirs(os.path.join(self.plugin, ".claude-plugin"))
        self.version(self.plugin, "0.8.0")
        os.makedirs(os.path.join(self.remoto, ".claude-plugin"))
        sh(self.remoto, "git", "init", "-q", "-b", "main")
        sh(self.remoto, "git", "config", "user.email", "prueba@example.com")
        sh(self.remoto, "git", "config", "user.name", "prueba")
        self.version(self.remoto, "0.8.0")
        sh(self.remoto, "git", "add", "-A")
        sh(self.remoto, "git", "commit", "-q", "-m", "0.8.0")
        os.makedirs(self.mk)
        sh(self.mk, "git", "clone", "-q", self.remoto, "capitan")
        self.copia = os.path.join(self.mk, "capitan")

    def tearDown(self):
        self.tmp.cleanup()

    def version(self, carpeta, v):
        with open(os.path.join(carpeta, ".claude-plugin", "plugin.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "capitan", "version": v}, f)

    def publicar(self, v):
        self.version(self.remoto, v)
        sh(self.remoto, "git", "commit", "-q", "-am", v)

    def aviso(self, hoy="2026-01-01"):
        return aviso_version(self.plugin, self.mk, self.sello, hoy)

    def test_al_dia_no_avisa(self):
        self.assertIsNone(self.aviso())

    def test_avisa_si_hay_una_mas_nueva(self):
        self.publicar("0.8.1")
        a = self.aviso()
        self.assertIn("0.8.0", a)
        self.assertIn("0.8.1", a)
        self.assertNotIn("divergió", a)

    def test_avisa_que_la_copia_divergio(self):
        self.publicar("0.8.1")
        with open(os.path.join(self.copia, "local.txt"), "w") as f:
            f.write("x")
        sh(self.copia, "git", "add", "-A")
        sh(self.copia, "git", "-c", "user.email=p@example.com", "-c", "user.name=p", "commit", "-q", "-m", "local")
        self.assertIn("divergió", self.aviso())

    def test_una_vez_al_dia(self):
        self.publicar("0.8.1")
        self.assertIsNotNone(self.aviso("2026-01-01"))
        self.assertIsNone(self.aviso("2026-01-01"))
        self.assertIsNotNone(self.aviso("2026-01-02"))

    def test_compara_como_numeros(self):
        self.version(self.plugin, "0.10.0")
        self.publicar("0.9.0")
        self.assertIsNone(self.aviso())


if __name__ == "__main__":
    unittest.main()
