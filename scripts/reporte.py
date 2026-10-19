#!/usr/bin/env python3
"""Arma el reporte de una sesión —el .md y la página— desde UNA sola fuente:
el `sesion.json` que se va llenando en el paso 16 del ciclo.

Uso:
  python3 reporte.py <sesion.json> --md docs/capitan/sesiones/AAAA-MM-DD.md --html <pagina.html>
  python3 reporte.py --ejemplo        # imprime un sesion.json mínimo para copiar

La página sale de `plantillas/reporte-sesion.html` (estilos y scripts fijos);
este script solo pone el contenido. Así todos los proyectos entregan la misma
página: pestañas Resumen · Actividades · Hallazgos · Pendientes · Lo que salió
mal; «Necesito de ti» con botones para contestar (opciones, «Ya lo hice»,
«Tengo dudas» y comentario); tarjetas por actividad en el orden de la sesión
con «Marcar como leída»; fichas de prueba con «Contra el código anterior»; y
pendientes con Pasó/Falló, comentario y evidencia.

La página se publica con capabilities {db, assets, user}. Lo que el dueño
contesta queda en la base de la página:
  necesito/<id>   {respuesta, dudas, comentario, actualizado}
  resultados/<id> {estado: paso|fallo, comentario, evidencias, actividad, cuando}
  lectura/actividades {claves: [...]}

Texto: todo se escapa. Dentro de cualquier texto se puede usar `código` y
**negritas**; nada más.

Nació el 2026-10-05: cada sesión armaba la página a mano y cada proyecto
entregaba una distinta. El dueño: «hay que ponerle plantilla al plugin».
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import re
import sys
from pathlib import Path

PLANTILLA = Path(__file__).resolve().parent.parent / "plantillas" / "reporte-sesion.html"

TIPOS_NEC = {
    "merge": "Merge",
    "decision": "Decisión",
    "aprobacion": "Aprobación",
    "accion": "Hacer tú",
    "bloqueo": "Te bloquea",
    "piloto": "Antes de salir",
    "opcional": "Opcional",
}
RESPUESTAS = {
    "si_no": [{"v": "si", "t": "Sí"}, {"v": "no", "t": "No"}],
    "hecho": [{"v": "hecho", "t": "Ya lo hice"}],
}
SEVERIDADES = ["critico", "alto", "medio", "moderado", "bajo", "info", "deuda"]
SEV_TEXTO = {"critico": "Crítico", "alto": "Alto", "medio": "Medio", "moderado": "Moderado",
             "bajo": "Bajo", "info": "Info", "deuda": "Deuda"}

EJEMPLO = {
    "proyecto": "mi-proyecto",
    "clave_proyecto": "ABC-001",
    "fecha": "2026-10-05",
    "titulo": "Lo que cambió hoy, en una frase",
    "dueno": "Ana",
    "pr": {"numero": 56, "url": "https://github.com/org/repo/pull/56"},
    "ci": "CI local verde",
    "tiempo": "10:30 → 12:45 (2 h 15 min)",
    "uso": {"gasto": "La sesión gastó 5 puntos de la semana (65 % → 70 %)", "cinco_horas": "+21 y +7 tras el reinicio"},
    "resultado_anterior": "Nadie marcó resultados en la página anterior.",
    "fechas_en_riesgo": ["ACT-077 (10-06): espera tus decisiones."],
    "sin_terminar": "ACT-077 no se pudo empezar.",
    "datos": [{"dt": "CI local", "dd": "backend 1549 · vitest 972"}],
    "necesito": [
        {"id": "merge-56", "tipo": "merge", "etiqueta": "PR #56", "texto": "Merge del PR de la sesión",
         "por_que": "Mientras no se mergee, nada llega al ambiente de pruebas.",
         "que_haria": "Botón «Merge pull request» con *Create a merge commit*.", "respuesta": "hecho"},
        {"id": "freno", "tipo": "decision", "texto": "¿Qué hace el freno si se cae Redis?",
         "por_que": "…", "que_haria": "Recomiendo b.", "enlace": "act-048",
         "opciones": [{"v": "a", "t": "a) Dejar buscar"}, {"v": "b", "t": "b) Bloquear"}]},
    ],
    "partes": [{"id": "manana", "nombre": "Mañana", "horas": "10:30 → 12:45", "uso": "+5 pts",
                "actividades": ["ACT-048"]}],
    "actividades": [{
        "clave": "ACT-048", "titulo": "Contactos con datos completos", "columna": "Revisión de código",
        "inicio": "12:05", "cierre": "12:38", "consumo": "5 h +7 · semana +1",
        "agentes": "crítico (opus) · probador (sonnet) · seguridad (opus)",
        "resumen": "Una o dos líneas para la tarjeta.",
        "simple": "Qué cambió para quien lo usa, sin jerga.",
        "tecnico": ["Archivos, funciones, decisiones."],
        "para_ti": "Lo que el dueño tiene que hacer o decidir de esta actividad (opcional).",
        "hallazgos": ["Cerrados 105 y 106."], "trabajo_nuevo": [],
        "pruebas": [{"que": "Busco un teléfono como Lector 31 veces en un minuto.", "esperado": "La 31 se frena (429).",
                     "real": "429 en la 31.", "resultado": "paso", "antes": "Pasaban las 600."}],
        "capturas": [{"src": "capturas/048-admin.jpg", "alt": "Lista de contactos", "juicio": "Qué se ve y por qué está bien o mal (≥30 caracteres; prohibido «se ve bien»)."}],
        "sin_capturas": "",
        "para_que_lo_veas": "Contactos en el ambiente de pruebas.",
        "pendientes": ["048-1"],
        "no_probado": "El nginx del servidor.",
    }],
    "hallazgos": [{"id": "105", "titulo": "La búsqueda servía de oráculo", "severidad": "medio", "estado": "cerrado",
                   "estado_texto": "Corregido", "actividad": "ACT-048", "simple": "…", "donde": "console_api.py",
                   "evidencia": "…",
                   "solucion": {"que_cambia": "…", "como": ["paso 1", "paso 2"], "para_ti": "…",
                                "si_no": "…", "prueba": "…", "cuando": "ACT-0xx, antes de …"}}],
    "trabajo_nuevo": [{"clave": "ACT-081", "titulo": "…", "estado": "cerrado", "estado_texto": "Hecha hoy",
                       "donde_va": "junto a ACT-074: …", "fecha": "10-06", "de_donde": "E2E de ACT-074"}],
    "pendientes": [{"id": "048-1", "actividad": "ACT-048", "titulo": "Buscar un correo en Contactos",
                    "pasos": "…", "debe_pasar": "…", "origen": ""}],
    "salio_mal": [{"que": "…", "regla": "…"}],
}


# ── texto ──────────────────────────────────────────────────────────────────

def e(s: object) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def t(s: object) -> str:
    """Escapa y luego permite `código` y **negritas**."""
    out = e(s)
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    out = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", out)
    return out


def lista(v: object) -> list[str]:
    if v is None or v == "":
        return []
    return [str(x) for x in v] if isinstance(v, list) else [str(v)]


def ancla(clave: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", clave.lower()).strip("-")
    return base if base.startswith("act-") else f"act-{base}"


def es_act(clave: str) -> bool:
    return bool(re.fullmatch(r"ACT-\d+", clave))


def plural(n: int, uno: str, varios: str) -> str:
    return f"{n} {uno if n == 1 else varios}"


# ── piezas de la página ──────────────────────────────────────────────────────

def cabecera(s: dict, n_act: int) -> str:
    franja = []
    pr = s.get("pr")
    if pr:
        franja.append(f'<li><span class="lbl">PR</span><a href="{e(pr["url"])}">#{e(pr["numero"])}</a></li>')
    if s.get("ci"):
        franja.append(f'<li><span class="lbl">CI</span><span class="ok">{t(s["ci"])}</span></li>')
    franja.append(f'<li><span class="lbl">Actividades</span><b class="num">{plural(n_act, "actividad", "actividades")}</b></li>')
    if s.get("tiempo"):
        franja.append(f'<li><span class="lbl">Tiempo</span><span class="num">{t(s["tiempo"])}</span></li>')
    uso = s.get("uso") or {}
    if uso.get("gasto"):
        franja.append(f'<li><span class="lbl">Uso gastado</span><span class="num">{t(uso["gasto"])}</span></li>')
    eyebrow = " · ".join(x for x in ["Método Capitán", s.get("proyecto"), f"sesión {s['fecha']}"] if x)
    return (f'<header class="cab"><p class="eyebrow">{e(eyebrow)}</p><h1>{t(s["titulo"])}</h1>'
            f'<ul class="franja">{"".join(franja)}</ul></header>')


def pestanas(n_act: int, n_nec: int, n_abiertos: int, n_pend: int) -> str:
    def b(tab, txt, extra="", sel=False):
        return (f'<button type="button" role="tab" data-tab="{tab}" aria-selected="{str(sel).lower()}">'
                f'{txt}{extra}</button>')
    return ('<nav class="tabs" role="tablist" aria-label="Secciones del reporte">'
            + b("resumen", "Resumen", f' <span class="cuenta warn" title="Por responder"><span class="n-necesito">{n_nec}</span></span>', True)
            + b("actividades", "Actividades", f' <span class="cuenta"><span class="n-leidas-tab">0</span>/{n_act} leídas</span>')
            + b("hallazgos", "Hallazgos", f' <span class="cuenta">{plural(n_abiertos, "abierto", "abiertos")}</span>')
            + b("pendientes", "Pendientes", f' <span class="cuenta">{n_pend}</span>')
            + b("salio-mal", "Lo que salió mal")
            + "</nav>")


def necesito(items: list[dict], dueno: str) -> str:
    lis = []
    for n in items:
        tipo = n.get("tipo", "decision")
        etiqueta = n.get("etiqueta") or TIPOS_NEC.get(tipo, tipo)
        ops = n.get("opciones") or RESPUESTAS[n.get("respuesta") or ("hecho" if tipo in ("merge", "accion") else "si_no")]
        titulo = (f'<a href="#{e(n["enlace"])}" class="nec-txt">{t(n["texto"])}</a>' if n.get("enlace")
                  else f'<span class="nec-txt">{t(n["texto"])}</span>')
        cuerpo = [titulo]
        if n.get("por_que"):
            cuerpo.append(f'<p><b>Por qué:</b> {t(n["por_que"])}</p>')
        if n.get("detalle"):
            cuerpo.append("<ol>" + "".join(f"<li>{t(x)}</li>" for x in lista(n["detalle"])) + "</ol>")
        if n.get("que_haria"):
            cuerpo.append(f'<p><b>Qué haría yo:</b> {t(n["que_haria"])}</p>')
        botones = "".join(f'<button type="button" class="b-op" data-v="{e(o["v"])}" aria-pressed="false">{t(o["t"])}</button>' for o in ops)
        cuerpo.append(
            f'<div class="acciones nec-resp" role="group" aria-label="Tu respuesta: {e(re.sub(r"[`*]", "", n["texto"]))}">'
            f'{botones}<button type="button" class="b-duda" aria-pressed="false">Tengo dudas</button>'
            f'<span class="estado" aria-live="polite">Sin responder</span></div>'
            f'<label for="n-{e(n["id"])}">Comentario o duda</label>'
            f'<textarea id="n-{e(n["id"])}" rows="2" placeholder="Escribe aquí tu duda, o si quieres algo distinto"></textarea>')
        lis.append(f'<li class="nec {e(tipo)}" data-id="{e(n["id"])}" id="nec-{e(n["id"])}">'
                   f'<span class="nec-tipo">{t(etiqueta)}</span><div class="nec-cuerpo">{"".join(cuerpo)}</div></li>')
    return ('<div class="bloque necesito"><h2>Necesito de ti</h2>'
            f'<p class="tenue">Cada punto explica por qué y qué haría yo. Contesta con un botón o márcalo como hecho; '
            f'si algo no queda claro, pica «Tengo dudas» y escríbelas. Lo leo al empezar la siguiente sesión.</p>'
            f'<ol class="nec-lista">{"".join(lis)}</ol><p class="aviso" id="nec-aviso" hidden></p></div>')


def como_fue(s: dict, partes: list[dict]) -> str:
    ps = []
    for p in partes:
        acts = "".join(f'<a href="#{ancla(c)}">{e(c)}</a>' for c in p["actividades"])
        ps.append(f'<div class="parte"><div class="p-cab"><b>{t(p["nombre"])}</b><span class="num">{t(p.get("horas", ""))}</span>'
                  f'<span class="tenue">{t(p.get("uso", ""))}</span></div><div class="p-acts">{acts}</div></div>')
    datos = [("Resultado de la sesión anterior", s.get("resultado_anterior") or "—")]
    fr = lista(s.get("fechas_en_riesgo"))
    datos.append(("Fechas en riesgo", " · ".join(fr) if fr else "Ninguna."))
    if s.get("sin_terminar"):
        datos.append(("Sin terminar", s["sin_terminar"]))
    uso = s.get("uso") or {}
    if uso.get("cinco_horas"):
        datos.append(("Ventana de 5 horas", uso["cinco_horas"]))
    datos += [(d["dt"], d["dd"]) for d in s.get("datos", [])]
    dl = "".join(f"<div><dt>{t(a)}</dt><dd>{t(b)}</dd></div>" for a, b in datos)
    return f'<div class="bloque"><h2>Cómo fue la sesión</h2><div class="partes">{"".join(ps)}</div><dl class="datos">{dl}</dl></div>'


def resumen_pruebas(a: dict) -> str:
    pr = a.get("pruebas", [])
    pasaron = sum(1 for p in pr if p.get("resultado", "paso") == "paso")
    antes = sum(1 for p in pr if p.get("antes"))
    txt = f"{pasaron}/{len(pr)} pruebas pasaron"
    return txt + (f" · {antes} {'falló' if antes == 1 else 'fallaron'} antes" if antes else "")


def tarjeta(a: dict, paso: int, total: int, parte: str) -> str:
    para = "si" if a.get("para_ti") else "no"
    pie = [f'<span class="num">{e(a.get("inicio", ""))} → {e(a.get("cierre", ""))}</span>', f'<span class="num">{resumen_pruebas(a)}</span>']
    if para == "si":
        pie.append('<span class="flag">Decisión para ti</span>')
    return (f'<a class="tarjeta" href="#{ancla(a["clave"])}" data-clave="{ancla(a["clave"])}" data-parte="{e(parte)}" data-para="{para}">'
            f'<span class="t-top"><span class="paso num" aria-label="Atendida en el lugar {paso} de {total}">{paso}</span>'
            f'<span class="clave">{e(a["clave"])}</span><span class="visto">✓ Leída</span><span class="pill">{e(a.get("columna", ""))}</span></span>'
            f'<span class="t-tit">{t(a["titulo"])}</span><span class="t-res">{t(a.get("resumen") or a.get("simple", ""))}</span>'
            f'<span class="t-pie">{"".join(pie)}</span></a>')


def ficha(p: dict, n: int) -> str:
    ok = p.get("resultado", "paso") == "paso"
    antes = (f'<div class="antes"><span class="lbl">Contra el código anterior</span><p>{t(p["antes"])}</p></div>'
             if p.get("antes") else "")
    return (f'<li class="prueba"><div class="pr-cab"><span class="pr-n num">{n}</span><p class="pr-que">{t(p["que"])}</p>'
            f'<span class="est-p {"paso" if ok else "fallo"}">{"✓ Pasó" if ok else "✗ Falló"}</span></div>'
            f'<div class="pr-res"><div><span class="lbl">Resultado esperado</span><p>{t(p.get("esperado", ""))}</p></div>'
            f'<div><span class="lbl">Resultado real</span><p>{t(p.get("real", ""))}</p></div></div>{antes}</li>')


def imagen(src: str, base: Path, incrustar: bool) -> str:
    if not incrustar or src.startswith(("data:", "http")):
        return src
    ruta = (base / src).resolve()
    tipo = mimetypes.guess_type(ruta.name)[0] or "image/jpeg"
    return f"data:{tipo};base64," + base64.b64encode(ruta.read_bytes()).decode()


def seccion_act(a: dict, s: dict, paso: int, total: int, parte_nombre: str, sig: dict | None, base: Path, incrustar: bool) -> str:
    clave = a["clave"]
    eyebrow = f'{s["clave_proyecto"]}/{clave}' if s.get("clave_proyecto") and es_act(clave) else clave
    meta = [f'<span class="num">{e(a.get("inicio", ""))} → {e(a.get("cierre", ""))}</span>']
    if a.get("consumo"):
        meta.append(f'<span class="num">Consumo: {t(a["consumo"])}</span>')
    if a.get("agentes"):
        meta.append(f'<span>Agentes: {t(a["agentes"])}</span>')
    partes = [
        f'<section class="act" id="{ancla(clave)}" hidden>',
        f'<p class="eyebrow">{e(eyebrow)}</p>',
        f'<div class="d-barra"><a href="#actividades" class="volver">← Actividades</a>'
        f'<span class="tenue num">{paso} de {total} en el orden de la sesión · {t(parte_nombre)}</span>'
        f'<button type="button" class="b-leida" data-clave="{ancla(clave)}" aria-pressed="false">Marcar como leída</button></div>',
        f'<div class="d-cab"><h2>{t(a["titulo"])}</h2><span class="pill">{e(a.get("columna", ""))}</span></div>',
        f'<p class="meta">{"".join(meta)}</p>',
        f'<p class="simple"><b>En simple:</b> {t(a.get("simple", ""))}</p>',
    ]
    tec = lista(a.get("tecnico"))
    if tec:
        partes.append('<details class="tec"><summary>Detalle técnico</summary><div class="tec-cuerpo">'
                      + "".join(f"<p>{t(x)}</p>" for x in tec) + "</div></details>")
    if a.get("para_ti"):
        partes.append(f'<div class="para-ti"><span class="lbl">Para ti</span><p>{t(a["para_ti"])}</p></div>')
    pr = a.get("pruebas", [])
    pasaron = sum(1 for p in pr if p.get("resultado", "paso") == "paso")
    partes.append(f'<div class="d-bloque"><h3>Pruebas ejecutadas <span class="tenue num">{pasaron} de {len(pr)} pasaron</span></h3>'
                  f'<ol class="pruebas">{"".join(ficha(p, i + 1) for i, p in enumerate(pr))}</ol>')
    caps = a.get("capturas", [])
    if caps:
        figs = "".join(f'<figure><img src="{e(imagen(c["src"], base, incrustar))}" alt="{e(c.get("alt", ""))}" loading="lazy">'
                       f'<figcaption>{t(c["juicio"])}</figcaption></figure>' for c in caps)
        partes.append(f'<div class="capturas">{figs}</div>')
    else:
        partes.append(f'<p class="tenue">Sin capturas: {t(a.get("sin_capturas") or "no tiene pantalla")}.</p>')
    partes.append("</div>")
    for titulo, campo in (("Hallazgos", "hallazgos"), ("Trabajo nuevo", "trabajo_nuevo")):
        items = lista(a.get(campo))
        if items:
            partes.append(f'<div class="d-bloque"><h3>{titulo}</h3><ul>' + "".join(f"<li>{t(x)}</li>" for x in items) + "</ul></div>")
    if a.get("para_que_lo_veas"):
        partes.append(f'<div class="d-bloque"><h3>Para que lo veas</h3><p>{t(a["para_que_lo_veas"])}</p></div>')
    pend = lista(a.get("pendientes"))
    if pend:
        links = ", ".join(f'<a href="#pend-{e(p)}">{e(p)}</a>' for p in pend)
        partes.append(f'<div class="d-bloque"><h3>Pendientes para ti</h3><p>{links}, en la pestaña Pendientes.</p></div>')
    partes.append(f'<div class="d-bloque"><h3>Qué no se probó</h3><p>{t(a.get("no_probado") or "—")}</p></div>')
    if sig:
        partes.append(f'<nav class="d-nav" aria-label="Otras actividades"><span></span><a href="#{ancla(sig["clave"])}" class="b-leida-sig" '
                      f'data-clave="{ancla(clave)}">Leída · siguiente: {e(sig["clave"])} →</a></nav>')
    else:
        partes.append(f'<nav class="d-nav" aria-label="Otras actividades"><span></span><a href="#actividades" class="b-leida-sig" '
                      f'data-clave="{ancla(clave)}">Leída · volver a la lista →</a></nav>')
    partes.append("</section>")
    return "".join(partes)


def panel_actividades(s: dict, acts: list[dict], partes: list[dict], base: Path, incrustar: bool) -> str:
    por_clave = {a["clave"]: a for a in acts}
    orden = [(c, p) for p in partes for c in p["actividades"]]
    total = len(orden)
    filtros = ['<button type="button" data-f="todas" aria-pressed="true">Todas</button>']
    if len(partes) > 1:
        filtros += [f'<button type="button" data-f="{e(p["id"])}" aria-pressed="false">{t(p["nombre"])}</button>' for p in partes]
    filtros += ['<button type="button" data-f="para" aria-pressed="false">Con decisión para ti</button>',
                '<button type="button" data-f="sinleer" aria-pressed="false">Sin leer</button>',
                f'<span class="progreso num" aria-live="polite"><span id="n-leidas">0</span> de {total} leídas</span>']
    grupos, secciones, paso = [], [], 0
    for p in partes:
        tarjetas = []
        for c in p["actividades"]:
            paso += 1
            tarjetas.append(tarjeta(por_clave[c], paso, total, p["id"]))
        grupos.append(f'<div class="grupo" data-parte="{e(p["id"])}"><div class="g-cab"><h3>{t(p["nombre"])}</h3>'
                      f'<span class="num">{t(p.get("horas", ""))}</span><span class="tenue">{plural(len(p["actividades"]), "actividad", "actividades")}'
                      f'{" · " + t(p["uso"]) if p.get("uso") else ""}</span></div><div class="rejilla">{"".join(tarjetas)}</div></div>')
    for i, (c, p) in enumerate(orden):
        sig = por_clave[orden[i + 1][0]] if i + 1 < total else None
        secciones.append(seccion_act(por_clave[c], s, i + 1, total, p["nombre"], sig, base, incrustar))
    return ('<section class="panel" id="actividades" role="tabpanel" hidden>'
            f'<div class="filtros" role="group" aria-label="Filtrar actividades">{"".join(filtros)}</div>'
            '<p class="orden-nota tenue">En el orden en que se atendieron: el número de cada tarjeta es su lugar en la sesión.</p>'
            f'<div class="grupos">{"".join(grupos)}</div>{"".join(secciones)}</section>')


def enlace_act(clave: str, claves: set[str]) -> str:
    return f'<a href="#{ancla(clave)}">{e(clave)}</a>' if clave in claves else f'<span class="mono">{e(clave)}</span>'


#: La solución recomendada de un hallazgo ABIERTO, completa. Una línea técnica
#: suelta no le dice al dueño qué va a pasar ni por qué importa.
PARTES_SOLUCION = (
    ("que_cambia", "Qué cambiaría"),
    ("como", "Cómo, paso a paso"),
    ("para_ti", "Qué vas a notar tú"),
    ("si_no", "Qué pasa si no se hace"),
    ("prueba", "Cómo sabremos que quedó"),
    ("cuando", "Cuándo y en qué actividad"),
)


def solucion_html(sol: object) -> str:
    """La solución recomendada como bloque visible (no plegado)."""
    if not isinstance(sol, dict):
        return f'<div class="solucion"><span class="lbl">Solución recomendada</span><p>{t(sol)}</p></div>' if sol else ""
    filas = []
    for llave, rotulo in PARTES_SOLUCION:
        valor = sol.get(llave)
        if not valor:
            continue
        if isinstance(valor, list):
            cuerpo = "<ol>" + "".join(f"<li>{t(x)}</li>" for x in valor) + "</ol>"
        else:
            cuerpo = f"<p>{t(valor)}</p>"
        filas.append(f"<dt>{rotulo}</dt><dd>{cuerpo}</dd>")
    return f'<div class="solucion"><span class="lbl">Solución recomendada</span><dl>{"".join(filas)}</dl></div>'


def solucion_md(sol: object) -> list[str]:
    if not isinstance(sol, dict):
        return [f"**Solución recomendada:** {sol}"] if sol else []
    out = ["**Solución recomendada:**", ""]
    for llave, rotulo in PARTES_SOLUCION:
        valor = sol.get(llave)
        if isinstance(valor, list):
            out.append(f"- **{rotulo}:**")
            out += [f"  {i}. {x}" for i, x in enumerate(valor, 1)]
        elif valor:
            out.append(f"- **{rotulo}:** {valor}")
    return out


def panel_hallazgos(s: dict, claves: set[str]) -> str:
    hs = sorted(s.get("hallazgos", []), key=lambda h: (h.get("estado") != "abierto", SEVERIDADES.index(h.get("severidad", "info"))))
    lis = []
    for h in hs:
        abierto = h.get("estado") == "abierto"
        # Abierto: la solución va completa y a la vista. Cerrado: lo aplicado,
        # dentro del detalle técnico.
        dl_campos = (("Dónde", "donde"), ("Evidencia", "evidencia")) + (
            () if abierto else (("Solución aplicada", "solucion"),)
        )
        dl = "".join(
            f"<dt>{k}</dt><dd>{t(h[c]) if not isinstance(h[c], dict) else t(h[c].get('que_cambia', ''))}</dd>"
            for k, c in dl_campos
            if h.get(c)
        )
        num = f'<span class="mono">#{e(h["id"])}</span>' if h.get("id") else ""
        act = enlace_act(h["actividad"], claves) if h.get("actividad") else ""
        lis.append(f'<li class="hall{" abierto" if abierto else ""}" id="hall-{e(h.get("id", ""))}"><div class="h-cab">'
                   f'<span class="sev {e(h.get("severidad", "info"))}">{SEV_TEXTO.get(h.get("severidad", "info"), "")}</span>{num}'
                   f'<b class="h-tit">{t(h["titulo"])}</b><span class="est {"abierto" if abierto else "cerrado"}">{t(h.get("estado_texto") or ("Abierto" if abierto else "Corregido"))}</span>{act}</div>'
                   f'<p>{t(h.get("simple", ""))}</p>'
                   + (solucion_html(h.get("solucion")) if abierto else "")
                   + (f'<details class="tec"><summary>Detalle técnico</summary><div class="tec-cuerpo"><dl class="h-dl">{dl}</dl></div></details>' if dl else "")
                   + "</li>")
    nuevos = []
    for n in s.get("trabajo_nuevo", []):
        cerrado = n.get("estado") == "cerrado"
        nuevos.append(f'<li class="nuevo"><div class="h-cab">{enlace_act(n["clave"], claves)}<b class="h-tit">{t(n["titulo"])}</b>'
                      f'<span class="est {"cerrado" if cerrado else "abierto"}">{t(n.get("estado_texto") or ("Hecha" if cerrado else "Backlog"))}</span></div>'
                      f'<p><span class="tenue">Dónde va y por qué:</span> {t(n.get("donde_va", ""))}'
                      f'{" · <span class=tenue>fecha</span> " + t(n["fecha"]) if n.get("fecha") else ""}</p>'
                      + (f'<details class="tec"><summary>Detalle técnico</summary><div class="tec-cuerpo"><p><b>De dónde salió:</b> {t(n["de_donde"])}</p></div></details>' if n.get("de_donde") else "")
                      + "</li>")
    vacio_h = '<p class="tenue">Ninguno en esta sesión.</p>'
    vacio_n = '<p class="tenue">No nació trabajo nuevo en esta sesión.</p>'
    return ('<section class="panel" id="hallazgos" role="tabpanel" hidden>'
            '<div class="bloque"><h2>Hallazgos</h2><p class="tenue">Primero los abiertos, por gravedad. Cada uno en simple; el detalle técnico se despliega.</p>'
            + (f'<ul class="halls">{"".join(lis)}</ul>' if lis else vacio_h) + "</div>"
            '<div class="bloque"><h2>Trabajo nuevo</h2><p class="tenue">Actividades que nacieron en esta sesión, qué son y por qué van donde van.</p>'
            + (f'<ul class="halls">{"".join(nuevos)}</ul>' if nuevos else vacio_n) + "</div></section>")


def panel_pendientes(s: dict) -> str:
    cards = []
    for p in s.get("pendientes", []):
        pid = e(p["id"])
        origen = f' <span class="tenue">· {t(p["origen"])}</span>' if p.get("origen") else ""
        cards.append(
            f'<article class="pend" data-id="{pid}" id="pend-{pid}"><header><span class="clave">{e(p["actividad"])}</span>'
            f'<h3>{t(p["titulo"])}</h3><span class="mono">{pid}</span>{origen}</header>'
            f'<p><b>Pasos:</b> {t(p["pasos"])}</p><p><b>Qué debe pasar:</b> {t(p["debe_pasar"])}</p>'
            '<div class="acciones"><button type="button" class="b-paso" data-estado="paso" aria-pressed="false">Pasó</button>'
            '<button type="button" class="b-fallo" data-estado="fallo" aria-pressed="false">Falló</button>'
            '<span class="estado" aria-live="polite">Resultado: sin marcar</span></div>'
            f'<label for="c-{pid}">Comentario</label><textarea id="c-{pid}" rows="2" placeholder="Qué viste, sobre todo si falló o no lo pudiste hacer. Puedes pegar una captura aquí (Ctrl+V)."></textarea>'
            f'<div class="evid" hidden><div class="evid-lista"></div><label class="evid-subir" for="f-{pid}">Subir imágenes de evidencia</label>'
            f'<input type="file" id="f-{pid}" accept="image/png,image/jpeg,image/gif,image/webp" multiple>'
            '<span class="evid-estado tenue" aria-live="polite"></span></div></article>')
    dueno = s.get("dueno") or "el dueño"
    return ('<section class="panel" id="pendientes" role="tabpanel" hidden>'
            f'<div class="bloque"><h2>Pendientes para {e(dueno)}</h2><p class="tenue">Solo lo que yo no puedo probar: tu login, '
            'que algo llegue de verdad a tu teléfono o bandeja, tu criterio. Lo que falle se vuelve actividad nueva.</p>'
            '<p class="aviso" id="aviso-db">Cargando dónde guardar tus resultados…</p></div>'
            f'<div class="pends">{"".join(cards)}</div></section>')


def panel_salio_mal(s: dict) -> str:
    lis = "".join(f'<li><p>{t(m["que"])}</p><p class="regla"><span class="lbl">Regla</span>{t(m["regla"])}</p></li>' for m in s.get("salio_mal", []))
    cuerpo = f'<ol class="mal">{lis}</ol>' if lis else '<p class="tenue">Nada que anotar en esta sesión.</p>'
    return f'<section class="panel" id="salio-mal" role="tabpanel" hidden><div class="bloque"><h2>Lo que salió mal</h2>{cuerpo}</div></section>'


def partes_de(s: dict) -> list[dict]:
    partes = s.get("partes") or [{"id": "sesion", "nombre": "La sesión", "horas": s.get("tiempo", ""),
                                  "actividades": [a["clave"] for a in s["actividades"]]}]
    claves = {a["clave"] for a in s["actividades"]}
    en_partes = [c for p in partes for c in p["actividades"]]
    faltan = claves - set(en_partes)
    sobran = set(en_partes) - claves
    if faltan or sobran or len(en_partes) != len(set(en_partes)):
        raise SystemExit(f"partes no cuadra con actividades: faltan {sorted(faltan)}, sobran {sorted(sobran)}, o hay repetidas")
    return partes


def pagina(s: dict, base: Path, incrustar: bool) -> str:
    acts = s["actividades"]
    partes = partes_de(s)
    claves = {a["clave"] for a in acts}
    abiertos = sum(1 for h in s.get("hallazgos", []) if h.get("estado") == "abierto")
    cuerpo = (cabecera(s, len(acts))
              + pestanas(len(acts), len(s.get("necesito", [])), abiertos, len(s.get("pendientes", [])))
              + "<main>"
              + '<section class="panel" id="resumen" role="tabpanel">' + necesito(s.get("necesito", []), s.get("dueno", ""))
              + como_fue(s, partes) + "</section>"
              + panel_actividades(s, acts, partes, base, incrustar)
              + panel_hallazgos(s, claves) + panel_pendientes(s) + panel_salio_mal(s)
              + "</main>")
    titulo = f'Sesión {s.get("proyecto", "")} {s["fecha"]}'.replace("  ", " ")
    plantilla = PLANTILLA.read_text(encoding="utf-8")
    return plantilla.replace("{{TITULO}}", e(titulo)).replace("{{CUERPO}}", cuerpo)


# ── el .md (con las marcas que exige revisar_reporte.py) ─────────────────────

def markdown(s: dict) -> str:
    L: list[str] = []
    w = L.append
    w(f'# Sesión {s["fecha"]} · {s.get("clave_proyecto") or s.get("proyecto", "")} — {s["titulo"]}\n')
    w("## Resumen\n")
    if s.get("pr"):
        w(f'- **PR de sesión:** {s["pr"]["url"]}')
    if s.get("tiempo"):
        w(f'- **Tiempo:** {s["tiempo"]}')
    uso = s.get("uso") or {}
    w(f'- **Lo que gastó la sesión:** {uso.get("gasto", "—")}' + (f' · ventana de 5 h: {uso["cinco_horas"]}' if uso.get("cinco_horas") else ""))
    if s.get("ci"):
        w(f'- **CI:** {s["ci"]}')
    for d in s.get("datos", []):
        w(f'- **{d["dt"]}:** {d["dd"]}')
    if s.get("sin_terminar"):
        w(f'- **Sin terminar:** {s["sin_terminar"]}')
    w("\n| Actividad | Columna | En simple |\n|---|---|---|")
    for a in s["actividades"]:
        w(f'| {a["clave"]} | {a.get("columna", "")} | {a.get("resumen") or a["titulo"]} |')
    w("\n**Fechas en riesgo:**\n")
    for f in lista(s.get("fechas_en_riesgo")) or ["Ninguna."]:
        w(f"- {f}")
    w("\n**Necesito de ti:**\n")
    for i, n in enumerate(s.get("necesito", []), 1):
        ops = n.get("opciones") or RESPUESTAS[n.get("respuesta") or ("hecho" if n.get("tipo") in ("merge", "accion") else "si_no")]
        w(f'{i}. **{n["texto"]}**' + (f' — {n["por_que"]}' if n.get("por_que") else "")
          + (f' Qué haría yo: {n["que_haria"]}' if n.get("que_haria") else "")
          + f' (respuestas: {" / ".join(o["t"] for o in ops)} / Tengo dudas; id `{n["id"]}`)')
        for d in lista(n.get("detalle")):
            w(f"   - {d}")
    w(f'\n**Resultado de la sesión anterior:** {s.get("resultado_anterior") or "—"}\n')
    w("## Trabajo nuevo\n")
    if s.get("trabajo_nuevo"):
        w("| Clave | Qué | Dónde va y por qué | Fecha | De dónde salió |\n|---|---|---|---|---|")
        for n in s["trabajo_nuevo"]:
            w(f'| {n["clave"]} | {n["titulo"]} | {n.get("donde_va", "")} | {n.get("fecha", "")} | {n.get("de_donde", "")} |')
    else:
        w("No nació trabajo nuevo en esta sesión.")
    w("\n## Hallazgos\n")
    if s.get("hallazgos"):
        w("| # | Gravedad | Qué | Dónde | Estado | Solución recomendada |\n|---|---|---|---|---|---|")
        for h in s["hallazgos"]:
            w(f'| {h.get("id", "")} | {SEV_TEXTO.get(h.get("severidad", "info"), "")} | {h["titulo"]} | {h.get("donde", "")} | '
              f'{h.get("estado_texto") or h.get("estado", "")} | '
              f'{h["solucion"].get("que_cambia", "") if isinstance(h.get("solucion"), dict) else h.get("solucion", "")} |')
        for h in s["hallazgos"]:
            if h.get("estado") == "abierto":
                w(f'\n### Hallazgo {h.get("id", "")} · {h["titulo"]}\n')
                w(h.get("simple", ""))
                w("")
                for linea in solucion_md(h.get("solucion")):
                    w(linea)
    else:
        w("Ninguno en esta sesión.")
    for a in s["actividades"]:
        w(f'\n## {a["clave"]} · {a["titulo"]}\n')
        w(f'**Tiempo y consumo:** {a.get("inicio", "")} → {a.get("cierre", "")}' + (f' · {a["consumo"]}' if a.get("consumo") else "") + "\n")
        w(f'**Agentes:** {a.get("agentes") or "ninguno"}\n')
        w("### Qué se hizo\n")
        w(f'**En simple:** {a.get("simple", "")}\n')
        w("**Técnico:** " + " ".join(lista(a.get("tecnico"))) + "\n")
        if a.get("para_ti"):
            w(f'**Para ti:** {a["para_ti"]}\n')
        w("### Hallazgos\n")
        w("\n".join(f"- {x}" for x in lista(a.get("hallazgos"))) or "Ninguno.")
        w("\n### Trabajo nuevo\n")
        w("\n".join(f"- {x}" for x in lista(a.get("trabajo_nuevo"))) or "—")
        w("\n### Pruebas\n")
        pr = a.get("pruebas", [])
        pasaron = sum(1 for p in pr if p.get("resultado", "paso") == "paso")
        w(f"**1. Ejecutadas por los agentes y por mí ({pasaron} de {len(pr)} pasaron):**\n")
        for i, p in enumerate(pr, 1):
            w(f'{i}. {p["que"]} Esperado: {p.get("esperado", "")} Real: {p.get("real", "")} '
              f'— {"pasó" if p.get("resultado", "paso") == "paso" else "FALLÓ"}'
              + (f'. Antes del arreglo: {p["antes"]}' if p.get("antes") else ""))
        if a.get("capturas"):
            w("\nCapturas (en la página, con su juicio): " + "; ".join(c["juicio"] for c in a["capturas"]))
        else:
            w(f'\nSin capturas: {a.get("sin_capturas") or "no tiene pantalla"}.')
        w(f'\n**2. Para que lo veas:** {a.get("para_que_lo_veas") or "—"}\n')
        if lista(a.get("pendientes")):
            w(f'**3. Pendientes para el dueño:** {", ".join(lista(a["pendientes"]))} (abajo y en la página).\n')
        w("### Qué no se probó\n")
        w(a.get("no_probado") or "—")
    w("\n## Pendientes para el dueño\n")
    w("**Pendientes para el dueño** (resultado y comentario en la página de la sesión):\n")
    for p in s.get("pendientes", []):
        w(f'- **{p["id"]}** ({p["actividad"]}{", " + p["origen"] if p.get("origen") else ""}) · {p["titulo"]}. '
          f'Pasos: {p["pasos"]} Debe pasar: {p["debe_pasar"]} Resultado: ___')
    w("\n## Lo que salió mal\n")
    if s.get("salio_mal"):
        w("| Qué pasó | Regla que nace |\n|---|---|")
        for m in s["salio_mal"]:
            w(f'| {m["que"]} | {m["regla"]} |')
    else:
        w("Nada que anotar en esta sesión.")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sesion", nargs="?", help="sesion.json")
    ap.add_argument("--md", help="dónde escribir el .md")
    ap.add_argument("--html", help="dónde escribir la página")
    ap.add_argument("--no-incrustar", action="store_true", help="dejar las capturas como rutas (publicarlas con `files`)")
    ap.add_argument("--ejemplo", action="store_true", help="imprime un sesion.json de ejemplo")
    args = ap.parse_args()
    if args.ejemplo:
        print(json.dumps(EJEMPLO, ensure_ascii=False, indent=2))
        return 0
    if not args.sesion or not (args.md or args.html):
        ap.print_usage()
        return 2
    ruta = Path(args.sesion)
    s = json.loads(ruta.read_text(encoding="utf-8"))
    if args.html:
        out = pagina(s, ruta.parent, not args.no_incrustar)
        Path(args.html).write_text(out, encoding="utf-8")
        mb = len(out.encode()) / 1e6
        print(f"página: {args.html} ({mb:.1f} MB)")
        if mb > 15:
            print("La página pasa de 15 MB: reduce las capturas o usa --no-incrustar.", file=sys.stderr)
            return 1
    if args.md:
        Path(args.md).write_text(markdown(s), encoding="utf-8")
        print(f"md: {args.md}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
