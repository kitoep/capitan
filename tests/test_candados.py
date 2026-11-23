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
from hook_tracker import aviso_config  # noqa: E402
import ci_local  # noqa: E402
from repo_actividad import CLAVE, RAMA, SESION, RepoActividad, escribir_checklist  # noqa: E402

QUINCE = {n: {} for n in range(1, 16)}

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
        escribir_checklist(self.dir, "ACT-012", QUINCE)
        r = self.hook()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_bloquea_sin_checklist(self):
        self.estado(ESTADO_OK)
        r = self.hook()
        self.assertEqual(r.returncode, 2)
        self.assertIn("no tiene checklist", r.stderr)

    def test_bloquea_con_un_paso_abierto(self):
        self.estado(ESTADO_OK)
        escribir_checklist(self.dir, "ACT-012", {n: {} for n in range(1, 16) if n != 11})
        r = self.hook()
        self.assertEqual(r.returncode, 2)
        self.assertIn("abiertos los pasos 11", r.stderr)

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


class CandadoApagado(Repo):
    """Una config anterior a la forma fija apaga el candado: al abrir la sesión se dice."""

    def inicio(self):
        env = {**os.environ, "HOME": self.dir, "USERPROFILE": self.dir}
        r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "hook_inicio.py")], input=json.dumps({"cwd": self.dir}),
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_forma_fija_no_avisa(self):
        self.assertIsNone(aviso_config(CONFIG.format(ci="true")))

    def test_tablero_local_no_avisa(self):
        self.assertIsNone(aviso_config("| Tracker | local |\n"))

    def test_mover_sin_backticks_avisa(self):
        a = aviso_config(CONFIG.format(ci="true").replace("`cambiar-columna`", "cambiar-columna"))
        self.assertIn("APAGADO", a)
        self.assertIn("«Mover»", a)
        self.assertNotIn("Revisión de código»", a.split("no trae")[1].split("con la")[0])

    def test_sin_revision_avisa(self):
        a = aviso_config(CONFIG.format(ci="true").replace("| Revisión de código | `review` | Revisión |\n", ""))
        self.assertIn("«Revisión de código»", a)

    def test_hook_inicio_lo_dice_al_dueno(self):
        self.escribir(".claude/capitan.md", CONFIG.format(ci="true").replace("`cambiar-columna`", "cambiar-columna"))
        salida = self.inicio()
        self.assertIn("APAGADO", salida["systemMessage"])
        self.assertIn("AVISO PARA EL DUEÑO", salida["hookSpecificOutput"]["additionalContext"])

    def test_hook_inicio_calla_con_la_forma_fija(self):
        self.escribir(".claude/capitan.md", CONFIG.format(ci="true"))
        self.assertNotIn("systemMessage", self.inicio())


def correr_hook(script, cwd, entrada, env=None):
    return subprocess.run([sys.executable, os.path.join(SCRIPTS, script)], input=json.dumps({"cwd": cwd, **entrada}),
                          capture_output=True, text=True, env=env)


