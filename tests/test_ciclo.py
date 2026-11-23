"""Pruebas del checklist mecánico (scripts/ciclo.py), sobre un repo de git de verdad:
    python3 -m unittest discover -s tests
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from repo_actividad import CLAVE, RAMA, RepoActividad, ciclo, sh


class Ciclo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.r = RepoActividad(self.tmp.name)
        self.assertEqual(self.r.ciclo("crear", CLAVE).returncode, 0)

    def tearDown(self):
        self.tmp.cleanup()

    def falla(self, n, bandera, texto):
        r = self.r.ciclo("paso", CLAVE, str(n), bandera, texto)
        self.assertNotEqual(r.returncode, 0, f"paso {n} debió negarse: {r.stdout}")
        return r.stderr

    def paso(self, n):
        return next(p for p in self.r.leer()["pasos"] if p["n"] == n)

    # --- el SKILL manda ---
    def test_los_pasos_que_valida_son_los_del_skill(self):
        titulos = dict(ciclo.pasos_del_ciclo())
        self.assertIn("Rama", titulos[1])
        self.assertIn("Plan de pruebas", titulos[5])
        self.assertIn("reproducir", titulos[6])
        self.assertIn("Implementar", titulos[7])
        self.assertIn("pruebas", titulos[10])
        self.assertIn("Seguridad", titulos[11])
        self.assertIn("Verificador", titulos[12])
        self.assertIn("Entregar", titulos[13])
        self.assertIn("Relevo", titulos[15])
        self.assertIn("tracker", titulos[16])
        self.assertEqual(ciclo.pares_en_paralelo(), {4: 5, 5: 4, 10: 11, 11: 10})

    def test_crear_dos_veces_se_niega(self):
        self.assertIn("ya tiene", self.r.ciclo("crear", CLAVE).stderr)

    def test_vive_en_git_y_no_ensucia_el_arbol(self):
        self.r.cerrar(1)
        self.assertEqual(sh(self.r.dir, "git", "status", "--porcelain", "--", ".claude", "app"), "")
        self.assertTrue(os.path.exists(ciclo.ruta_viva(self.r.dir, CLAVE)))
        self.assertIn(".git", ciclo.ruta_viva(self.r.dir, CLAVE))

    # --- de punta a punta ---
    def test_ciclo_completo_deja_la_copia_para_el_pr(self):
        self.r.cerrar_hasta(16)
        c = self.r.leer()
        self.assertTrue(all(p["estado"] != "pendiente" for p in c["pasos"]))
        copia = os.path.join(self.r.dir, "docs", "capitan", "ciclo", f"{CLAVE}.json")
        with open(copia, encoding="utf-8") as f:
            self.assertEqual(json.load(f), c)
        self.assertIn("«3 passed, 0 failed»", self.paso(12)["nota"])
        self.assertIn("inicio", self.paso(2)["nota"])
        self.assertIn("cierre", self.paso(15)["nota"])
        self.assertIn("→", self.paso(15)["dato"]["linea"])

    def test_el_espejo_trae_el_titulo_exacto(self):
        r = self.r.cerrar(1)
        self.assertIn(f"Ciclo 1 · Rama propia — rama {RAMA}", r.stdout)

    # --- la evidencia mínima ---
    def test_1_exige_una_rama_que_exista(self):
        self.assertIn("rama", self.falla(1, "--hecho", "rama que-no-existe"))

    def test_2_y_16_leen_el_medidor_no_el_texto(self):
        os.makedirs(os.path.join(self.r.dir, ".claude"), exist_ok=True)
        import datetime as dt
        with open(os.path.join(self.r.dir, ".claude", "usage-now.json"), "w", encoding="utf-8") as f:
            json.dump({"five_hour_pct": 12, "seven_day_pct": 30,
                       "written_at": dt.datetime.now(dt.timezone.utc).isoformat()}, f)
        self.r.cerrar_hasta(2)
        self.assertIn("uso 5 h 12 %", self.paso(2)["nota"])
        self.assertEqual(self.paso(2)["dato"]["cinco"], 12)

    def test_5_exige_el_archivo_del_plan(self):
        self.r.cerrar_hasta(3)
        self.assertIn("ruta del plan", self.falla(5, "--hecho", "plan en docs/capitan/pruebas/NO-EXISTE.md"))
        self.r.cerrar(5)

    def test_6_exige_la_salida_roja(self):
        self.r.cerrar_hasta(5)
        self.assertIn("ROJA", self.falla(6, "--hecho", "lo reproduje"))
        r = self.r.ciclo("paso", CLAVE, "6", "--hecho", "FAILED test_algo - AssertionError: 2 != 1")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_7_exige_un_commit_de_la_rama(self):
        self.r.cerrar_hasta(6)
        sh(self.r.dir, "git", "checkout", "-q", "main")
        self.r.escribir("app/otro.py", "y = 2\n")
        fuera = self.r.commit("otro trabajo en la principal")
        sh(self.r.dir, "git", "checkout", "-q", RAMA)
        self.assertIn(RAMA, self.falla(7, "--hecho", "sin sha"))
        self.assertIn(RAMA, self.falla(7, "--hecho", f"commit {fuera[:9]}"))
        self.r.cerrar(7)

    def test_10_exige_revisó_sha(self):
        self.r.cerrar_hasta(9)
        self.assertIn("revisó <sha>", self.falla(10, "--hecho", "sin hallazgos"))

    def test_10_se_niega_si_hay_codigo_despues_del_sha(self):
        self.r.cerrar_hasta(9)
        viejo = self.r.sha
        self.r.cambio("app/algo.py", "def algo():\n    return 2\n", "fix: algo")
        self.assertIn("revise la punta", self.falla(10, "--hecho", f"revisó {viejo[:9]}"))

    def test_un_commit_de_docs_no_obliga_a_revisar_otra_vez(self):
        self.r.cerrar_hasta(9)
        viejo = self.r.sha
        self.r.cambio("docs/notas.md", "nota\n", "docs: nota")
        r = self.r.ciclo("paso", CLAVE, "10", "--hecho", f"revisó {viejo[:9]}")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_revision_cruzada_de_un_arreglo(self):
        self.r.cerrar_hasta(11)
        # el probador provoca un arreglo después de que los dos cerraron
        nuevo = self.r.cambio("app/algo.py", "def algo():\n    return 2\n", "fix: lo que encontró el probador")
        self.r.registrar_ci(nuevo)
        err = self.falla(12, "--hecho", "CI")
        self.assertIn("paso 10", err)
        self.assertIn("paso 11", err)
        self.r.ciclo("paso", CLAVE, "10", "--hecho", f"revisó {nuevo[:9]}")
        err = self.falla(12, "--hecho", "CI")
        self.assertNotIn("paso 10", err)
        self.assertIn("paso 11", err)
        r = self.r.ciclo("paso", CLAVE, "11", "--hecho", f"solo el diff del arreglo, revisó {nuevo[:9]}")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.paso(11)["antes"]), 1)
        self.r.cerrar(12)

    def test_12_exige_el_registro_del_ci_sobre_la_punta(self):
        self.r.cerrar_hasta(11)
        self.assertIn("ci_local.py", self.falla(12, "--hecho", "todo verde"))
        self.r.registrar_ci(self.r.sha)
        self.r.cambio("docs/x.md", "x\n", "docs: x")  # la punta se movió: el registro ya no es de ella
        self.assertIn("ci_local.py", self.falla(12, "--hecho", "todo verde"))

    def test_13_exige_el_merge_de_la_actividad(self):
        self.r.cerrar_hasta(12)
        self.assertIn("merge", self.falla(13, "--hecho", f"merge {self.r.sha[:9]}"))
        self.r.cerrar(13)

    def test_15_exige_el_relevo_despues_del_merge(self):
        self.r.cerrar_hasta(14)
        self.r.relevo(despues_del_merge=False)
        self.assertIn("después del merge", self.falla(15, "--hecho", "relevo"))

    def test_1_prefiere_la_rama_de_la_actividad_a_la_principal(self):
        r = self.r.ciclo("paso", CLAVE, "1", "--hecho", f"desde main: {RAMA}")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.paso(1)["dato"]["rama"], RAMA)

    def test_16_exige_la_medicion_pegada_en_estado(self):
        self.r.cerrar_hasta(14)
        self.r.escribir("docs/capitan/estado.md", f"# Estado\n\n## Dónde quedó\n{CLAVE} · En curso · {RAMA}\n")
        r = self.r.ciclo("paso", CLAVE, "15", "--hecho", "relevo")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("medición que imprimió el paso 15", self.falla(16, "--hecho", "comentario 2026-01-01"))
        self.r.relevo()
        self.r.cerrar(16)

    # --- reabrir y retomar ---
    def test_reabrir_exige_permiso_y_guarda_lo_anterior(self):
        self.r.cerrar_hasta(2)
        r = self.r.ciclo("reabrir", CLAVE, "2", "--permiso", "me equivoqué")
        self.assertNotEqual(r.returncode, 0)
        r = self.r.ciclo("reabrir", CLAVE, "2", "--permiso", "permiso del dueño, 2026-01-01: se marcó antes de mover")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.paso(2)["estado"], "pendiente")
        self.assertIn("reabierto", self.paso(2)["antes"][0])
        self.r.cerrar(2)

    def test_otra_maquina_retoma_de_la_copia(self):
        self.r.cerrar_hasta(3)
        self.assertEqual(self.r.ciclo("exportar", CLAVE).returncode, 0)
        os.remove(ciclo.ruta_viva(self.r.dir, CLAVE))  # el clon nuevo no tiene el vivo
        self.assertEqual([p["estado"] for p in self.r.leer()["pasos"][:4]], ["hecha", "hecha", "hecha", "pendiente"])
        self.assertTrue(os.path.exists(ciclo.ruta_viva(self.r.dir, CLAVE)))
        self.r.cerrar(4)

    # --- no aplica y omitido ---
    def test_pruebas_y_seguridad_nunca_son_no_aplica(self):
        self.r.cerrar_hasta(9)
        self.assertIn("permiso", self.falla(10, "--no-aplica", "es chica"))

    def test_omitido_exige_el_permiso_con_fecha(self):
        self.r.cerrar_hasta(9)
        self.assertIn("permiso", self.falla(10, "--omitido", "no hacía falta"))
        r = self.r.ciclo("paso", CLAVE, "10", "--omitido", "permiso del dueño, 2026-01-01: la prueba la hace él")
        self.assertEqual(r.returncode, 0, r.stderr)

    # --- orden ---
    def test_orden_con_pares_en_paralelo(self):
        self.r.cerrar_hasta(3)
        self.r.cerrar(5)  # el 5 antes que el 4
        self.assertIn("4", self.falla(6, "--no-aplica", "es mejora"))
        self.r.cerrar(4)
        self.r.cerrar(6)
        self.assertIn("7", self.falla(8, "--no-aplica", "sin UI"))

    def test_un_paso_cerrado_no_se_vuelve_a_marcar(self):
        self.r.cerrar(1)
        self.assertIn("ya está cerrado", self.falla(1, "--hecho", f"rama {RAMA}"))


if __name__ == "__main__":
    unittest.main()
