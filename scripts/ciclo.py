#!/usr/bin/env python3
"""El checklist del ciclo de cada actividad, mecánico (plugin capitan).

Es la fuente de verdad del checklist con CUALQUIER tracker: el tracker es un
espejo. Lo escribe solo este script, que valida la evidencia mínima de cada
paso; los hooks lo leen en cada puerta (al lanzar un agente, en el merge a la
rama de sesión, al pasar a Revisión de código y en `gh pr create`). Así que al
agente no se le pase registrar nada no depende de su memoria.

Dónde vive:
  <git común>/capitan/ciclo/ACT-0xx.json   el vivo: lo comparten todos los
      worktrees del repo y no ensucia el árbol (ci_local.py lo exige limpio);
  docs/capitan/ciclo/ACT-0xx.json          la copia que viaja en el PR: se
      escribe al cerrar el paso 16 (o con `exportar`).

Uso (desde el repo):
  ciclo.py listar                        los pasos, leídos del SKILL
  ciclo.py crear ACT-0xx                 crea el checklist (paso 2)
  ciclo.py paso ACT-0xx <n> --hecho "<evidencia>"
                            | --no-aplica "<por qué>"
                            | --omitido "permiso de <dueño>, AAAA-MM-DD: <por qué>"
  ciclo.py ver ACT-0xx                   estado y títulos para el espejo
  ciclo.py exportar ACT-0xx              escribe la copia en docs/capitan/ciclo/ (en cada punto limpio)
  ciclo.py reabrir ACT-0xx <n> --permiso "permiso de <dueño>, AAAA-MM-DD: <por qué>"
                                         reabre un paso mal marcado

Si en este clon no está el vivo pero sí la copia de docs/capitan/ciclo/, lo
retoma de ahí: una actividad a medias sigue en otra máquina.

Cada paso se niega con uno anterior abierto, salvo su par en paralelo (línea
«**En paralelo:**» del SKILL). Los pasos 10, 11 y 12 se pueden volver a
marcar cuando revisan un commit más nuevo: así se registra la revisión
cruzada de un arreglo.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import json
import os
import re
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
SKILL_TRABAJAR = os.path.join(AQUI, "..", "skills", "trabajar", "SKILL.md")
CICLO_PREFIJO = "Ciclo"
ESTADOS = {"hecha": "hecho", "no_aplica": "no aplica", "omitida": "omitido"}
CLAVE = re.compile(r"\b(?:[A-Z][A-Z0-9]*-\d+/)?(ACT-\d+)\b")
SHA = re.compile(r"\b[0-9a-f]{7,40}\b")
REVISO = re.compile(r"\brevis[oó]\s+([0-9a-f]{7,40})\b", re.I)
RANGO = re.compile(r"\b\d{1,2}:\d{2}\s*(?:→|->)\s*\d{1,2}:\d{2}\b")
ROJO = re.compile(r"fail|error|assert|rojo|✗|✘|traceback|exception", re.I)
PERMISO = re.compile(r"permiso\b.*\b\d{4}-\d{2}-\d{2}\b", re.I | re.S)
MEDIDOR = os.path.join(os.path.expanduser("~"), ".claude", "usage-now.json")
MEDIDOR_VIEJO_S = 15 * 60

# Pasos que no pueden cerrarse como «no aplica» (SKILL: las pruebas y la seguridad
# del diff nunca se saltan; la rama, el plan, el código, la entrega y el relevo tampoco).
NO_APLICA_OK = {4, 6, 8, 9, 14}
# Pasos que revisan un commit: se vuelven a marcar cuando revisan uno más nuevo.
REVISAN_COMMIT = {10: "probador", 11: "seguridad del diff", 12: "CI local"}


class Rechazo(Exception):
    """El paso no se puede marcar así; el mensaje dice por qué y qué falta."""


# --------------------------------------------------------------------- SKILL
def pasos_del_ciclo(ruta: str = SKILL_TRABAJAR) -> list[tuple[int, str]]:
    """Los pasos de «El ciclo de una actividad», leídos de su tabla en el SKILL (la única fuente)."""
    try:
        with open(ruta, encoding="utf-8") as f:
            texto = f.read()
    except OSError:
        raise Rechazo(f"No encuentro el SKILL del ciclo en {ruta}")
    m = re.search(r"^## El ciclo de una actividad\s*$(.*?)^## ", texto, re.M | re.S)
    if not m:
        raise Rechazo("El SKILL no trae la sección «## El ciclo de una actividad».")
    pasos = []
    for fila in m.group(1).splitlines():
        r = re.match(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|", fila)
        if r:
            t = re.sub(r"\*\*|`", "", r.group(2))
            t = re.sub(r"\s*\([^)]*\)", "", t).strip()
            pasos.append((int(r.group(1)), t[:1].upper() + t[1:]))
    if [n for n, _ in pasos] != list(range(1, len(pasos) + 1)) or not pasos:
        raise Rechazo("La tabla del ciclo en el SKILL no está numerada 1..N sin huecos.")
    return pasos


def pares_en_paralelo(ruta: str = SKILL_TRABAJAR) -> dict[int, int]:
    """Los pasos que corren a la vez, de la línea «**En paralelo:** 4 y 5 · 10 y 11» del SKILL."""
    try:
        with open(ruta, encoding="utf-8") as f:
            texto = f.read()
    except OSError:
        return {}
    m = re.search(r"\*\*En paralelo:\*\*([^\n]*)", texto)
    pares = {}
    for x, y in re.findall(r"(\d+)\s+y\s+(\d+)", m.group(1) if m else ""):
        pares[int(x)], pares[int(y)] = int(y), int(x)
    return pares


# ----------------------------------------------------------------------- git
def git(cwd: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def sale(cwd: str, *args: str) -> str:
    return git(cwd, *args).stdout.strip()


def raiz(cwd: str) -> str:
    return sale(cwd, "rev-parse", "--show-toplevel") or cwd


def commit(cwd: str, ref: str) -> str | None:
    r = git(cwd, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return r.stdout.strip() if r.returncode == 0 else None


def ancestro(cwd: str, a: str, b: str) -> bool:
    return git(cwd, "merge-base", "--is-ancestor", a, b).returncode == 0


def codigo_despues(cwd: str, sha: str, punta: str) -> list[str]:
    """Commits de punta que no están en sha y tocan algo fuera de docs/."""
    return sale(cwd, "rev-list", f"{sha}..{punta}", "--", ":/", ":(top,exclude)docs").split()


def principal(cwd: str) -> str | None:
    for ref in (sale(cwd, "rev-parse", "--abbrev-ref", "origin/HEAD"), "origin/main", "main", "origin/master", "master"):
        if ref and ref != "origin/HEAD" and commit(cwd, ref):
            return ref
    return None


# --------------------------------------------------------------- el registro
def normalizar(clave: str) -> str:
    m = CLAVE.search(clave.upper())
    if not m:
        raise Rechazo(f"«{clave}» no es una clave de actividad (ACT-0xx).")
    return m.group(1)


def dir_vivo(cwd: str) -> str:
    comun = sale(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not comun:
        raise Rechazo("No estoy dentro de un repo de git: el checklist vive junto al repo.")
    return os.path.join(comun, "capitan", "ciclo")


def ruta_viva(cwd: str, clave: str) -> str:
    return os.path.join(dir_vivo(cwd), normalizar(clave) + ".json")


def ruta_copia(cwd: str, clave: str) -> str:
    return os.path.join(raiz(cwd), "docs", "capitan", "ciclo", normalizar(clave) + ".json")


def leer(cwd: str, clave: str) -> dict | None:
    """El checklist vivo; None si no existe. Si existe y no se puede leer, lanza OSError/ValueError.

    Si no hay vivo pero sí la copia de docs/capitan/ciclo/ (la que se deja en cada punto limpio
    y al cerrar), lo retoma de ahí: así una actividad a medias sigue en otra máquina o en un clon nuevo."""
    ruta = ruta_viva(cwd, clave)
    if not os.path.exists(ruta):
        copia = ruta_copia(cwd, clave)
        if not os.path.exists(copia):
            return None
        with open(copia, encoding="utf-8") as f:
            c = json.load(f)
        escribir(ruta, c)
        return c
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


@contextlib.contextmanager
def candado(cwd: str):
    """Una sola escritura a la vez: los pares en paralelo pueden marcarse al mismo tiempo."""
    os.makedirs(dir_vivo(cwd), exist_ok=True)
    with open(os.path.join(dir_vivo(cwd), ".lock"), "w") as f:
        try:
            import fcntl
            fcntl.flock(f, fcntl.LOCK_EX)
        except ImportError:  # Windows: sin flock, se confía en que no choquen
            pass
        yield


def escribir(ruta: str, datos: dict) -> None:
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, ruta)


def ahora() -> dt.datetime:
    return dt.datetime.now()


def paso_de(c: dict, n: int) -> dict:
    p = next((x for x in c["pasos"] if x["n"] == n), None)
    if not p:
        raise Rechazo(f"El ciclo de {c['clave']} va del 1 al {c['pasos'][-1]['n']}.")
    return p


def cerrado(p: dict) -> bool:
    return p.get("estado", "pendiente") != "pendiente"


def abiertos_antes(c: dict, n: int, pares: dict[int, int] | None = None) -> list[int]:
    """Los pasos anteriores a n que siguen abiertos, sin contar su par en paralelo."""
    pareja = (pares if pares is not None else pares_en_paralelo()).get(n)
    return [p["n"] for p in c["pasos"] if p["n"] < n and p["n"] != pareja and not cerrado(p)]


def abiertos_hasta(c: dict, n: int) -> list[int]:
    return [p["n"] for p in c["pasos"] if p["n"] <= n and not cerrado(p)]


def titulo_espejo(p: dict) -> str:
    base = f"{CICLO_PREFIJO} {p['n']} · {p['titulo']}"
    if not cerrado(p):
        return base
    if p["estado"] == "hecha":
        return f"{base} — {p['nota']}"
    return f"{base} — {ESTADOS[p['estado']]}: {p['nota']}"


def crear(cwd: str, clave: str) -> dict:
    clave = normalizar(clave)
    if leer(cwd, clave) is not None:
        raise Rechazo(f"{clave} ya tiene su checklist del ciclo: `ciclo.py ver {clave}`.")
    c = {"clave": clave, "creado": ahora().strftime("%Y-%m-%d %H:%M"),
         "pasos": [{"n": n, "titulo": t, "estado": "pendiente"} for n, t in pasos_del_ciclo()]}
    escribir(ruta_viva(cwd, clave), c)
    return c


# ------------------------------------------------------------------ medidor
def medidor() -> dict | None:
    """El uso de la cuenta, del medidor de la barra de estado, si está fresco."""
    try:
        with open(MEDIDOR, encoding="utf-8") as f:
            m = json.load(f)
        escrito = dt.datetime.fromisoformat(m["written_at"]).timestamp()
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if dt.datetime.now().timestamp() - escrito > MEDIDOR_VIEJO_S:
        return None
    return {"cinco": m.get("five_hour_pct"), "semana": m.get("seven_day_pct")}


def _pct(x) -> str:
    return "?" if x is None else f"{x:g} %"


def _delta(a, b) -> str:
    return "?" if a is None or b is None else f"{b - a:+g}"


# --------------------------------------------------------------- validación
def _rama(cwd: str, c: dict) -> str:
    rama = (paso_de(c, 1).get("dato") or {}).get("rama")
    if not rama or not commit(cwd, rama):
        raise Rechazo("No sé cuál es la rama de la actividad: el paso 1 debe nombrar una rama que exista.")
    return rama


def _archivo(cwd: str, texto: str) -> str | None:
    r = raiz(cwd)
    for tok in re.findall(r"[\w./-]+\.\w+", texto):
        for base in (r, cwd):
            if os.path.isfile(os.path.join(base, tok)):
                return tok
    return None


def faltan_revisiones(cwd: str, c: dict, punta: str) -> list[str]:
    """Qué paso de 10, 11 y 12 no cubre la punta de la rama (commits de código sin revisar)."""
    problemas = []
    for n, quien in REVISAN_COMMIT.items():
        try:
            p = paso_de(c, n)
        except Rechazo:
            continue
        if p.get("estado") != "hecha":
            continue  # abierto: lo dice la cuenta de pasos; omitido con permiso: no se exige
        sha = (p.get("dato") or {}).get("sha")
        if not sha or not commit(cwd, sha):
            problemas.append(f"el paso {n} ({quien}) no registra un commit que exista en este repo.")
            continue
        if not ancestro(cwd, sha, punta):
            problemas.append(f"el paso {n} ({quien}) revisó {sha[:9]}, que no está en la rama de la actividad.")
            continue
        nuevos = codigo_despues(cwd, sha, punta)
        if nuevos:
            problemas.append(f"el paso {n} ({quien}) revisó {sha[:9]} y después hay {len(nuevos)} commit(s) de "
                             f"código (el último, {nuevos[0][:9]}): vuelve a correrlo sobre la punta y márcalo otra vez.")
    return problemas


def registro_ci(cwd: str, sha: str) -> tuple[str, list[str]] | None:
    """(alcance, últimas líneas) de la corrida de ci_local.py sobre sha, la más reciente."""
    ruta = os.path.join(os.path.dirname(dir_vivo(cwd)), "ci-registro.log")
    try:
        with open(ruta, encoding="utf-8") as f:
            texto = f.read()
    except OSError:
        return None
    hallado = None
    for bloque in re.split(r"^(?===\s)", texto, flags=re.M):
        cab, _, cuerpo = bloque.partition("\n")
        partes = cab.removeprefix("== ").split(" · ")
        if partes and partes[0] == sha:
            alcance = partes[2] if len(partes) >= 4 else "completo"
            hallado = (alcance, [l for l in cuerpo.splitlines() if l.strip()])
    return hallado


def linea_de_estado(texto: str, clave: str) -> str | None:
    m = re.search(r"^## Dónde quedó\s*$(.*?)(?=^## |\Z)", texto, re.M | re.S)
    for l in (m.group(1) if m else texto).splitlines():
        if re.search(rf"\b{re.escape(clave)}\b", l):
            return l
    return None


def validar(cwd: str, c: dict, n: int, nota: str) -> tuple[str, dict]:
    """La evidencia mínima de cada paso hecho. Devuelve (nota final, datos que se guardan)."""
    clave = c["clave"]
    if n == 1:
        ramas = set(sale(cwd, "for-each-ref", "--format=%(refname:short)", "refs/heads").split())
        prin = (principal(cwd) or "").removeprefix("origin/")
        candidatas = [t for t in re.findall(r"[\w./-]+", nota) if t in ramas and t not in (prin, "main", "master")
                      and "-sesion-" not in t]
        numero = int(clave.split("-")[1])
        con_clave = [t for t in candidatas if any(int(x) == numero for x in re.findall(r"act-?(\d+)", t, re.I))]
        rama = (con_clave or candidatas or [None])[0]
        if not rama:
            raise Rechazo("La evidencia del paso 1 nombra la rama de la actividad, y tiene que existir "
                          "(no la principal ni la de sesión).")
        return nota, {"rama": rama}
    if n == 2:
        m, t = medidor(), ahora().strftime("%H:%M")
        cuando = "inicio"
        dato = {"hora": t, "cinco": (m or {}).get("cinco"), "semana": (m or {}).get("semana")}
        extra = f"{cuando} {t} · uso 5 h {_pct(dato['cinco'])} · semana {_pct(dato['semana'])}"
        if not m:
            extra += " · sin medidor (o con más de 15 min sin escribir)"
        return f"{nota} · {extra}", dato
    if n in (5, 9):
        archivo = _archivo(cwd, nota)
        if not archivo:
            raise Rechazo(f"La evidencia del paso {n} lleva la ruta del plan de pruebas, y el archivo tiene que existir "
                          f"(p. ej. docs/capitan/pruebas/{clave}.md).")
        return nota, {"archivo": archivo}
    if n == 6:
        if not ROJO.search(nota):
            raise Rechazo("La evidencia del paso 6 es la salida ROJA pegada del test que reproduce el bug "
                          "(con su FAIL / error / assert).")
        return nota, {}
    if n == 7:
        rama = _rama(cwd, c)
        sha = next((commit(cwd, s) for s in SHA.findall(nota) if commit(cwd, s)), None)
        if not sha or not ancestro(cwd, sha, rama):
            raise Rechazo(f"La evidencia del paso 7 lleva el sha de un commit de la implementación que esté en {rama}.")
        return nota, {"sha": sha}
    if n in (10, 11):
        rama = _rama(cwd, c)
        m = REVISO.findall(nota)
        sha = commit(cwd, m[-1]) if m else None
        if not sha:
            raise Rechazo(f"La evidencia del paso {n} dice qué commit revisó, en la forma «revisó <sha>», "
                          "y ese commit tiene que existir.")
        if not ancestro(cwd, sha, rama):
            raise Rechazo(f"El paso {n} revisó {sha[:9]}, que no está en {rama}.")
        nuevos = codigo_despues(cwd, sha, rama)
        if nuevos:
            raise Rechazo(f"El paso {n} revisó {sha[:9]}, pero {rama} ya tiene {len(nuevos)} commit(s) de código "
                          f"después (el último, {nuevos[0][:9]}): que revise la punta.")
        return nota, {"sha": sha}
    if n == 12:
        rama = _rama(cwd, c)
        punta = commit(cwd, rama)
        reg = registro_ci(cwd, punta)
        if not reg:
            raise Rechazo(f"ci_local.py no ha registrado una corrida verde sobre la punta de {rama} ({punta[:9]}). "
                          "Corre `ci_local.py --areas` en la rama de la actividad y vuelve a marcar.")
        faltan = faltan_revisiones(cwd, c, punta)
        if faltan:
            raise Rechazo("Antes del CI, los revisores tienen que cubrir la punta:\n- " + "\n- ".join(faltan))
        alcance, ultimas = reg
        literal = ultimas[-1] if ultimas else "(sin salida)"
        return f"{nota} · CI {alcance} sobre {punta[:9]}: «{literal}»", {"sha": punta, "alcance": alcance}
    if n == 13:
        rama = _rama(cwd, c)
        for s in SHA.findall(nota):
            sha = commit(cwd, s)
            if not sha:
                continue
            padres = sale(cwd, "rev-list", "--parents", "-n", "1", sha).split()[1:]
            asunto = sale(cwd, "log", "-1", "--format=%s", sha)
            if len(padres) >= 2 and re.search(rf"\b{re.escape(clave)}\b", asunto) and ancestro(cwd, commit(cwd, rama), sha):
                return nota, {"merge": sha, "cuando": int(sale(cwd, "log", "-1", "--format=%ct", sha))}
        raise Rechazo(f"La evidencia del paso 13 lleva el sha del merge `--no-ff` de {rama} a la rama de sesión, "
                      f"con {clave} en su mensaje y la punta de la rama adentro.")
    if n == 15:
        merge = (paso_de(c, 13).get("dato") or {}).get("cuando")
        ruta = os.path.join(raiz(cwd), "docs", "capitan", "estado.md")
        if not os.path.exists(ruta):
            raise Rechazo("No existe docs/capitan/estado.md: el relevo es este paso.")
        if merge and os.path.getmtime(ruta) < merge:
            raise Rechazo("docs/capitan/estado.md no se reescribió después del merge del paso 13.")
        with open(ruta, encoding="utf-8") as f:
            if not linea_de_estado(f.read(), clave):
                raise Rechazo(f"docs/capitan/estado.md («## Dónde quedó») no trae la línea de {clave}.")
        # La medición de cierre la toma el script ahora, con el reloj y el medidor; el dueño la pega en estado.md.
        m, t = medidor(), ahora().strftime("%H:%M")
        ini = paso_de(c, 2).get("dato") or {}
        dato = {"hora": t, "cinco": (m or {}).get("cinco"), "semana": (m or {}).get("semana")}
        medida = (f"{ini.get('hora', '?')} → {t} · uso 5 h {_delta(ini.get('cinco'), dato['cinco'])}"
                  f" · semana {_delta(ini.get('semana'), dato['semana'])}")
        if not m:
            medida += " · sin medidor"
        dato["linea"] = medida
        return f"{nota} · cierre {medida}", dato
    if n == 16:
        medida = (paso_de(c, 15).get("dato") or {}).get("linea")
        ruta = os.path.join(raiz(cwd), "docs", "capitan", "estado.md")
        try:
            with open(ruta, encoding="utf-8") as f:
                linea = linea_de_estado(f.read(), clave) or ""
        except OSError:
            linea = ""
        if not RANGO.search(linea) or "uso" not in linea.lower():
            raise Rechazo(f"La línea de {clave} en docs/capitan/estado.md lleva la medición que imprimió el paso 15"
                          + (f" («{medida}»)" if medida else "") + ": pégala y vuelve a marcar.")
        return nota, {}
    return nota, {}


def reabrir(cwd: str, clave: str, n: int, permiso: str) -> dict:
    """Reabre un paso mal marcado. Solo con el permiso escrito del dueño; lo anterior queda en «antes»."""
    clave = normalizar(clave)
    if not PERMISO.search(permiso or ""):
        raise Rechazo("Reabrir un paso lleva el permiso escrito del dueño: «permiso de <dueño>, AAAA-MM-DD: <por qué>».")
    with candado(cwd):
        c = leer(cwd, clave)
        if c is None:
            raise Rechazo(f"{clave} no tiene el checklist del ciclo.")
        p = paso_de(c, n)
        if not cerrado(p):
            raise Rechazo(f"El paso {n} ya está abierto.")
        p.setdefault("antes", []).append({**{k: p[k] for k in ("estado", "nota", "cuando", "dato") if k in p},
                                          "reabierto": permiso.strip()})
        for k in ("nota", "cuando", "dato"):
            p.pop(k, None)
        p["estado"] = "pendiente"
        escribir(ruta_viva(cwd, clave), c)
        return p


def marcar(cwd: str, clave: str, n: int, estado: str, texto: str) -> tuple[dict, dict]:
    """Cierra (o, en 10/11/12, vuelve a marcar) un paso con su evidencia validada."""
    with candado(cwd):
        return _marcar(cwd, clave, n, estado, texto)


def _marcar(cwd: str, clave: str, n: int, estado: str, texto: str) -> tuple[dict, dict]:
    clave = normalizar(clave)
    c = leer(cwd, clave)
    if c is None:
        raise Rechazo(f"{clave} no tiene el checklist del ciclo: `ciclo.py crear {clave}` (paso 2).")
    p = paso_de(c, n)
    texto = (texto or "").strip()
    if not texto:
        raise Rechazo("Falta el texto: la evidencia, el motivo de «no aplica» o el permiso del dueño.")
    if cerrado(p) and not (n in REVISAN_COMMIT and estado == "hecha" and p["estado"] == "hecha"):
        raise Rechazo(f"El paso {n} ya está cerrado ({ESTADOS[p['estado']]}: {p.get('nota', '')}).")
    abiertos = abiertos_antes(c, n)
    if abiertos:
        raise Rechazo(f"Antes del paso {n} cierra los anteriores: {', '.join(map(str, abiertos))}. "
                      "El checklist manda el orden.")
    dato: dict = {}
    if estado == "hecha":
        texto, dato = validar(cwd, c, n, texto)
    elif estado == "no_aplica":
        if n not in NO_APLICA_OK:
            raise Rechazo(f"El paso {n} no puede cerrarse como «no aplica»: solo se omite con permiso escrito del dueño.")
    elif not PERMISO.search(texto):
        raise Rechazo("Un paso omitido lleva el permiso escrito del dueño: «permiso de <dueño>, AAAA-MM-DD: <por qué>».")
    if cerrado(p):
        p.setdefault("antes", []).append({k: p[k] for k in ("nota", "cuando", "dato") if k in p})
    p.update(estado=estado, nota=texto, cuando=ahora().strftime("%Y-%m-%d %H:%M"))
    if dato:
        p["dato"] = dato
    escribir(ruta_viva(cwd, clave), c)
    if n == len(c["pasos"]) and all(cerrado(x) for x in c["pasos"]):
        escribir(ruta_copia(cwd, clave), c)
    return c, p


# ---------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ciclo.py", description="El checklist del ciclo, mecánico.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("listar")
    for nombre in ("crear", "ver", "exportar"):
        sub.add_parser(nombre).add_argument("clave")
    rp = sub.add_parser("reabrir")
    rp.add_argument("clave")
    rp.add_argument("n", type=int)
    rp.add_argument("--permiso", required=True)
    sp = sub.add_parser("paso")
    sp.add_argument("clave")
    sp.add_argument("n", type=int)
    g = sp.add_mutually_exclusive_group(required=True)
    g.add_argument("--hecho")
    g.add_argument("--no-aplica")
    g.add_argument("--omitido")
    a = ap.parse_args(argv)
    cwd = os.getcwd()
    try:
        if a.cmd == "listar":
            for n, t in pasos_del_ciclo():
                print(f"{CICLO_PREFIJO} {n} · {t}")
        elif a.cmd == "crear":
            c = crear(cwd, a.clave)
            print(f"{c['clave']} · checklist creado. Agrega en el tracker estas subtareas, tal cual:")
            for p in c["pasos"]:
                print("  " + titulo_espejo(p))
        elif a.cmd == "ver":
            c = leer(cwd, a.clave)
            if c is None:
                raise Rechazo(f"{normalizar(a.clave)} no tiene el checklist del ciclo.")
            print(f"{c['clave']} · {sum(cerrado(p) for p in c['pasos'])}/{len(c['pasos'])} cerrados")
            for p in c["pasos"]:
                print(("  [x] " if cerrado(p) else "  [ ] ") + titulo_espejo(p))
        elif a.cmd == "reabrir":
            p = reabrir(cwd, a.clave, a.n, a.permiso)
            print(f"{normalizar(a.clave)} · paso {p['n']} reabierto. Espejo: desmarca la subtarea y ponle «{titulo_espejo(p)}».")
        elif a.cmd == "exportar":
            c = leer(cwd, a.clave)
            if c is None:
                raise Rechazo(f"{normalizar(a.clave)} no tiene el checklist del ciclo.")
            escribir(ruta_copia(cwd, a.clave), c)
            print(os.path.relpath(ruta_copia(cwd, a.clave), raiz(cwd)))
        else:
            estado, texto = (("hecha", a.hecho) if a.hecho is not None else
                             ("no_aplica", a.no_aplica) if a.no_aplica is not None else ("omitida", a.omitido))
            c, p = marcar(cwd, a.clave, a.n, estado, texto)
            print(f"{c['clave']} · paso {p['n']} {ESTADOS[p['estado']]} · ciclo "
                  f"{sum(cerrado(x) for x in c['pasos'])}/{len(c['pasos'])}")
            print("Espejo en el tracker (marca la subtarea y ponle este título):")
            print("  " + titulo_espejo(p))
            if p["n"] == len(c["pasos"]):
                print(f"Copia para el PR: {os.path.relpath(ruta_copia(cwd, c['clave']), raiz(cwd))} (súmala al commit del relevo).")
    except Rechazo as e:
        print(f"ciclo: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