class HookCiclo(unittest.TestCase):
    """El merge a la rama de sesión y el PR leen el checklist."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.r = RepoActividad(self.tmp.name)
        self.r.ciclo("crear", CLAVE)

    def tearDown(self):
        self.tmp.cleanup()

    def bash(self, comando):
        return correr_hook("hook_ciclo.py", self.r.dir, {"tool_name": "Bash", "tool_input": {"command": comando}})

    def merge(self):
        sh(self.r.dir, "git", "checkout", "-q", SESION)
        return self.bash(f"git merge --no-ff -m 'Merge ABC-001/{CLAVE} mejora' {RAMA}")

    def test_merge_con_1_a_12_al_dia_pasa(self):
        self.r.cerrar_hasta(12)
        r = self.merge()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_merge_con_pasos_abiertos_se_bloquea(self):
        self.r.cerrar_hasta(9)
        r = self.merge()
        self.assertEqual(r.returncode, 2)
        self.assertIn("10, 11, 12", r.stderr)

    def test_merge_con_codigo_sin_revisar_se_bloquea(self):
        self.r.cerrar_hasta(12)
        self.r.cambio("app/algo.py", "def algo():\n    return 3\n", "fix: tarde")
        r = self.merge()
        self.assertEqual(r.returncode, 2)
        for n in ("10", "11", "12"):
            self.assertIn(f"el paso {n}", r.stderr)

    def test_merge_sin_checklist_se_bloquea(self):
        os.remove(os.path.join(sh(self.r.dir, "git", "rev-parse", "--path-format=absolute", "--git-common-dir").strip(),
                               "capitan", "ciclo", f"{CLAVE}.json"))
        r = self.merge()
        self.assertEqual(r.returncode, 2)
        self.assertIn("no tiene checklist", r.stderr)

    def test_comandos_que_solo_mencionan_merge_o_pr_no_se_revisan(self):
        self.r.cerrar_hasta(2)
        sh(self.r.dir, "git", "checkout", "-q", SESION)
        for comando in (f"git merge-base --is-ancestor {RAMA} HEAD",
                        'git commit -m "docs: explica gh pr create y git merge"',
                        "cat <<'FIN' > nota.md\ngh pr create --fill\ngit merge " + RAMA + "\nFIN",
                        "git merge --abort"):
            r = self.bash(comando)
            self.assertEqual(r.returncode, 0, f"{comando}: {r.stderr}")

    def test_merge_con_C_o_cd_tambien_se_revisa(self):
        self.r.cerrar_hasta(9)
        sh(self.r.dir, "git", "checkout", "-q", SESION)
        r = correr_hook("hook_ciclo.py", os.path.dirname(self.r.dir),
                        {"tool_input": {"command": f"git -C {os.path.basename(self.r.dir)} merge --no-ff {RAMA}"}})
        self.assertEqual(r.returncode, 2, r.stderr)
        r = correr_hook("hook_ciclo.py", self.r.dir,
                        {"tool_input": {"command": f"cd . && git -c core.x=1 merge {RAMA}"}})
        self.assertEqual(r.returncode, 2, r.stderr)

    def test_la_clave_sale_de_la_rama_registrada_en_el_paso_1(self):
        import hook_ciclo
        self.r.cerrar(1)
        self.assertEqual(hook_ciclo.clave_de(self.r.dir, RAMA, ""), CLAVE)
        self.assertEqual(hook_ciclo.clave_de(self.r.dir, "otra-act-1-x", ""), CLAVE)  # act-1 = ACT-001
        self.assertEqual(hook_ciclo.clave_de(self.r.dir, "sin-numero", "Merge ABC-001/ACT-044 algo"), "ACT-044")
        self.assertIsNone(hook_ciclo.clave_de(self.r.dir, "sin-numero", ""))

    def test_merge_fuera_de_la_rama_de_sesion_no_se_revisa(self):
        sh(self.r.dir, "git", "checkout", "-q", "main")
        self.assertEqual(self.bash(f"git merge {RAMA}").returncode, 0)

    def cerrar_sesion(self, copia=True, ci=True):
        self.r.cerrar_hasta(16)
        if copia:
            sh(self.r.dir, "git", "add", "docs/capitan/ciclo", "docs/capitan/estado.md")
            sh(self.r.dir, "git", "commit", "-q", "-m", "docs: relevo")
        if ci:
            ruta = ci_local.archivo_ok(self.r.dir)
            os.makedirs(os.path.dirname(ruta), exist_ok=True)
            with open(ruta, "a", encoding="utf-8") as f:
                f.write(sh(self.r.dir, "git", "rev-parse", "HEAD") + "\n")

    def test_pr_con_todo_cerrado_pasa(self):
        self.cerrar_sesion()
        r = self.bash("gh pr create --fill")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_pr_sin_ci_completo_se_bloquea(self):
        self.cerrar_sesion(ci=False)
        r = self.bash("gh pr create --fill")
        self.assertEqual(r.returncode, 2)
        self.assertIn("CI completo", r.stderr)

    def test_pr_sin_la_copia_se_bloquea(self):
        self.cerrar_sesion(copia=False)
        r = self.bash("gh pr create --fill")
        self.assertEqual(r.returncode, 2)
        self.assertIn(f"docs/capitan/ciclo/{CLAVE}.json", r.stderr)

    def test_pr_con_una_actividad_a_medias_se_bloquea(self):
        self.r.cerrar_hasta(13)
        r = self.bash("gh pr create --fill")
        self.assertEqual(r.returncode, 2)
        self.assertIn(f"{CLAVE}: pasos abiertos 14, 15, 16", r.stderr)


class HookBrief(unittest.TestCase):
    BRIEF = "Reglas que no se negocian en este encargo\n"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.r = RepoActividad(self.tmp.name)
        self.r.ciclo("crear", CLAVE)

    def tearDown(self):
        self.tmp.cleanup()

    def agente(self, prompt, tipo="general-purpose"):
        return correr_hook("hook_brief.py", self.r.dir,
                           {"tool_name": "Agent", "tool_input": {"subagent_type": tipo, "prompt": prompt}})

    def test_sin_brief_se_bloquea(self):
        self.assertIn("brief base", self.agente("Paso 3 de ACT-001").stderr)

    def test_sin_declarar_el_paso_se_bloquea(self):
        r = self.agente(self.BRIEF + "critica el plan")
        self.assertEqual(r.returncode, 2)
        self.assertIn("Paso 10 de ACT-012", r.stderr)

    def test_fuera_del_ciclo_pasa(self):
        self.assertEqual(self.agente(self.BRIEF + "Fuera del ciclo: escribir el plan del proyecto").returncode, 0)

    def test_paso_con_anteriores_abiertos_se_bloquea(self):
        self.r.cerrar_hasta(8)
        r = self.agente(self.BRIEF + "Paso 10 de ABC-001/ACT-001: corre las pruebas")
        self.assertEqual(r.returncode, 2)
        self.assertIn("abiertos los pasos 9", r.stderr)

    def test_paso_en_paralelo_con_su_par_abierto_pasa(self):
        self.r.cerrar_hasta(3)
        self.assertEqual(self.agente(self.BRIEF + "Paso 5 de ACT-001: plan de pruebas").returncode, 0)
        self.assertEqual(self.agente(self.BRIEF + "Paso 4 de ACT-001: crítica").returncode, 0)

    def test_paso_sin_checklist_se_bloquea(self):
        r = self.agente(self.BRIEF + "Paso 10 de ACT-077: pruebas")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no tiene checklist", r.stderr)

    def test_la_plantilla_completa_no_cuenta_como_declaracion(self):
        with open(os.path.join(RAIZ, "plantillas", "brief-agente.md"), encoding="utf-8") as f:
            plantilla = f.read()
        r = self.agente(plantilla + "\nHaz X, y revisa lo del paso 7 de ACT-001.")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertEqual(self.agente(plantilla + "\nPaso 3 de ACT-001: el plan").returncode, 2)  # 1 y 2 abiertos
        self.assertEqual(self.agente(plantilla + "\nFuera del ciclo: revisar el README").returncode, 0)

    def test_solo_lectura_sin_declarar_pasa(self):
        self.assertEqual(self.agente("busca dónde se define X", tipo="Explore").returncode, 0)

    def test_solo_lectura_que_declara_paso_tambien_respeta_el_orden(self):
        self.assertEqual(self.agente("Paso 4 de ACT-001: crítica", tipo="Plan").returncode, 2)


class CiPorArea(unittest.TestCase):
    AREAS = """
