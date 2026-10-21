#!/usr/bin/env python3
"""Tracker local del método Capitán, para proyectos sin tracker externo.

La fuente es `docs/capitan/tablero.json` (versionado en git: cada cambio queda
en el historial y viaja en el PR). Cada comando que cambia algo deja una
entrada en la bitácora de la actividad y regenera `docs/capitan/tablero.html`,
que se abre en el navegador. Nadie edita el JSON ni el HTML a mano.

Uso (desde la raíz del proyecto):
  tablero.py init "<nombre del proyecto>"
  tablero.py epica <clave> "<nombre>"                      p. ej. epica M1 "Login"
  tablero.py crear "<título>" --epica M1 [--tipo bug|mejora|historia]
        [--criterio "..."]... [--subtarea "..."]... [--depende ACT-001]...
        [--inicia AAAA-MM-DD] [--termina AAAA-MM-DD]
        [--importada --columna <columna>]     solo al migrar de otro tracker: nace en su
                                              columna, sin movimientos ni tiempos inventados
  tablero.py mover ACT-001 <columna>                        backlog|por_hacer|en_curso|revision|pruebas|por_desplegar|listo
  tablero.py comentar ACT-001 "<texto>"
  tablero.py subtarea ACT-001 <n> [--hecha|--pendiente|--titulo "..."]
  tablero.py fechas ACT-001 --inicia AAAA-MM-DD --termina AAAA-MM-DD   (solo actividades nuevas)
  tablero.py criterios ACT-001 --criterio "..."...          reemplaza los criterios (deja bitácora)
  tablero.py bloquear ACT-001 "<motivo>" | desbloquear ACT-001
  tablero.py listar [--abiertas] [--columna X]
  tablero.py ver ACT-001
  tablero.py html                                           regenera la página

Consumo: solo el de las conversaciones que trabajan en ESTE proyecto, nunca el
de toda la cuenta. La barra de estado de Claude Code escribe
`~/.claude/capitan-sesiones/<ruta-del-proyecto>.json` con el costo y la duración
de la conversación activa (exactos) y lo que subió el % semanal desde que empezó
(aproximado: incluye lo que se haga en paralelo en otra conversación). Cada
comando del tablero registra esa sesión en `tablero.json` y cada entrada de
bitácora guarda una foto, para medir lo que costó cada actividad. Sin medidor,
esos campos salen como «—».
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys

DIR = os.path.join("docs", "capitan")
JSON = os.path.join(DIR, "tablero.json")
HTML = os.path.join(DIR, "tablero.html")
COLUMNAS = ["backlog", "por_hacer", "en_curso", "revision", "pruebas", "por_desplegar", "listo"]
NOMBRES = {
    "backlog": "Backlog", "por_hacer": "Por hacer", "en_curso": "En curso", "revision": "Revisión de código",
    "pruebas": "Pruebas funcionales", "por_desplegar": "Por desplegar", "listo": "Listo",
}


def ahora() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def cargar() -> dict:
    if not os.path.exists(JSON):
        sys.exit(f"No existe {JSON}: corre primero `tablero.py init \"<nombre>\"`.")
    return json.load(open(JSON, encoding="utf-8"))


def guardar(t: dict) -> None:
    os.makedirs(DIR, exist_ok=True)
    registrar_sesion(t)
    json.dump(t, open(JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    open(HTML, "w", encoding="utf-8").write(render(t))


def actividad(t: dict, clave: str) -> dict:
    for a in t["actividades"]:
        if a["clave"] == clave:
            return a
    sys.exit(f"No existe la actividad {clave}.")


SESIONES_DIR = os.path.join(os.path.expanduser("~"), ".claude", "capitan-sesiones")
VIGENCIA_MIN = 10


def leer_sesion() -> dict | None:
    """Consumo de la conversación que trabaja en este proyecto, si el medidor es reciente."""
    clave = re.sub(r"[^a-z0-9]+", "-", os.getcwd().lower()).strip("-")
    try:
        s = json.load(open(os.path.join(SESIONES_DIR, clave + ".json"), encoding="utf-8-sig"))
        w = str(s["written_at"]).replace("Z", "+00:00")
        w = re.sub(r"(\.\d{6})\d+", lambda m: m.group(1), w)
        escrito = dt.datetime.fromisoformat(w)
        if escrito.tzinfo is None:
            escrito = escrito.replace(tzinfo=dt.timezone.utc)
    except Exception:
        return None
    if (dt.datetime.now(dt.timezone.utc) - escrito).total_seconds() / 60 > VIGENCIA_MIN or not s.get("session_id"):
        return None
    return s


def registrar_sesion(t: dict) -> None:
    """Anota (o actualiza) la conversación actual en tablero.json."""
    s = leer_sesion()
    if not s:
        return
    ses = t.setdefault("sesiones", {})
    r = ses.setdefault(s["session_id"], {"primera": ahora()})
    r.update({
        "ultima": ahora(),
        "costo_usd": s.get("cost_usd"),
        "duracion_ms": s.get("duration_ms"),
        "semana_pct": s.get("week_delta_pct"),
    })


def bitacora(a: dict, texto: str) -> None:
    entrada = {"cuando": ahora(), "que": texto}
    s = leer_sesion()
    if s:
        entrada["sesion"] = s["session_id"]
        entrada["costo_sesion"] = s.get("cost_usd")
        entrada["semana_sesion"] = s.get("week_delta_pct")
    a.setdefault("bitacora", []).append(entrada)


def cmd_init(args) -> None:
    if os.path.exists(JSON):
        sys.exit(f"{JSON} ya existe: no se sobrescribe.")
    guardar({"proyecto": args.nombre, "creado": ahora(), "epicas": [], "actividades": []})
    print(f"Tablero creado: {JSON} y {HTML}")


def cmd_epica(args) -> None:
    t = cargar()
    if any(e["clave"] == args.clave for e in t["epicas"]):
        sys.exit(f"La épica {args.clave} ya existe.")
    t["epicas"].append({"clave": args.clave, "nombre": args.nombre, "estado": "abierta"})
    guardar(t)
    print(f"Épica {args.clave} · {args.nombre}")


def cmd_crear(args) -> None:
    t = cargar()
    if args.columna not in COLUMNAS:
        sys.exit(f"Columna inválida. Opciones: {', '.join(COLUMNAS)}")
    if args.columna != "backlog" and not args.importada:
        sys.exit("Una actividad nueva nace en Backlog; --columna solo vale con --importada.")
    if args.epica and not any(e["clave"] == args.epica for e in t["epicas"]):
        sys.exit(f"La épica {args.epica} no existe: créala con `tablero.py epica`.")
    for d in args.depende or []:
        actividad(t, d)
    n = max([int(a["clave"].split("-")[1]) for a in t["actividades"]] + [0]) + 1
    a = {
        "clave": f"ACT-{n:03d}", "titulo": args.titulo, "epica": args.epica, "tipo": args.tipo,
        "columna": args.columna, "criterios": args.criterio or [],
        "subtareas": [{"titulo": s, "hecha": False} for s in (args.subtarea or [])],
        "depende_de": args.depende or [], "inicia": args.inicia, "termina": args.termina,
        "bloqueada": None, "comentarios": [], "bitacora": [],
    }
    if args.importada:
        a["importada"] = True
        bitacora(a, f"importada en {NOMBRES[args.columna]} desde el tracker anterior")
    else:
        bitacora(a, "creada en Backlog")
    t["actividades"].append(a)
    guardar(t)
    print(f"{a['clave']} · {a['titulo']}")


def cmd_mover(args) -> None:
    t = cargar()
    a = actividad(t, args.clave)
    if args.columna not in COLUMNAS:
        sys.exit(f"Columna inválida. Opciones: {', '.join(COLUMNAS)}")
    de, a_ = COLUMNAS.index(a["columna"]), COLUMNAS.index(args.columna)
    if abs(a_ - de) != 1:
        sys.exit(f"Solo se mueve a la columna contigua ({NOMBRES[a['columna']]} → ?). Un retroceso cuenta como retrabajo.")
    if a.get("bloqueada") and a_ > de:
        sys.exit(f"{a['clave']} está bloqueada: {a['bloqueada']}")
    texto = f"{NOMBRES[a['columna']]} → {NOMBRES[args.columna]}" + (" (retrabajo)" if a_ < de else "")
    a["columna"] = args.columna
    bitacora(a, texto)
    guardar(t)
    print(f"{a['clave']} · {texto}")


def cmd_comentar(args) -> None:
    t = cargar()
    a = actividad(t, args.clave)
    a["comentarios"].append({"cuando": ahora(), "texto": args.texto})
    bitacora(a, "comentario")
    guardar(t)
    print(f"Comentario en {a['clave']}")


def cmd_sesion(args) -> None:
    """Liga una sesión con su reporte: la página (Artifact) y el .md en docs/capitan/sesiones/."""
    url = (args.reporte or "").strip()
    if not url.startswith("https://"):
        sys.exit("El enlace del reporte debe empezar con https://")
    t = cargar()
    ses = t.setdefault("sesiones", {})
    sid = args.id
    if not sid:
        s = leer_sesion()
        if not s:
            sys.exit("No hay medidor de la sesión actual; pasa --id <session_id>")
        registrar_sesion(t)
        sid = s["session_id"]
    coincide = [k for k in ses if k == sid or k.startswith(sid)]
    if len(coincide) != 1:
        sys.exit(f"No encuentro una sola sesión que empiece con {sid!r}")
    r = ses[coincide[0]]
    r["reporte_url"] = url
    if args.archivo:
        r["reporte_archivo"] = args.archivo
    guardar(t)
    print(f"Sesión {coincide[0][:8]} ligada a su reporte")


def cmd_subtarea(args) -> None:
    t = cargar()
    a = actividad(t, args.clave)
    if not 1 <= args.n <= len(a["subtareas"]):
        sys.exit(f"{a['clave']} tiene {len(a['subtareas'])} subtareas.")
    s = a["subtareas"][args.n - 1]
    if args.titulo:
        bitacora(a, f"subtarea {args.n} renombrada: «{s['titulo']}» → «{args.titulo}»")
        s["titulo"] = args.titulo
    if args.hecha or args.pendiente:
        s["hecha"] = bool(args.hecha)
        bitacora(a, f"subtarea {args.n} {'hecha' if s['hecha'] else 'pendiente'}: {s['titulo']}")
    guardar(t)
    print(f"{a['clave']} · {sum(x['hecha'] for x in a['subtareas'])}/{len(a['subtareas'])} subtareas")


def cmd_fechas(args) -> None:
    t = cargar()
    a = actividad(t, args.clave)
    if (a.get("inicia") or a.get("termina")) and not args.forzar:
        sys.exit(f"{a['clave']} ya tiene fechas: las fechas existentes no se mueven (usa --forzar solo con OK del dueño).")
    bitacora(a, f"fechas: {a.get('inicia')}→{a.get('termina')} ⇒ {args.inicia}→{args.termina}")
    a["inicia"], a["termina"] = args.inicia, args.termina
    guardar(t)
    print(f"{a['clave']} · {args.inicia} → {args.termina}")


def cmd_criterios(args) -> None:
    t = cargar()
    a = actividad(t, args.clave)
    bitacora(a, "criterios reemplazados (antes: " + " | ".join(a["criterios"]) + ")")
    a["criterios"] = args.criterio
    guardar(t)
    print(f"{a['clave']} · {len(args.criterio)} criterios")


def cmd_bloquear(args) -> None:
    t = cargar()
    a = actividad(t, args.clave)
    a["bloqueada"] = args.motivo
    bitacora(a, f"bloqueada: {args.motivo}")
    guardar(t)
    print(f"{a['clave']} bloqueada")


def cmd_desbloquear(args) -> None:
    t = cargar()
    a = actividad(t, args.clave)
    a["bloqueada"] = None
    bitacora(a, "desbloqueada")
    guardar(t)
    print(f"{a['clave']} desbloqueada")


def vencida(a: dict) -> bool:
    return bool(a.get("termina")) and a["columna"] != "listo" and a["termina"] < dt.date.today().isoformat()


def _fecha(s: str) -> dt.datetime | None:
    try:
        return dt.datetime.strptime(s, "%Y-%m-%d %H:%M")
    except Exception:
        return None


def duracion(minutos: float | None) -> str:
    """«—» sin dato o con menos de un minuto (p. ej. movimientos en lote al migrar)."""
    if minutos is None or minutos < 1:
        return "—"
    if minutos < 60:
        return f"{minutos:.0f} min"
    if minutos < 60 * 24:
        return f"{minutos / 60:.1f} h"
    return f"{minutos / 1440:.1f} d"


def _incrementos(valores: list) -> float:
    """Suma de subidas entre fotos consecutivas; si baja (la sesión reinició su base), cuenta desde cero."""
    total, previo = 0.0, None
    for v in valores:
        if v is None:
            continue
        if previo is not None:
            total += v - previo if v >= previo else v
        previo = v
    return total


def consumo_ventana(bit: list, ini: dict | None, fin: dict | None, abierta: bool):
    """Costo (USD) y % semanal de las sesiones mientras la actividad estuvo en curso."""
    if not ini:
        return None, None
    i0 = bit.index(ini)
    i1 = bit.index(fin) + 1 if fin else len(bit)
    fotos = [x for x in bit[i0:i1] if x.get("sesion")]
    vivo = leer_sesion() if abierta else None
    if vivo:
        fotos.append({"sesion": vivo["session_id"], "costo_sesion": vivo.get("cost_usd"), "semana_sesion": vivo.get("week_delta_pct")})
    if len(fotos) < 2:
        return None, None
    costo = semana = 0.0
    for sid in dict.fromkeys(x["sesion"] for x in fotos):
        de_esa = [x for x in fotos if x["sesion"] == sid]
        costo += _incrementos([x.get("costo_sesion") for x in de_esa])
        semana += _incrementos([x.get("semana_sesion") for x in de_esa])
    return costo, semana


def ventanas(bit: list) -> list:
    """Las ventanas de consumo: de cada «→ En curso» a la siguiente «→ Revisión de código» (o «→ Listo» si el flujo no
    pasa por Revisión). La última puede seguir abierta (fin None)."""
    lista, abierta = [], None
    for x in bit:
        # Solo movimientos («Origen → Destino», con «(retrabajo)» si retrocede); no un texto con flechas adentro.
        mov = re.fullmatch(r"[^→]+ → ([^→(]+?)(?: \(retrabajo\))?", x["que"])
        destino = mov.group(1) if mov else None
        if destino == "En curso" and abierta is None:
            abierta = x
        elif abierta is not None and destino in ("Revisión de código", "Listo"):
            lista.append((abierta, x)); abierta = None
    if abierta is not None:
        lista.append((abierta, None))
    return lista


def en_paralelo(m: dict, clave: str) -> bool:
    """Alguna ventana de esta actividad se cruza con la de otra (estricto: el relevo en el mismo minuto no cuenta)."""
    ahora = dt.datetime.now()
    for i, f in m[clave]["ventanas"]:
        for otra, mo in m.items():
            if otra == clave:
                continue
            for oi, of in mo["ventanas"]:
                if i < (of or ahora) and oi < (f or ahora):
                    return True
    return False


def metricas(a: dict) -> dict:
    """Fechas, tiempos y consumo calculados de la bitácora; nada se guarda aparte."""
    bit = a.get("bitacora", [])
    creada = _fecha(bit[0]["cuando"]) if bit else None
    movs = [x for x in bit if "→" in x["que"]]
    ultimo = _fecha(movs[-1]["cuando"]) if movs else creada
    ini = next((x for x in bit if x["que"].endswith("→ En curso")), None)
    fin = next((x for x in reversed(bit) if x["que"].endswith("→ Listo")), None) if a["columna"] == "listo" else None
    t_ini = _fecha(ini["cuando"]) if ini else None
    t_fin = _fecha(fin["cuando"]) if fin else None
    ya = dt.datetime.now()
    # Consumo: lo que marcó el medidor entre que la actividad entra a
    # En curso y que pasa a Revisión de código, aunque otra corra en paralelo; el retrabajo abre otra ventana y se suman.
    costo = semana = None
    for v_ini, v_fin in ventanas(bit):
        c, s = consumo_ventana(bit, v_ini, v_fin, v_fin is None and a["columna"] != "listo")
        if c is not None:
            costo = (costo or 0.0) + c
        if s is not None:
            semana = (semana or 0.0) + s
    return {
        "creada": creada.strftime("%Y-%m-%d") if creada else "",
        "ultimo": ultimo.strftime("%Y-%m-%d %H:%M") if ultimo else "",
        # importada y sin movimientos reales: no hay dato de cuánto lleva en su columna
        "en_col_min": None if (a.get("importada") and not movs) else ((ya - ultimo).total_seconds() / 60 if ultimo else None),
        "ejec_min": ((t_fin or ya) - t_ini).total_seconds() / 60 if t_ini else None,
        "total_min": (t_fin - creada).total_seconds() / 60 if (t_fin and creada) else None,
        "inicio": t_ini.strftime("%Y-%m-%d %H:%M") if t_ini else "",
        "fin": t_fin.strftime("%Y-%m-%d %H:%M") if t_fin else "",
        "costo": costo, "semana": semana,
        "ventanas": [(_fecha(i["cuando"]), _fecha(f["cuando"]) if f else None) for i, f in ventanas(bit)],
        "retrabajos": sum("(retrabajo)" in x["que"] for x in bit),
    }


def cmd_listar(args) -> None:
    t = cargar()
    for a in t["actividades"]:
        if args.abiertas and a["columna"] == "listo":
            continue
        if args.columna and a["columna"] != args.columna:
            continue
        extra = []
        if a.get("termina"):
            extra.append(f"vence {a['termina']}" + (" ⚠ vencida" if vencida(a) else ""))
        if a.get("bloqueada"):
            extra.append(f"BLOQUEADA: {a['bloqueada']}")
        pend = [d for d in a["depende_de"] if actividad(t, d)["columna"] != "listo"]
        if pend:
            extra.append("espera a " + ", ".join(pend))
        print(f"{a['clave']} · {a.get('epica') or '—'} · {a['titulo']} · {NOMBRES[a['columna']]}" + (" · " + " · ".join(extra) if extra else ""))


def cmd_ver(args) -> None:
    a = actividad(cargar(), args.clave)
    print(json.dumps(a, ensure_ascii=False, indent=2))


def cmd_html(args) -> None:
    t = cargar()
    guardar(t)
    print(f"Regenerado {HTML}")
    if args.fragmento:
        open(args.fragmento, "w", encoding="utf-8", newline="\n").write(fragmento(render(t)))
        print(f"Versión para publicar como Artifact: {args.fragmento}")


def fragmento(doc: str) -> str:
    """El documento sin doctype/html/head/body, como lo pide el Artifact (que pone su propio esqueleto)."""
    cabeza = re.search(r"<head>(.*?)</head>", doc, re.S)
    cuerpo = re.search(r"<body[^>]*>(.*)</body>", doc, re.S)
    if not cabeza or not cuerpo:
        sys.exit("No reconozco la estructura de tablero.html")
    head = re.sub(r"<meta (charset|name='viewport')[^>]*>", "", cabeza.group(1))
    return head + cuerpo.group(1)


ESTADO_TONO = {  # el color señala estado, no adorna (admin-kit)
    "backlog": "neutro", "por_hacer": "neutro", "en_curso": "info", "revision": "info",
    "pruebas": "info", "por_desplegar": "warn", "listo": "success",
}


def _usd(x) -> str:
    return "—" if x is None else f"${x:,.2f}"


def _pct(x) -> str:
    return "—" if x is None else f"{x:.1f}%"


def render(t: dict) -> str:
    e = lambda s: html.escape(str(s if s is not None else ""))
    epicas = {x["clave"]: x["nombre"] for x in t["epicas"]}
    acts = t["actividades"]
    m = {a["clave"]: metricas(a) for a in acts}
    sesiones = t.get("sesiones", {})

    def consumo_txt(k: str) -> str:
        mk = m[k]
        if mk["costo"] is None and mk["semana"] is None:
            return "—"
        # En paralelo: su consumo incluye el de la otra; no se suman como si fueran separados.
        return f"{_pct(mk['semana'])} · {_usd(mk['costo'])}" + (" · en paralelo" if en_paralelo(m, k) else "")

    def depende_txt(a: dict) -> str:
        partes = []
        for d in a["depende_de"]:
            otra = next((x for x in acts if x["clave"] == d), {})
            partes.append(d + ("" if otra.get("columna") == "listo" else " (pendiente)"))
        return ", ".join(partes)

    def num_v(x) -> str:
        return f"{x:.0f}" if x is not None and x >= 1 else "-1"

    def pill(columna: str, extra: str = "") -> str:
        return f"<span class='pill {ESTADO_TONO[columna]}'>{e(NOMBRES[columna])}{e(extra)}</span>"

    # --- KPIs ---
    n = len(acts)
    listas = sum(a["columna"] == "listo" for a in acts)
    pct = round(100 * listas / n) if n else 0
    abiertas = [a for a in acts if a["columna"] != "listo"]
    bloqueadas = sum(bool(a.get("bloqueada")) for a in acts)
    vencidas = sum(vencida(a) for a in acts)
    costo_total = sum((s.get("costo_usd") or 0) for s in sesiones.values())
    semana_total = sum((s.get("semana_pct") or 0) for s in sesiones.values())
    horas = sum((s.get("duracion_ms") or 0) for s in sesiones.values()) / 3_600_000
    kpis = (
        f"<article class='kpi'><span class='lbl'>Avance</span><b class='num'>{pct}%</b>"
        f"<i class='barra'><i style='width:{pct}%'></i></i>"
        f"<small>{listas} de {n} actividades en Listo</small></article>"
        f"<article class='kpi'><span class='lbl'>Abiertas</span><b class='num'>{len(abiertas)}</b>"
        f"<small>{sum(a['columna'] == 'en_curso' for a in acts)} en curso · "
        f"<span class='{ 'txt-danger' if bloqueadas else ''}'>{bloqueadas} bloqueadas</span> · "
        f"<span class='{ 'txt-danger' if vencidas else ''}'>{vencidas} vencidas</span></small></article>"
        f"<article class='kpi'><span class='lbl'>Consumo de las sesiones de trabajo</span>"
        f"<b class='num'>{_pct(semana_total) if sesiones else '—'}</b>"
        f"<small>{len(sesiones)} {'sesión' if len(sesiones) == 1 else 'sesiones'} · {_usd(costo_total) if sesiones else '—'} · "
        f"{horas:.1f} h · % semanal aproximado, costo exacto</small></article>"
    )

    # --- vista tablero ---
    cols = []
    for c in COLUMNAS:
        tarjetas = []
        for a in [a for a in acts if a["columna"] == c]:
            k, mk = a["clave"], m[a["clave"]]
            hechas = sum(s["hecha"] for s in a["subtareas"])
            marcas = ""
            if vencida(a):
                marcas += "<span class='pill danger'>vencida</span>"
            if a.get("bloqueada"):
                marcas += "<span class='pill danger'>bloqueada</span>"
            if mk["retrabajos"]:
                marcas += f"<span class='pill warn'>retrabajo ×{mk['retrabajos']}</span>"
            if a.get("importada"):
                marcas += "<span class='pill neutro'>importada</span>"
            campos = (
                "<dl class='campos'>"
                f"<dt>Creada</dt><dd>{e(mk['creada'] or '—')}</dd>"
                f"<dt>Plan</dt><dd>{e(a.get('inicia') or '—')} → {e(a.get('termina') or '—')}</dd>"
                f"<dt>Inició</dt><dd>{e(mk['inicio'] or '—')}</dd>"
                f"<dt>Terminó</dt><dd>{e(mk['fin'] or '—')}</dd>"
                f"<dt>Ejecución</dt><dd class='num'>{e(duracion(mk['ejec_min']))}</dd>"
                f"<dt>En esta columna</dt><dd class='num'>{e(duracion(mk['en_col_min']))}</dd>"
                f"<dt>Consumo</dt><dd class='num'>{e(consumo_txt(k))}</dd>"
                "</dl>"
            )
            secc = []
            if a["criterios"]:
                secc.append("<h4>Criterios</h4><ul>" + "".join(f"<li>{e(x)}</li>" for x in a["criterios"]) + "</ul>")
            if a["subtareas"]:
                secc.append("<h4>Subtareas</h4><ul class='sub'>" + "".join(
                    f"<li><span class='check {'si' if s['hecha'] else ''}'></span>{e(s['titulo'])}</li>" for s in a["subtareas"]) + "</ul>")
            if a.get("bloqueada"):
                secc.append(f"<p class='aviso danger'><b>Bloqueo:</b> {e(a['bloqueada'])}</p>")
            if a["depende_de"]:
                secc.append(f"<p><b>Depende de:</b> {e(depende_txt(a))}</p>")
            if a["comentarios"]:
                secc.append("<h4>Comentarios</h4>" + "".join(
                    f"<p class='com'><time>{e(x['cuando'])}</time>{e(x['texto'])}</p>" for x in a["comentarios"]))
            renglones = []
            for x in a["bitacora"]:
                r = f"<time>{e(x['cuando'])}</time>{e(x['que'])}"
                if x.get("costo_sesion") is not None:
                    r += f" <span class='tenue'>· sesión {e(_usd(x['costo_sesion']))}</span>"
                renglones.append(f"<li>{r}</li>")
            secc.append("<h4>Bitácora</h4><ul class='bit'>" + "".join(renglones) + "</ul>")
            meta = [f"<span>{e(a.get('epica') or '—')}</span>", f"<span>{e(a.get('tipo'))}</span>"]
            if a.get("termina"):
                meta.append(f"<span>vence {e(a['termina'])}</span>")
            if mk["ejec_min"] is not None and mk["ejec_min"] >= 1:
                meta.append(f"<span class='num'>⏱ {e(duracion(mk['ejec_min']))}</span>")
            if mk["costo"] is not None:
                meta.append(f"<span class='num'>{e(_usd(mk['costo']))}</span>")
            progreso = ""
            if a["subtareas"]:
                p = round(100 * hechas / len(a["subtareas"]))
                progreso = (f"<div class='prog'><i class='barra'><i style='width:{p}%'></i></i>"
                            f"<span class='num'>{hechas}/{len(a['subtareas'])}</span></div>")
            tarjetas.append(
                f"<details class='tarjeta'><summary><div class='t-top'><span class='clave'>{e(k)}</span>{marcas}</div>"
                f"<div class='t-tit'>{e(a['titulo'])}</div>{progreso}<div class='meta'>{''.join(meta)}</div></summary>"
                f"<div class='t-det'>{campos}{''.join(secc)}</div></details>"
            )
        vacio = "<p class='vacio'>Sin actividades</p>"
        cols.append(
            f"<section class='col'><header><span class='dot {ESTADO_TONO[c]}'></span><h2>{NOMBRES[c]}</h2>"
            f"<span class='cuenta num'>{len(tarjetas)}</span></header>"
            f"<div class='col-cuerpo'>{''.join(tarjetas) or vacio}</div></section>"
        )

    # --- vista lista ---
    filas = []
    for a in acts:
        k, mk = a["clave"], m[a["clave"]]
        hechas = sum(s["hecha"] for s in a["subtareas"])
        extra = (" · bloqueada" if a.get("bloqueada") else "") + (" · vencida" if vencida(a) else "")
        celdas = [
            (f"{int(k.split('-')[1]):05d}", e(k), "mono"),
            (e(a["titulo"].lower()), e(a["titulo"]), "tit"),
            (e(a.get("epica") or ""), e(a.get("epica") or "—"), ""),
            (e(a.get("tipo")), e(a.get("tipo")), ""),
            (str(COLUMNAS.index(a["columna"])), pill(a["columna"], extra), ""),
            (e(mk["creada"]), e(mk["creada"] or "—"), "num"),
            (e(a.get("inicia") or ""), e(a.get("inicia") or "—"), "num"),
            (e(a.get("termina") or ""), e(a.get("termina") or "—"), "num"),
            (e(mk["inicio"]), e(mk["inicio"] or "—"), "num"),
            (e(mk["fin"]), e(mk["fin"] or "—"), "num"),
            (num_v(mk["ejec_min"]), e(duracion(mk["ejec_min"])), "num der"),
            (num_v(mk["en_col_min"]), e(duracion(mk["en_col_min"])), "num der"),
            (f"{mk['semana']:.2f}" if mk["semana"] is not None else "-1", e(_pct(mk["semana"])), "num der"),
            (f"{mk['costo']:.2f}" if mk["costo"] is not None else "-1", e(_usd(mk["costo"])), "num der"),
            (str(hechas), f"{hechas}/{len(a['subtareas'])}", "num der"),
            (e(depende_txt(a)), e(depende_txt(a) or "—"), ""),
            (e(mk["ultimo"]), e(mk["ultimo"] or "—"), "num"),
        ]
        tds = "".join(f"<td data-v='{v}' class='{cl}'>{x}</td>" for v, x, cl in celdas)
        filas.append(f"<tr data-col='{e(a['columna'])}' data-epica='{e(a.get('epica') or '')}'>{tds}</tr>")
    cabeceras = ["Clave", "Actividad", "Épica", "Tipo", "Estado", "Creada", "Inicio plan", "Fin plan", "Inició",
                 "Terminó", "Ejecución", "En columna", "% semana", "Costo", "Subtareas", "Depende de", "Último movimiento"]
    opciones_col = "".join(f"<option value='{c}'>{NOMBRES[c]}</option>" for c in COLUMNAS)
    opciones_ep = "".join(f"<option value='{e(x['clave'])}'>{e(x['clave'])} · {e(x['nombre'])}</option>" for x in t["epicas"])
    lista = (
        "<div class='filtros'><input id='q' type='search' placeholder='Buscar actividad o clave' aria-label='Buscar'>"
        f"<select id='fcol' aria-label='Columna'><option value=''>Todas las columnas</option><option value='abiertas'>Abiertas</option>{opciones_col}</select>"
        f"<select id='fep' aria-label='Épica'><option value=''>Todas las épicas</option>{opciones_ep}</select>"
        "<span id='cuenta' class='num'></span></div>"
        "<div class='card tabla'><table id='tabla-lista'><thead><tr>"
        + "".join(f"<th data-i='{i}' scope='col'>{h}</th>" for i, h in enumerate(cabeceras))
        + "</tr></thead><tbody>" + "".join(filas) + "</tbody></table></div>"
    )

    # --- vista sesiones ---
    # actividades trabajadas en cada sesión: se derivan de la bitácora (cada entrada anota su sesión)
    por_sesion: dict = {}
    for a in acts:
        for x in a["bitacora"]:
            if x.get("sesion"):
                por_sesion.setdefault(x["sesion"], {}).setdefault(a["clave"], []).append(x)

    def resumen(entradas: list) -> str:
        movs = [x["que"].split("→")[-1].strip() for x in entradas if "→" in x["que"]]
        partes = []
        if any(x["que"].startswith(("creada", "importada")) for x in entradas):
            partes.append("creada")
        if movs:
            partes.append("movida a " + movs[-1].replace(" (retrabajo)", "") + (" (retrabajo)" if any("retrabajo" in x["que"] for x in entradas) else ""))
        n_com = sum(x["que"] == "comentario" for x in entradas)
        if n_com:
            partes.append(f"{n_com} comentario{'s' if n_com > 1 else ''}")
        otras = [x["que"] for x in entradas if "→" not in x["que"] and x["que"] != "comentario"
                 and not x["que"].startswith(("creada", "importada"))]
        partes += otras[-2:]
        return " · ".join(partes) or f"{len(entradas)} cambios"

    fila_ses = []
    for sid, s in sorted(sesiones.items(), key=lambda kv: kv[1].get("primera", ""), reverse=True):
        dur = (s.get("duracion_ms") or 0) / 60000
        tocadas = por_sesion.get(sid, {})
        items = []
        for clave, entradas in sorted(tocadas.items(), key=lambda kv: kv[1][0]["cuando"]):
            a = next(x for x in acts if x["clave"] == clave)
            costo = _incrementos([x.get("costo_sesion") for x in entradas]) if len(entradas) > 1 else None
            items.append(
                f"<li><span class='clave'>{e(clave)}</span><span class='ses-tit'>{e(a['titulo'])}</span>"
                f"{pill(a['columna'])}<span class='ses-res'>{e(resumen(entradas))}"
                f"{(' · ' + e(_usd(costo))) if costo else ''}</span></li>"
            )
        lista_act = (f"<ul class='ses-acts'>{''.join(items)}</ul>" if items
                     else "<span class='tenue'>Sin cambios en el tablero durante esta sesión</span>")
        url_rep = s.get("reporte_url") or ""
        if url_rep.startswith("https://"):
            reporte = (f"<a class='ses-rep' href='{e(url_rep)}' target='_blank' rel='noopener noreferrer'>"
                       f"Reporte de la sesión ↗</a>")
            if s.get("reporte_archivo"):
                reporte += f"<span class='mono tenue'>{e(s['reporte_archivo'])}</span>"
        else:
            reporte = "<span class='tenue'>Sin reporte ligado</span>"
        fila_ses.append(
            f"<article class='card ses'><header><span class='mono'>{e(sid[:8])}</span>"
            f"<span class='num'>{e(s.get('primera'))} → {e(s.get('ultima'))}</span>"
            f"<span class='ses-kpis num'><b>{e(duracion(dur))}</b><b>{e(_pct(s.get('semana_pct')))}</b>"
            f"<b>{e(_usd(s.get('costo_usd')))}</b><b>{len(tocadas)} actividad{'es' if len(tocadas) != 1 else ''}</b></span>"
            f"</header><p class='ses-reporte'>{reporte}</p>{lista_act}</article>"
        )
    vista_ses = (
        "<p class='nota'>Solo las conversaciones que trabajaron en este proyecto, con las actividades que tocaron. "
        "El costo es exacto (equivalente en API, del propio Claude Code); el % semanal es lo que subió tu uso mientras "
        "duró la conversación e incluye lo que hayas hecho en paralelo en otra. El costo por actividad es el que corrió "
        "entre su primer y su último cambio dentro de la sesión.</p>"
        + ("".join(fila_ses) or "<p class='vacio'>Aún no hay sesiones registradas.</p>")
    )

    return (
        "<!doctype html><html lang='es' data-tema='esmeralda' data-modo='claro'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Tablero · {e(t['proyecto'])}</title>"
        "<link rel='preconnect' href='https://fonts.googleapis.com'><link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>"
        "<link href='https://fonts.googleapis.com/css2?family=Lexend:wght@400;500;600&family=Plus+Jakarta+Sans:wght@600;700&display=swap' rel='stylesheet'>"
        f"<script>{JS_TEMA}</script><style>{CSS_TABLERO}</style></head><body>"
        "<header class='top'><div><h1>" + e(t["proyecto"]) + "</h1>"
        f"<p class='sub-h'>Tablero del método Capitán · generado {ahora()}</p></div>"
        "<div class='controles'>"
        "<label class='ctl'><span>Tema</span><select id='tema'><option value='esmeralda'>Esmeralda</option>"
        "<option value='indigo'>Índigo</option><option value='naranja'>Naranja</option></select></label>"
        "<div class='seg' role='group' aria-label='Modo'><button data-modo='sistema'>Sistema</button>"
        "<button data-modo='claro'>Claro</button><button data-modo='oscuro'>Oscuro</button></div></div></header>"
        f"<section class='kpis'>{kpis}</section>"
        "<nav class='tabs' role='tablist'><button role='tab' data-v='tablero' aria-selected='true'>Tablero</button>"
        "<button role='tab' data-v='lista' aria-selected='false'>Lista</button>"
        f"<button role='tab' data-v='sesiones' aria-selected='false'>Sesiones <span class='num'>{len(sesiones)}</span></button></nav>"
        f"<main><div class='vista' id='v-tablero'><div class='tablero'>{''.join(cols)}</div></div>"
        f"<div class='vista' id='v-lista' hidden>{lista}</div>"
        f"<div class='vista' id='v-sesiones' hidden>{vista_ses}</div></main>"
        f"<script>{JS_TABLERO}</script></body></html>"
    )


# Temas tomados de las semillas de admin-kit (Esmeralda, Índigo corporativo, Naranja cálido).
_TEMAS = {
    "esmeralda": {
        "claro": dict(canvas="#F3F5F7", card="#FFFFFF", well="#F7F9FA", control="#EEF1F3", line="#E8ECEF", line_2="#858B90",
                      ink="#16181C", ink_2="#5A626B", ink_3="#697079", brand="#00BF63", brand_deep="#007C40",
                      brand_soft="#E6F9F0", on_brand="#06130C"),
        "oscuro": dict(canvas="#0D0F11", card="#17191D", well="#1F2226", control="#262A2F", line="#24272C", line_2="#6B6F75",
                       ink="#F2F4F6", ink_2="#A8AFB7", ink_3="#8A9199", brand="#00BF63", brand_deep="#2BD584",
                       brand_soft="#0B2C1D", on_brand="#06130C"),
        "forma": dict(r_ctl="10px", r_card="16px", display='"Plus Jakarta Sans", system-ui, sans-serif',
                      body='"Lexend", system-ui, sans-serif'),
    },
    "indigo": {
        "claro": dict(canvas="#F5F6FA", card="#FFFFFF", well="#F0F2F8", control="#D2D8E5", line="#E4E7F0", line_2="#828897",
                      ink="#14161F", ink_2="#565E75", ink_3="#676E80", brand="#4F46E5", brand_deep="#4338CA",
                      brand_soft="#EEF0FE", on_brand="#FFFFFF"),
        "oscuro": dict(canvas="#0B0D14", card="#14161F", well="#1C1F2B", control="#32394B", line="#232735", line_2="#666D80",
                       ink="#F1F3F8", ink_2="#A7AEC1", ink_3="#9098AB", brand="#818CF8", brand_deep="#A5B4FC",
                       brand_soft="#1E1B4B", on_brand="#14161F"),
        "forma": dict(r_ctl="6px", r_card="10px", display='system-ui, -apple-system, "Segoe UI", sans-serif',
                      body='system-ui, -apple-system, "Segoe UI", sans-serif'),
    },
    "naranja": {
        "claro": dict(canvas="#FAF7F4", card="#FFFFFF", well="#F6F1EC", control="#EEE8E1", line="#EDE5DD", line_2="#91867B",
                      ink="#1C1815", ink_2="#5E564F", ink_3="#69615A", brand="#F97316", brand_deep="#B4460A",
                      brand_soft="#FFF1E6", on_brand="#2A1000"),
        "oscuro": dict(canvas="#12100E", card="#1B1815", well="#241F1B", control="#3C362E", line="#2C2823", line_2="#736D65",
                       ink="#F5F1EC", ink_2="#B0A79E", ink_3="#968D85", brand="#FB923C", brand_deep="#FDBA74",
                       brand_soft="#3A1D08", on_brand="#2A1000"),
        "forma": dict(r_ctl="14px", r_card="22px", display='Georgia, "Times New Roman", serif',
                      body='system-ui, -apple-system, "Segoe UI", sans-serif'),
    },
}
_SEMANTICOS = {
    "claro": dict(success="#007C40", success_soft="#E6F9F0", danger="#B42318", danger_soft="#FDF0F1",
                  warn="#7A5A00", warn_soft="#FFF6DE", info="#00688A", info_soft="#E9F7FC",
                  sh_card="0 1px 2px rgba(16,24,40,.04), 0 2px 8px rgba(16,24,40,.06)", card_border="transparent"),
    "oscuro": dict(success="#2BD584", success_soft="#0B2C1D", danger="#F87171", danger_soft="#2B1416",
                   warn="#FFBC00", warn_soft="#271F0A", info="#00C3FF", info_soft="#092028",
                   sh_card="none", card_border="var(--line)"),
}


def _vars_tema() -> str:
    bloques = []
    for nombre, tema in _TEMAS.items():
        for modo in ("claro", "oscuro"):
            v = {**tema[modo], **_SEMANTICOS[modo], **tema["forma"]}
            decl = ";".join(f"--{k.replace('_', '-')}:{val}" for k, val in v.items())
            bloques.append(f"html[data-tema='{nombre}'][data-modo='{modo}']{{{decl};color-scheme:{'light' if modo == 'claro' else 'dark'}}}")
    return "\n".join(bloques)


JS_TEMA = """
(function(){var d=document.documentElement,t='esmeralda',m='sistema';
try{t=localStorage.getItem('capitan-tema')||t;m=localStorage.getItem('capitan-modo')||m}catch(e){}
var o=m==='sistema'?(matchMedia('(prefers-color-scheme: dark)').matches?'oscuro':'claro'):m;
d.setAttribute('data-tema',t);d.setAttribute('data-modo',o);d.setAttribute('data-pref',m);})();
"""

CSS_TABLERO = _vars_tema() + """
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--canvas);color:var(--ink);font-family:var(--body);font-size:14px;line-height:1.5;padding:20px 16px 40px;
  max-width:1680px;margin:0 auto}
