#!/usr/bin/env python3
"""Revisa que el reporte de una sesión tenga TODO lo que pide el skill
capitan:trabajar. Si falta algo, sale con código 1 y dice qué: el reporte
no se publica hasta que pase.

Uso:
  python3 revisar_reporte.py <docs/capitan/sesiones/AAAA-MM-DD.md> <pagina.html> [<docs/capitan/sesiones/sesion-anterior.md>]

También revisa que docs/capitan/estado.md (el relevo para la conversación
siguiente) se haya reescrito en esta sesión.

Desde el 2026-10-05 exige además que la página salga de la plantilla del
plugin (scripts/reporte.py) y que «Necesito de ti» se pueda contestar.

Desde el 2026-10-18 cada actividad del .md exige su propia sección en la
página, reconocida por su eyebrow también cuando la clave del proyecto no
lleva número («TRACKER/ACT-020»): antes, con esa clave, se saltaba todas
las revisiones por actividad y aprobaba una página sin pruebas.

Nació el 2026-10-02: el primer reporte salió como un resumen sin pruebas ni
capturas, y el resultado de la sesión anterior no se había pasado a su
registro. Una lista que hay que recordar no se cumple; este script sí.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

GLOBALES_MD = {
    "## Resumen": "el resumen de la sesión",
    "**Fechas en riesgo:**": "las fechas en riesgo",
    "**Necesito de ti:**": "lo que necesitas del dueño",
    "**Resultado de la sesión anterior:**": "el resultado de las pruebas de la sesión anterior",
    "## Trabajo nuevo": "la tabla de trabajo nuevo (o la frase de que no hubo)",
    "## Hallazgos": "los hallazgos de la sesión",
    "**Pendientes para el dueño**": "los pendientes que solo el dueño puede probar",
    "## Lo que salió mal": "la sección de lo que salió mal en el proceso (aunque sea «nada»)",
}
POR_ACTIVIDAD_MD = {
    "**Tiempo y consumo:**": "tiempo y consumo",
    "**Agentes:**": "los agentes corridos",
    "### Qué se hizo": "qué se hizo",
    "**En simple:**": "la explicación en simple",
    "**Técnico:**": "lo técnico",
    "### Hallazgos": "hallazgos",
    "### Trabajo nuevo": "trabajo nuevo",
    "### Pruebas": "pruebas",
    "**1. Ejecutadas": "las pruebas ejecutadas",
    "**2. Para que lo veas:**": "qué ver en el ambiente de verificación",
    "### Qué no se probó": "qué no se probó",
}


# Clave del proyecto antes de la actividad en el eyebrow: «ABC-001/», «TRACKER/», «MI-APP/» o nada.
PREFIJO = r"(?:[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*/)?"


ESTADO_MD = {
    "**Actualizado:**": "la fecha de actualización",
    "## Dónde quedó": "dónde quedó el trabajo",
    "## Lo que sigue": "lo que sigue (la próxima actividad y por qué)",
    "## Esperando al dueño": "lo que espera una decisión o prueba del dueño",
    "## Cuidado": "las trampas abiertas que la conversación siguiente debe saber",
}


def revisar_estado(md_path: Path) -> list[str]:
    """El relevo es lo que lee una conversación nueva al abrir (hook
    SessionStart). Si no se reescribió hoy, la siguiente arranca a ciegas."""
    faltas: list[str] = []
    estado = md_path.resolve().parent.parent / "estado.md"
    if not estado.exists():
        return [f"[estado] no existe {estado}: el relevo para la conversación siguiente"]
    texto = estado.read_text(encoding="utf-8")
    for marca, que in ESTADO_MD.items():
        if marca not in texto:
            faltas.append(f"[estado] falta {que} («{marca}»)")
    fecha = re.match(r"\d{4}-\d{2}-\d{2}", md_path.name)
    m = re.search(r"\*\*Actualizado:\*\*\s*(\d{4}-\d{2}-\d{2})", texto)
    if fecha and (not m or m.group(1) != fecha.group(0)):
        faltas.append(f"[estado] no se reescribió en esta sesión (dice {m.group(1) if m else '—'}, la sesión es {fecha.group(0)})")
    return faltas


def revisar(md_path: Path, html_path: Path, anterior: Path | None) -> list[str]:
    faltas: list[str] = []
    md = md_path.read_text(encoding="utf-8")
    html = html_path.read_text(encoding="utf-8")

    for marca, que in GLOBALES_MD.items():
        if marca not in md:
            faltas.append(f"[md] falta {que} («{marca}»)")
    if not re.search(r"gast[óo]", md, re.IGNORECASE):
        faltas.append("[md] el consumo no dice lo GASTADO por la sesión (se reporta el delta, no el acumulado)")

    secciones = re.split(r"^## (?=ACT-\d+)", md, flags=re.MULTILINE)[1:]
    if not secciones:
        faltas.append("[md] no hay ninguna sección por actividad («## ACT-0xx · …»)")
    claves = []
    for sec in secciones:
        clave = sec.split(" ", 1)[0]
        claves.append(clave)
        for marca, que in POR_ACTIVIDAD_MD.items():
            if marca not in sec:
                faltas.append(f"[md] {clave}: falta {que} («{marca}»)")
        if not re.search(r"\d{1,2}:\d{2}\s*→\s*\d{1,2}:\d{2}", sec):
            faltas.append(f"[md] {clave}: el tiempo no trae hora de inicio → cierre medida")
        if not re.search(r"roj[ao]s?|fall[aó]\w* (contra|antes)|antes del arreglo", sec, re.IGNORECASE):
            faltas.append(f"[md] {clave}: las pruebas no dicen cómo se vieron fallar contra el código anterior")

    # La sección DE una actividad: su eyebrow es la clave, con o sin la del proyecto
    # («ABC-001/ACT-053», «TRACKER/ACT-053» o «ACT-053» con el tablero local).
    con_seccion = set(re.findall(r'<section class="act"[^>]*>\s*<p class="eyebrow">' + PREFIJO + r'(ACT-\d+)</p>', html))
    for clave in claves:
        if clave not in con_seccion:
            faltas.append(f"[html] falta la sección de {clave} (<section class=\"act\"> con su eyebrow)")
    if "capitan:reporte-sesion" not in html:
        faltas.append("[html] la página no salió de la plantilla del plugin (scripts/reporte.py)")
    # Con atributos o sin ellos: la plantilla las abre como <section class="act" id=… hidden>
    for bloque in re.split(r'<section class="act"[^>]*>', html)[1:]:
        # Solo las secciones DE una actividad: su eyebrow es la clave
        # («ABC-001/ACT-053», o «ACT-053» con el tablero local); las de tablas (trabajo nuevo, hallazgos)
        # mencionan claves pero no son de una actividad.
        m = re.match(r'\s*<p class="eyebrow">' + PREFIJO + r'(ACT-\d+)</p>', bloque)
        if not m:
            continue
        if "Pruebas ejecutadas" not in bloque:
            faltas.append(f"[html] {m.group(1)}: faltan las pruebas ejecutadas")
        if "<figure>" not in bloque and "Sin capturas" not in bloque:
            faltas.append(f"[html] {m.group(1)}: ni capturas ni la nota de que no tiene pantalla")
        for fig in re.findall(r"<figure>.*?</figure>", bloque, re.DOTALL):
            cap = re.search(r"<figcaption>(.*?)</figcaption>", fig, re.DOTALL)
            if not cap or len(re.sub(r"<[^>]+>", "", cap.group(1)).strip()) < 30:
                faltas.append(f"[html] {m.group(1)}: una captura sin juicio escrito")
            if re.search(r"se ve bien", fig, re.IGNORECASE):
                faltas.append(f"[html] {m.group(1)}: un juicio que dice «se ve bien» (prohibido)")
    if 'class="pend"' not in html:
        faltas.append("[html] faltan los pendientes del dueño con botones Pasó/Falló")
    if 'class="b-paso"' not in html or "<textarea" not in html:
        faltas.append("[html] los pendientes no tienen botones o comentario")

    # Cada hallazgo ABIERTO trae su solución recomendada completa, a la vista
    # (decisión del dueño, 2026-10-08: «explica más detalle de la solución
    # recomendada, siempre»).
    for bloque in re.findall(r'<li class=.hall abierto.*?</li>(?=<li class=.hall|</ul>)', html, re.DOTALL):
        hid = re.search(r'id="hall-([^"]*)"', bloque)
        nombre = hid.group(1) if hid else "?"
        sol = re.search(r'<div class="solucion">(.*?)</div>', bloque, re.DOTALL)
        if not sol:
            faltas.append(f"[html] hallazgo {nombre}: abierto sin solución recomendada a la vista")
            continue
        for rotulo in ("Qué cambiaría", "Cómo, paso a paso", "Qué vas a notar tú",
                       "Qué pasa si no se hace", "Cómo sabremos que quedó", "Cuándo y en qué actividad"):
            if rotulo not in sol.group(1):
                faltas.append(f"[html] hallazgo {nombre}: a la solución le falta «{rotulo}»")
    if 'id="nec-aviso"' not in html:
        faltas.append("[html] falta «Necesito de ti» con sus botones de respuesta")
    zona = html.split('id="nec-aviso"', 1)[0]
    for li in zona.split('<li class="nec ')[1:]:
        nid = re.search(r'data-id="([^"]+)"', li)
        if 'class="b-op"' not in li or 'class="b-duda"' not in li or "<textarea" not in li:
            faltas.append(f"[html] necesito {nid.group(1) if nid else '?'}: sin respuesta, «Tengo dudas» o comentario")

    faltas += revisar_estado(md_path)

    if anterior is not None and anterior.exists():
        if re.search(r"Resultado: _{2,}", anterior.read_text(encoding="utf-8")):
            faltas.append(f"[{anterior.name}] hay resultados de la sesión anterior sin pasar a su registro")
    return faltas


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    anterior = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    faltas = revisar(Path(sys.argv[1]), Path(sys.argv[2]), anterior)
    if faltas:
        print("El reporte NO está completo — no se publica:")
        for f in faltas:
            print(" -", f)
        return 1
    print("Reporte completo: tiene todo lo que pide el skill.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