## CI por área

| Área | Rutas | Comando |
|---|---|---|
| app | `app/` | `echo '3 passed (app)'` |
| web | `web/` `paquete.json` | `echo '9 passed (web)'` |
"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.r = RepoActividad(self.tmp.name)
        sh(self.r.dir, "git", "checkout", "-q", "main")
        self.r.escribir(".claude/capitan.md", self.r_config() + self.AREAS)
        self.r.commit("areas")
        sh(self.r.dir, "git", "checkout", "-q", RAMA)
        sh(self.r.dir, "git", "merge", "-q", "main")

    def r_config(self):
        from repo_actividad import CONFIG
        return CONFIG.replace("`true`", "`echo '100 passed (todo)'`")

    def tearDown(self):
        self.tmp.cleanup()

    def ci(self, *args):
        return subprocess.run([sys.executable, os.path.join(SCRIPTS, "ci_local.py"), *args], cwd=self.r.dir,
                              capture_output=True, text=True)

    def registro(self):
        return open(os.path.join(ci_local.dir_capitan(self.r.dir), "ci-registro.log"), encoding="utf-8").read()

    def verdes(self):
        try:
            return open(ci_local.archivo_ok(self.r.dir), encoding="utf-8").read()
        except OSError:
            return ""

    def test_corre_solo_el_area_tocada(self):
        r = self.ci("--areas")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("3 passed (app)", r.stdout)
        self.assertNotIn("(web)", r.stdout)
        self.assertNotIn("(todo)", r.stdout)
        self.assertIn("áreas: app", self.registro())
        self.assertEqual(self.verdes(), "")  # una corrida por área no cuenta como CI completo

    def test_un_archivo_sin_area_corre_todo(self):
        self.r.cambio("Makefile", "x:\n", "build")
        r = self.ci("--areas")
        self.assertIn("100 passed (todo)", r.stdout)
        self.assertIn("Makefile", r.stdout)
        self.assertIn(sh(self.r.dir, "git", "rev-parse", "HEAD"), self.verdes())

    def test_solo_docs_no_corre_nada(self):
        sh(self.r.dir, "git", "checkout", "-q", "-b", "solo-docs", "main")
        self.r.escribir("docs/guia.md", "x\n")
        self.r.commit("docs")
        r = self.ci("--areas")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("sin código", self.registro())

    def test_sin_areas_en_la_config_corre_todo(self):
        sh(self.r.dir, "git", "checkout", "-q", "main")
        self.r.escribir(".claude/capitan.md", self.r_config())
        self.r.commit("sin areas")
        r = self.ci("--areas")
        self.assertIn("100 passed (todo)", r.stdout)

    def test_una_base_que_no_existe_corre_todo(self):
        r = self.ci("--areas", "--base", "mian")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("100 passed (todo)", r.stdout)
        self.assertNotIn("sin código", self.registro())

    def test_el_paso_12_lee_la_corrida_por_area(self):
        self.r.ciclo("crear", CLAVE)
        for n in range(1, 12):
            self.r.cerrar(n)
        self.assertEqual(self.ci("--areas").returncode, 0)
        r = self.r.ciclo("paso", CLAVE, "12", "--hecho", "CI por área")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("CI áreas: app", r.stdout)
        self.assertIn("«3 passed (app)»", r.stdout)


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