h1,h2,.kpi b,th{font-family:var(--display)}
h1{font-size:21px;line-height:1.3;margin:0;font-weight:700}
.sub-h{margin:2px 0 0;color:var(--ink-2);font-size:12.5px}
.num{font-variant-numeric:tabular-nums}
.mono,.clave{font-family:ui-monospace,"SF Mono",Menlo,Consolas,monospace;font-size:11.5px;color:var(--ink-3)}
.top{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;justify-content:space-between;margin-bottom:20px}
.controles{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.ctl{display:flex;gap:8px;align-items:center;font-size:12.5px;color:var(--ink-2)}
select,input{font:inherit;font-size:14px;height:34px;padding:0 12px;border-radius:var(--r-ctl);border:1px solid var(--line-2);
  background:var(--card);color:var(--ink);max-width:100%}
input::placeholder{color:var(--ink-3)}
:focus-visible{outline:2px solid var(--brand-deep);outline-offset:2px}
.seg{display:inline-flex;padding:3px;gap:2px;background:var(--control);border-radius:var(--r-ctl)}
.seg button{font:inherit;font-size:12.5px;border:0;background:transparent;color:var(--ink-2);padding:5px 12px;
  border-radius:calc(var(--r-ctl) - 3px);cursor:pointer;transition:background .14s,color .14s}
.seg button[aria-pressed=true]{background:var(--card);color:var(--ink);box-shadow:0 1px 2px rgba(0,0,0,.12)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;margin-bottom:20px}
.card,.kpi,.col,.tarjeta{background:var(--card);border:1px solid var(--card-border);box-shadow:var(--sh-card)}
.kpi{border-radius:var(--r-card);padding:16px 20px}
.kpi .lbl{display:block;font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;font-weight:600;color:var(--ink-3)}
.kpi b{display:block;font-size:29px;line-height:1.15;margin:6px 0 4px;font-weight:700}
.kpi small{display:block;font-size:12.5px;color:var(--ink-2)}
.txt-danger{color:var(--danger);font-weight:500}
.barra{display:block;height:6px;background:var(--well);border-radius:999px;overflow:hidden;margin:8px 0}
.barra>i{display:block;height:100%;background:var(--brand);border-radius:999px}
.tabs{display:flex;gap:4px;border-bottom:1px solid var(--line);margin-bottom:16px}
.tabs button{font:inherit;font-weight:500;border:0;background:none;color:var(--ink-2);padding:10px 14px;cursor:pointer;
  border-bottom:2px solid transparent;margin-bottom:-1px;transition:color .14s,border-color .14s}
.tabs button[aria-selected=true]{color:var(--ink);border-bottom-color:var(--brand)}
.tabs button span{font-size:11.5px;background:var(--control);color:var(--ink-2);border-radius:999px;padding:1px 7px;margin-left:4px}
.vista[hidden]{display:none}
.tablero{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(260px,1fr);gap:12px;overflow-x:auto;padding-bottom:12px;align-items:start}
.col{background:var(--well);border:1px solid var(--line);box-shadow:none;border-radius:var(--r-card);padding:10px}
.col header{display:flex;align-items:center;gap:8px;padding:4px 6px 10px}
.col h2{font-size:14px;margin:0;font-weight:600;flex:1}
.cuenta{font-size:11.5px;color:var(--ink-2);background:var(--card);border:1px solid var(--line);border-radius:999px;padding:0 8px}
.dot{width:8px;height:8px;border-radius:999px;background:var(--line-2)}
.dot.info{background:var(--info)}.dot.warn{background:var(--warn)}.dot.success{background:var(--success)}
.col-cuerpo{display:flex;flex-direction:column;gap:8px}
.tarjeta{border-radius:calc(var(--r-card) - 4px);padding:12px;transition:border-color .14s}
.tarjeta:hover{border-color:var(--line-2)}
.tarjeta summary{cursor:pointer;list-style:none}
.tarjeta summary::-webkit-details-marker{display:none}
.t-top{display:flex;flex-wrap:wrap;gap:4px;align-items:center;margin-bottom:4px}
.t-top .clave{margin-right:auto}
.t-tit{font-weight:500;line-height:1.4}
.meta{display:flex;flex-wrap:wrap;gap:4px 10px;margin-top:8px;font-size:12px;color:var(--ink-2)}
.prog{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--ink-2)}
.prog .barra{flex:1;margin:6px 0}
.pill{display:inline-flex;align-items:center;height:22px;padding:0 9px;border-radius:999px;font-size:11.5px;font-weight:500;
  white-space:nowrap;border:1px solid transparent}
