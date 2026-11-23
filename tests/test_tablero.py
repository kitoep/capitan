"""Pruebas del checklist del ciclo en el tablero local (scripts/tablero.py).

Corren el script de verdad, en una carpeta temporal, como lo corre Capitán:
    python3 -m unittest discover -s tests
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

from repo_actividad import RAMA, RepoActividad  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLERO = os.path.join(RAIZ, "scripts", "tablero.py")
SKILL = os.path.join(RAIZ, "skills", "trabajar", "SKILL.md")


class Tablero(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # Un repo de verdad: el checklist vive junto al repo (ciclo.py) y valida la evidencia.
        # HOME propio: el medidor de sesión de la máquina no debe colarse en la prueba.
        self.repo = RepoActividad(self.tmp.name)
        self.dir = self.repo.dir
        self.env = self.repo.env
        self.ok("init", "mi-proyecto")
        self.ok("epica", "M1", "Primera épica")
        self.ok("crear", "M1 · Una mejora", "--epica", "M1", "--subtarea", "Escribir la consulta")

    def tearDown(self):
        self.tmp.cleanup()

    def run_(self, *args):
        return subprocess.run([sys.executable, TABLERO, *args], cwd=self.dir, env=self.env,
                              capture_output=True, text=True, encoding="utf-8")

    def ok(self, *args):
        r = self.run_(*args)
        self.assertEqual(r.returncode, 0, f"{args} falló: {r.stderr}")
        return r.stdout

    def falla(self, *args):
        r = self.run_(*args)
        self.assertNotEqual(r.returncode, 0, f"{args} debió negarse y salió: {r.stdout}")
        return r.stderr

    def act(self, clave="ACT-001"):
        with open(os.path.join(self.dir, "docs", "capitan", "tablero.json"), encoding="utf-8") as f:
            t = json.load(f)
        return next(a for a in t["actividades"] if a["clave"] == clave)

    def html(self):
        with open(os.path.join(self.dir, "docs", "capitan", "tablero.html"), encoding="utf-8") as f:
            return f.read()

    def ciclo(self):
        return [s for s in self.act()["subtareas"] if s.get("ciclo")]

    def a_en_curso(self):
        self.ok("mover", "ACT-001", "por_hacer")
        self.ok("mover", "ACT-001", "en_curso")

    def cerrar(self, n):
        bandera, texto = self.repo.evidencia(n)
        self.ok("paso", "ACT-001", str(n), bandera, texto)

    def cerrar_hasta(self, n):
        for i in range(1, n + 1):
            self.cerrar(i)

    # --- leer el ciclo del SKILL ---
    def test_listar_lee_la_tabla_del_skill(self):
        with open(SKILL, encoding="utf-8") as f:
            texto = f.read()
        filas = [l for l in texto.split("## El ciclo de una actividad")[1]
                 .split("\n## ")[0].splitlines() if l[:2] == "| " and l[2:3].isdigit()]
        salida = self.ok("ciclo", "--listar").splitlines()
        self.assertEqual(len(salida), len(filas))
        self.assertEqual(salida[0], "Ciclo 1 · Rama propia")
        self.assertTrue(any(l.startswith("Ciclo 4 · Crítica + seguridad del plan") for l in salida))
        for l in salida:
            self.assertNotIn("**", l)
            self.assertNotIn("(", l)

    # --- crear ---
    def test_ciclo_agrega_los_pasos_sin_tocar_las_subtareas_propias(self):
        self.ok("ciclo", "ACT-001")
        subs = self.act()["subtareas"]
        self.assertEqual(subs[0]["titulo"], "Escribir la consulta")
        self.assertNotIn("ciclo", subs[0])
        pasos = self.ciclo()
        self.assertEqual([s["ciclo"] for s in pasos], list(range(1, len(pasos) + 1)))
        self.assertTrue(all(s["titulo"].startswith(f"Ciclo {s['ciclo']} · ") for s in pasos))
        self.assertTrue(all(s["estado"] == "pendiente" and not s["hecha"] for s in pasos))

    def test_ciclo_no_se_duplica(self):
        self.ok("ciclo", "ACT-001")
        n = len(self.act()["subtareas"])
        self.assertIn("ya tiene", self.falla("ciclo", "ACT-001"))
        self.assertEqual(len(self.act()["subtareas"]), n)

    # --- marcar ---
    def test_paso_hecho_guarda_evidencia_y_bitacora(self):
        self.ok("ciclo", "ACT-001")
        self.ok("paso", "ACT-001", "1", "--hecho", f"rama {RAMA}")
        p = self.ciclo()[0]
        self.assertEqual((p["estado"], p["hecha"]), ("hecha", True))
        self.assertEqual(p["nota"], f"rama {RAMA}")
        self.assertIn("paso 1 hecho", self.act()["bitacora"][-1]["que"])
        self.assertIn(f"rama {RAMA}", self.html())

    def test_evidencia_invalida_no_toca_el_espejo(self):
        self.ok("ciclo", "ACT-001")
        self.assertIn("rama", self.falla("paso", "ACT-001", "1", "--hecho", "rama que-no-existe"))
        self.assertEqual(self.ciclo()[0]["estado"], "pendiente")

    def test_paso_sin_evidencia_se_niega(self):
        self.ok("ciclo", "ACT-001")
        self.falla("paso", "ACT-001", "1", "--hecho", "  ")
        self.falla("paso", "ACT-001", "1")
        self.assertEqual(self.ciclo()[0]["estado"], "pendiente")

    def test_paso_se_niega_con_uno_anterior_abierto(self):
        self.ok("ciclo", "ACT-001")
        self.cerrar(1)
        err = self.falla("paso", "ACT-001", "3", "--hecho", "plan escrito")
        self.assertIn("2", err)
        self.assertEqual(self.ciclo()[2]["estado"], "pendiente")

    def test_paso_cerrado_no_se_vuelve_a_marcar(self):
        self.ok("ciclo", "ACT-001")
        self.cerrar(1)
        self.falla("paso", "ACT-001", "1", "--no-aplica", "otra cosa")
        self.assertEqual(self.ciclo()[0]["estado"], "hecha")

    def test_subtarea_no_marca_un_paso_del_ciclo(self):
        self.ok("ciclo", "ACT-001")
        self.assertIn("paso 1", self.falla("subtarea", "ACT-001", "2", "--hecha"))
        self.ok("subtarea", "ACT-001", "1", "--hecha")  # la propia del trabajo sí

    # --- revisores en paralelo (las reglas viven en ciclo.py; aquí, que el tablero las respete) ---
    def test_plan_de_pruebas_cierra_antes_que_la_critica(self):
        self.ok("ciclo", "ACT-001")
        self.cerrar_hasta(3)
        self.cerrar(5)
        self.assertIn("4", self.falla("paso", "ACT-001", "6", "--no-aplica", "es mejora"))
        self.cerrar(4)
        self.cerrar(6)
        self.assertEqual([s["estado"] for s in self.ciclo()[3:6]], ["hecha", "hecha", "no_aplica"])

    # --- no aplica y omitido ---
    def test_no_aplica_cierra_sin_marcar_como_hecho(self):
        self.ok("ciclo", "ACT-001")
        self.cerrar_hasta(5)
        self.ok("paso", "ACT-001", "6", "--no-aplica", "es mejora, no bug")
        p = self.ciclo()[5]
        self.assertEqual((p["estado"], p["hecha"], p["nota"]), ("no_aplica", False, "es mejora, no bug"))
        self.cerrar(7)  # cuenta como cerrado para el orden
        self.assertIn("no aplica: es mejora, no bug", self.html())

    def test_no_aplica_sin_motivo_se_niega(self):
        self.ok("ciclo", "ACT-001")
        self.cerrar_hasta(5)
        self.falla("paso", "ACT-001", "6", "--no-aplica", "")
        self.assertEqual(self.ciclo()[5]["estado"], "pendiente")

    def test_omitido_guarda_el_permiso(self):
        self.ok("ciclo", "ACT-001")
        self.cerrar_hasta(7)
        self.ok("paso", "ACT-001", "8", "--omitido", "permiso del dueño, 2026-01-01: la pantalla la revisa él mañana")
        p = self.ciclo()[7]
        self.assertEqual((p["estado"], p["hecha"]), ("omitida", False))
        self.cerrar(9)

    # --- candado de Revisión de código ---
    def test_no_pasa_a_revision_con_pasos_abiertos(self):
        self.ok("ciclo", "ACT-001")
        self.a_en_curso()
        total = len(self.ciclo())
        self.cerrar_hasta(total - 1)
        err = self.falla("mover", "ACT-001", "revision")
        self.assertIn(str(total), err)
        self.assertEqual(self.act()["columna"], "en_curso")
        self.ok("paso", "ACT-001", str(total), "--hecho", "comentario de cierre publicado")
        self.ok("mover", "ACT-001", "revision")
        self.assertEqual(self.act()["columna"], "revision")

    # --- actividades que ya existían ---
    def test_checklist_de_antes_de_la_090_se_pasa_a_ciclo_py(self):
        self.ok("ciclo", "ACT-001")
        self.cerrar_hasta(2)
        import ciclo
        os.remove(ciclo.ruta_viva(self.dir, "ACT-001"))  # como quedaba antes: solo en el tablero
        self.assertIn("antes de la 0.9.0", self.falla("paso", "ACT-001", "3", "--hecho", "plan"))
        self.ok("ciclo", "ACT-001")
        c = ciclo.leer(self.dir, "ACT-001")
        self.assertEqual([p["estado"] for p in c["pasos"][:3]], ["hecha", "hecha", "pendiente"])
        self.cerrar(3)


    def test_actividad_sin_ciclo_se_mueve_y_se_pinta_como_antes(self):
        self.a_en_curso()
        self.ok("mover", "ACT-001", "revision")
        self.ok("subtarea", "ACT-001", "1", "--hecha")
        self.assertIn("1/1", self.html())
        self.assertIn("no tiene el checklist", self.falla("paso", "ACT-001", "1", "--hecho", "x"))


if __name__ == "__main__":
    unittest.main()