.pill.neutro{background:var(--control);color:var(--ink-2)}
.pill.info{background:var(--info-soft);color:var(--info)}
.pill.warn{background:var(--warn-soft);color:var(--warn)}
.pill.success{background:var(--success-soft);color:var(--success)}
.pill.danger{background:var(--danger-soft);color:var(--danger)}
.t-det{border-top:1px solid var(--line);margin-top:12px;padding-top:4px;font-size:12.5px}
.t-det h4{font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-3);margin:14px 0 6px;font-weight:600}
.t-det ul{margin:0;padding-left:18px}
.campos{display:grid;grid-template-columns:auto 1fr;gap:4px 12px;margin:10px 0 0}
.campos dt{color:var(--ink-3)} .campos dd{margin:0}
.sub{list-style:none;padding:0!important}
.sub li{display:flex;gap:8px;align-items:flex-start;margin:3px 0}
.check{width:14px;height:14px;border-radius:4px;border:1.5px solid var(--line-2);flex:none;margin-top:3px}
.check.si{background:var(--brand);border-color:var(--brand)}
.aviso{padding:8px 10px;border-radius:var(--r-ctl)}
.aviso.danger{background:var(--danger-soft);color:var(--danger)}
.com{margin:6px 0;color:var(--ink-2)}
time{display:block;font-size:11.5px;color:var(--ink-3);font-variant-numeric:tabular-nums}
.bit{list-style:none;padding:0!important;color:var(--ink-2)}
.bit li{display:flex;gap:10px;margin:3px 0}
.bit time{display:inline;flex:none}
.tenue{color:var(--ink-3)}
.vacio{color:var(--ink-3);font-size:12.5px;text-align:center;padding:16px 0;margin:0}
.filtros{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}
.filtros input{flex:1 1 240px}
#cuenta{font-size:12.5px;color:var(--ink-2)}
.tabla{border-radius:var(--r-card);overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:12.5px}
th,td{padding:10px 14px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap;vertical-align:top}
th{position:sticky;top:0;background:var(--card);font-size:11.5px;text-transform:uppercase;letter-spacing:.05em;
  color:var(--ink-3);font-weight:600;cursor:pointer;user-select:none}
th.asc::after{content:" ↑"} th.desc::after{content:" ↓"}
.der{text-align:right}
td.tit{white-space:normal;min-width:280px;font-weight:500;color:var(--ink)}
tbody tr:nth-child(even){background:color-mix(in srgb,var(--well) 60%,transparent)}
tbody tr:hover{background:var(--well)}
tbody tr:last-child td{border-bottom:0}
.nota{font-size:12.5px;color:var(--ink-2);margin:0 0 12px;max-width:760px}
.ses{border-radius:var(--r-card);padding:16px 20px;margin-bottom:12px}
.ses header{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;margin-bottom:10px}
.ses header>.num{color:var(--ink-2);font-size:12.5px}
.ses-kpis{margin-left:auto;display:flex;gap:16px;font-size:12.5px}
.ses-kpis b{font-weight:600}
.ses-reporte{display:flex;flex-wrap:wrap;gap:6px 12px;align-items:baseline;margin:0 0 10px;font-size:13.5px}
.ses-rep{color:var(--accent);font-weight:600;text-decoration:none}
.ses-rep:hover,.ses-rep:focus-visible{text-decoration:underline}
.ses-acts{list-style:none;margin:0;padding:0}
.ses-acts li{display:grid;grid-template-columns:72px minmax(0,1fr) auto;gap:4px 12px;align-items:center;padding:8px 0;border-top:1px solid var(--line)}
.ses-tit{font-weight:500}
.ses-res{grid-column:2 / 4;font-size:12.5px;color:var(--ink-2)}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
@media (max-width:640px){body{padding:16px}.kpi b{font-size:24px}}
"""

JS_TABLERO = """
(function(){
  var d=document.documentElement;
  function guardar(k,v){try{localStorage.setItem(k,v)}catch(e){}}
  var selTema=document.getElementById('tema');selTema.value=d.getAttribute('data-tema');
  selTema.addEventListener('change',function(){d.setAttribute('data-tema',selTema.value);guardar('capitan-tema',selTema.value)});
  var mq=matchMedia('(prefers-color-scheme: dark)');
  function aplicarModo(m){d.setAttribute('data-pref',m);
    d.setAttribute('data-modo',m==='sistema'?(mq.matches?'oscuro':'claro'):m);
    document.querySelectorAll('.seg button').forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.modo===m))})}
  document.querySelectorAll('.seg button').forEach(function(b){b.addEventListener('click',function(){aplicarModo(b.dataset.modo);guardar('capitan-modo',b.dataset.modo)})});
  aplicarModo(d.getAttribute('data-pref')||'sistema');
  mq.addEventListener&&mq.addEventListener('change',function(){if(d.getAttribute('data-pref')==='sistema')aplicarModo('sistema')});
  var vistas=['tablero','lista','sesiones'],tabs=document.querySelectorAll('.tabs button');
  function ver(v){tabs.forEach(function(b){b.setAttribute('aria-selected',String(b.dataset.v===v))});
    vistas.forEach(function(x){document.getElementById('v-'+x).hidden=x!==v});guardar('capitan-vista',v)}
  tabs.forEach(function(b){b.addEventListener('click',function(){ver(b.dataset.v)})});
  try{var g=localStorage.getItem('capitan-vista');if(vistas.indexOf(g)>=0)ver(g)}catch(e){}
  var h=location.hash.slice(1);if(vistas.indexOf(h)>=0)ver(h);
  var tb=document.querySelector('#tabla-lista tbody'),q=document.getElementById('q'),
      fc=document.getElementById('fcol'),fe=document.getElementById('fep'),cu=document.getElementById('cuenta');
  function filtrar(){var s=q.value.toLowerCase(),c=fc.value,ep=fe.value,n=0;
    Array.prototype.forEach.call(tb.rows,function(r){
      var ok=(!s||r.textContent.toLowerCase().indexOf(s)>=0)&&(!ep||r.dataset.epica===ep)&&
             (!c||(c==='abiertas'?r.dataset.col!=='listo':r.dataset.col===c));
      r.hidden=!ok;if(ok)n++});
    cu.textContent=n+' de '+tb.rows.length}
  [q,fc,fe].forEach(function(x){x.addEventListener('input',filtrar)});filtrar();
  var esNum=/^-?[0-9.]+$/;
  document.querySelectorAll('#tabla-lista th').forEach(function(th){th.addEventListener('click',function(){
    var i=+th.dataset.i,asc=!th.classList.contains('asc');
    document.querySelectorAll('#tabla-lista th').forEach(function(x){x.classList.remove('asc','desc')});
    th.classList.add(asc?'asc':'desc');
    var rows=Array.prototype.slice.call(tb.rows);
    rows.sort(function(a,b){var x=a.cells[i].dataset.v,y=b.cells[i].dataset.v;
      var r=(esNum.test(x)&&esNum.test(y))?parseFloat(x)-parseFloat(y):x.localeCompare(y,'es');return asc?r:-r});
    rows.forEach(function(r){tb.appendChild(r)})})});
})();
"""


def main() -> None:
    p = argparse.ArgumentParser(description="Tracker local del método Capitán")
    s = p.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("init"); x.add_argument("nombre"); x.set_defaults(f=cmd_init)
    x = s.add_parser("epica"); x.add_argument("clave"); x.add_argument("nombre"); x.set_defaults(f=cmd_epica)
    x = s.add_parser("crear"); x.add_argument("titulo"); x.add_argument("--epica"); x.add_argument("--tipo", default="mejora", choices=["bug", "mejora", "historia"])
    x.add_argument("--criterio", action="append"); x.add_argument("--subtarea", action="append"); x.add_argument("--depende", action="append")
    x.add_argument("--inicia"); x.add_argument("--termina"); x.add_argument("--importada", action="store_true"); x.add_argument("--columna", default="backlog"); x.set_defaults(f=cmd_crear)
    x = s.add_parser("mover"); x.add_argument("clave"); x.add_argument("columna"); x.set_defaults(f=cmd_mover)
    x = s.add_parser("comentar"); x.add_argument("clave"); x.add_argument("texto"); x.set_defaults(f=cmd_comentar)
    x = s.add_parser("subtarea"); x.add_argument("clave"); x.add_argument("n", type=int); g = x.add_mutually_exclusive_group()
    g.add_argument("--hecha", action="store_true"); g.add_argument("--pendiente", action="store_true"); x.add_argument("--titulo"); x.set_defaults(f=cmd_subtarea)
    x = s.add_parser("fechas"); x.add_argument("clave"); x.add_argument("--inicia", required=True); x.add_argument("--termina", required=True)
    x.add_argument("--forzar", action="store_true"); x.set_defaults(f=cmd_fechas)
    x = s.add_parser("criterios"); x.add_argument("clave"); x.add_argument("--criterio", action="append", required=True); x.set_defaults(f=cmd_criterios)
    x = s.add_parser("bloquear"); x.add_argument("clave"); x.add_argument("motivo"); x.set_defaults(f=cmd_bloquear)
    x = s.add_parser("desbloquear"); x.add_argument("clave"); x.set_defaults(f=cmd_desbloquear)
    x = s.add_parser("listar"); x.add_argument("--abiertas", action="store_true"); x.add_argument("--columna"); x.set_defaults(f=cmd_listar)
    x = s.add_parser("ver"); x.add_argument("clave"); x.set_defaults(f=cmd_ver)
    x = s.add_parser("html"); x.add_argument("--fragmento", help="escribe además la versión para publicar como Artifact")
    x.set_defaults(f=cmd_html)
    x = s.add_parser("sesion"); x.add_argument("--reporte", required=True); x.add_argument("--archivo"); x.add_argument("--id")
    x.set_defaults(f=cmd_sesion)
    a = p.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
