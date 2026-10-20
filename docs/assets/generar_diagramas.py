"""Genera los diagramas SVG del README de Capitán (claro/oscuro, sin Mermaid)."""
import sys
from pathlib import Path
from xml.sax.saxutils import escape as esc

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

STYLE = """<style>
.ink{fill:#1f2328}.ink2{fill:#59636e}.card{fill:#f6f8fa;stroke:#d0d7de}
.acc{fill:#1f5c8f}.accs{fill:#e3edf6}.accl{stroke:#1f5c8f}
.br{fill:#9a6b12}.brs{fill:#f6eedb}.brl{stroke:#9a6b12}
.ok{fill:#1a7f37}.oks{fill:#dcf3e3}.okl{stroke:#1a7f37}
.ln{stroke:#8c959f}.lnf{fill:#8c959f}.head{fill:#1f5c8f}.headt{fill:#ffffff}
@media (prefers-color-scheme: dark){
.ink{fill:#e6edf3}.ink2{fill:#9198a1}.card{fill:#161b22;stroke:#30363d}
.acc{fill:#7db3e3}.accs{fill:#1c2c3d}.accl{stroke:#7db3e3}
.br{fill:#e0b25a}.brs{fill:#2e2717}.brl{stroke:#e0b25a}
.ok{fill:#3fb950}.oks{fill:#12261a}.okl{stroke:#3fb950}
.ln{stroke:#6e7681}.lnf{fill:#6e7681}.head{fill:#1c2c3d}.headt{fill:#e6edf3}}
text{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans",Helvetica,Arial,sans-serif}
</style>
<defs><marker id="f" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="lnf"/></marker></defs>"""



W = 900


def svg(name, h, label, body):
    (OUT / name).write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" '
        f'role="img" aria-label="{esc(label)}">\n{STYLE}\n' + "\n".join(body) + "\n</svg>\n")


def t(x, y, s, cls="ink", size=17, weight=400, anchor="start"):
    return (f'<text x="{x}" y="{y}" class="{cls}" font-size="{size}" font-weight="{weight}" '
            f'text-anchor="{anchor}">{esc(s)}</text>')


def card(x, y, w, h, cls="card"):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" class="{cls}" stroke-width="1.5"/>'


def chip(x, y, label, kind, right=False):
    fg, bg = {"agente": ("acc", "accs"), "candado": ("br", "brs"), "tu": ("ok", "oks")}[kind]
    w = int(len(label) * 8.6) + 26
    if right:
        x = x - w
    return [f'<rect x="{x}" y="{y}" width="{w}" height="26" rx="13" class="{bg}"/>',
            t(x + w / 2, y + 18, label, fg, 13.5, 700, "middle")]


def arrow(x1, y1, x2, y2, cls="ln", dash=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="{cls}" stroke-width="2.2"{d} marker-end="url(#f)"/>'


def num(cx, cy, n, cls="acc", r=17):
    return [f'<circle cx="{cx}" cy="{cy}" r="{r}" class="{cls}"/>',
            t(cx, cy + 6.5, str(n), "headt", 17, 700, "middle")]


def tarjeta(b, x, y, w, h, n, tit, lines, chip_=None, ncls="acc"):
    b.append(card(x, y, w, h))
    b.extend(num(x + 34, y + 36, n, ncls))
    b.append(t(x + 62, y + 43, tit, "ink", 20, 700))
    for j, ln in enumerate(lines):
        b.append(t(x + 22, y + 82 + j * 25, ln, "ink2", 17))
    if chip_:
        b.extend(chip(x + 22, y + h - 40, *chip_))


# ---------------------------------------------------------------- configurar
def configurar():
    pasos = [
        ("¿Ya hay configuración?", ["Revisarla, rehacerla o migrar", "la de la versión anterior"]),
        ("Herramientas", ["Skills, GitHub, git limpio, Python,", "medidor de uso y hooks"]),
        ("El tracker", ["Busca tus conectores MCP o", "lo escribes; si no, tablero local"]),
        ("El plan", ["Épicas con alcance y orden;", "si no hay, no lo improvisa"]),
        ("Lo que el plan necesita", ["Dueño, CI local, ambientes, reglas:", "lo busca y te lo confirma"]),
        ("Escribe la configuración", ["capitan.md y docs/capitan/;", "te lo enseña antes de escribir"]),
        ("Concilia plan y tracker", ["Propone cambios; nada se", "escribe sin tu OK"]),
        ("Cierre", ["¿Listo? Sí o no, qué falta", "y quién lo resuelve"]),
    ]
    cw, ch, g, m, vg = 410, 140, 40, 20, 26
    b = []
    for i, (tit, lines) in enumerate(pasos):
        r, c = divmod(i, 2)
        x, y = m + c * (cw + g), 10 + r * (ch + vg)
        tarjeta(b, x, y, cw, ch, i, tit, lines)
        if c == 0:
            b.append(arrow(x + cw + 6, y + ch / 2, x + cw + g - 6, y + ch / 2))
        elif r < 3:
            xr, xl = m + cw + g + cw / 2, m + cw / 2
            b.append(f'<path d="M{xr} {y + ch + 3} V{y + ch + vg / 2} H{xl} V{y + ch + vg - 5}" fill="none" '
                     f'class="ln" stroke-width="2.2" marker-end="url(#f)"/>')
    svg("configurar.svg", 10 + 4 * ch + 3 * vg + 10, "Los 8 pasos de /capitan:configurar", b)


# ---------------------------------------------------------------- sesión
def sesion():
    cw, g, m = 266, 31, 20
    xs = [m + i * (cw + g) for i in range(3)]
    b = []
    # 1 · arranque, a todo lo ancho
    b.append(card(m, 10, W - 2 * m, 104))
    b.extend(num(m + 34, 46, 1))
    b.append(t(m + 62, 53, "Arranca", "ink", 20, 700))
    b.extend(chip(W - m - 22, 31, "CANDADO · RELEVO", "candado", right=True))
    b.append(t(m + 22, 92, "Recibe el relevo y las decisiones, y lee lo que contestaste en el reporte anterior.", "ink2", 17))
    b.append(arrow(W / 2, 118, W / 2, 146))
    # el bucle de actividades
    top, bh = 150, 300
    b.append(f'<rect x="10" y="{top}" width="{W - 20}" height="{bh}" rx="18" fill="none" class="accl" '
             f'stroke-width="2" stroke-dasharray="8 6"/>')
    b.append(t(30, top + 32, "UNA ACTIVIDAD TRAS OTRA", "acc", 14, 700))
    cy, chh = top + 50, 176
    fila = [("Elige", ["La primera sin bloqueo", "que quepa con su", "velocidad real"], None),
            ("La atiende", ["Plan, agentes y pruebas", "en 16 pasos con puertas"], ("6 AGENTES", "agente")),
            ("Cierra", ["Merge a la rama de", "sesión; estado.md al día"], ("CANDADO · JUEZ", "candado"))]
    for i, (tit, ln, ch_) in enumerate(fila):
        tarjeta(b, xs[i], cy, cw, chh, i + 2, tit, ln, ch_)
        if i < 2:
            b.append(arrow(xs[i] + cw + 5, cy + chh / 2, xs[i + 1] - 5, cy + chh / 2))
    ly = cy + chh + 34
    c1, c3 = xs[0] + cw / 2, xs[2] + cw / 2
    b.append(f'<path d="M{c3} {cy + chh + 3} V{ly} H{c1} V{cy + chh + 8}" fill="none" class="accl" '
             f'stroke-width="2.2" marker-end="url(#f)"/>')
    b.append(f'<rect x="{W / 2 - 205}" y="{ly - 16}" width="410" height="32" rx="16" class="accs"/>')
    b.append(t(W / 2, ly + 6, "¿Queda trabajo, uso y tiempo? → la siguiente", "acc", 16, 700, "middle"))
    # salida
    out = top + bh
    b.append(arrow(W / 2, out + 4, W / 2, out + 60))
    b.append(t(W / 2 + 16, out + 38, "Se acabó el trabajo, el uso (85 %) o tu presupuesto", "ink2", 15.5))
    y3, h3 = out + 66, 176
    fila3 = [("Reporte", [".md en el repo y una", "página que contestas"], None, "acc"),
             ("Un solo PR", ["Todas las actividades,", "con el CI local en verde"], ("CANDADO · PUSH", "candado"), "acc"),
             ("Tú decides", ["Recorres, contestas", "y haces el merge"], ("TÚ", "tu"), "ok")]
    for i, (tit, ln, ch_, nc) in enumerate(fila3):
        tarjeta(b, xs[i], y3, cw, h3, i + 5, tit, ln, ch_, nc)
        if i < 2:
            b.append(arrow(xs[i] + cw + 5, y3 + h3 / 2, xs[i + 1] - 5, y3 + h3 / 2))
    svg("sesion.svg", y3 + h3 + 10, "Una sesión de /capitan:trabajar", b)


# ---------------------------------------------------------------- actividad
def actividad():
    tramos = [
        ("Planear", [("1-2", "Rama propia y En curso", None), ("3", "Plan completo por escrito", None),
                     ("4", "Crítica del plan", ("OPUS", "agente")), ("4", "Seguridad del plan", ("OPUS", "agente")),
                     ("5", "Plan de pruebas", ("OPUS", "agente"))], "Sin plan criticado no hay código"),
        ("Construir", [("6", "Si es bug: un test que falla hoy", None), ("7", "Implementar + lista de desvíos", None),
                       ("8", "UI medida en el navegador", None)], "Las reglas del repo, intactas"),
        ("Verificar", [("9", "Ajuste de las pruebas", ("OPUS", "agente")), ("10", "Pruebas y recorridos E2E", ("SONNET", "agente")),
                       ("11", "Seguridad del diff", ("OPUS", "agente")), ("12", "Verificador: CI local", None)],
         "Rojo sin el cambio, verde con él"),
        ("Entregar", [("13", "Merge a la rama de sesión", ("JUEZ", "candado")), ("14", "Comentario en la tarjeta", None),
                      ("15", "Hallazgos con su solución", None), ("16", "Relevo en estado.md", None)],
         "Relevo al día antes de la siguiente"),
    ]
    cw, g, m = 415, 30, 20
    hh, sh, sg, ph = 54, 54, 8, 58
    b = []
    y = 10
    for fila in (0, 1):
        n = max(len(tramos[fila * 2][1]), len(tramos[fila * 2 + 1][1]))
        for c in (0, 1):
            i = fila * 2 + c
            nombre, pasos, puerta = tramos[i]
            x = m + c * (cw + g)
            b.append(f'<rect x="{x}" y="{y}" width="{cw}" height="{hh}" rx="14" class="head"/>')
            b.append(t(x + 22, y + 35, f"{i + 1} · {nombre}", "headt", 21, 700))
            if c == 0:
                b.append(arrow(x + cw + 4, y + hh / 2, x + cw + g - 4, y + hh / 2))
            for j, (k, txt, tag) in enumerate(pasos):
                sy = y + hh + 12 + j * (sh + sg)
                b.append(card(x, sy, cw, sh))
                b.append(t(x + 20, sy + 34, k, "acc", 16, 700))
                b.append(t(x + 62, sy + 34, txt, "ink", 17.5, 600))
                if tag:
                    b.extend(chip(x + cw - 14, sy + 14, tag[0], tag[1], right=True))
            py = y + hh + 12 + n * (sh + sg) + 4
            b.append(f'<rect x="{x}" y="{py}" width="{cw}" height="{ph}" rx="14" class="brs"/>')
            b.append(f'<rect x="{x}" y="{py}" width="6" height="{ph}" rx="3" class="br"/>')
            b.append(t(x + 22, py + 24, "PUERTA", "br", 13, 700))
            b.append(t(x + 22, py + 46, puerta, "ink", 17, 600))
        y = py + ph + 34
        if fila == 0:
            xr, xl = m + cw + g + cw / 2, m + cw / 2
            b.append(f'<path d="M{xr} {py + ph + 3} V{py + ph + 17} H{xl} V{y - 4}" fill="none" '
                     f'class="ln" stroke-width="2.2" marker-end="url(#f)"/>')
    svg("actividad.svg", y - 24, "Los 16 pasos de una actividad, en cuatro tramos", b)


# ---------------------------------------------------------------- agentes
def agentes():
    ags = [
        ("Crítico", "OPUS", "Paso 4 · antes del código",
         ["Revisa el plan sin oír la defensa:", "nadie lo convence de que está bien."]),
        ("Seguridad del plan", "OPUS", "Paso 4 · si toca datos o accesos",
         ["Encuentra el riesgo cuando aún es", "papel, no cuando ya es código."]),
        ("Planeador de pruebas", "OPUS", "Paso 5 · antes del código",
         ["Solo conoce lo que se pidió: sus", "pruebas no heredan los huecos."]),
        ("Ajuste de pruebas", "OPUS", "Paso 9 · si hubo desvíos",
         ["Sabe qué cambió del plan, no cómo:", "sigue midiendo lo que se pidió."]),
        ("Probador", "SONNET", "Paso 10 · tests y recorridos E2E",
         ["Cada prueba se ve roja sin el cambio", "y verde con él; si no, no cuenta."]),
        ("Seguridad del diff", "OPUS", "Paso 11 · en toda actividad",
         ["Lee solo el cambio, línea por línea,", "sin la historia de cómo se hizo."]),
    ]
    cw, ch, g, m = 420, 186, 20, 20
    b = []
    for i, (nom, mod, cuando, ventaja) in enumerate(ags):
        r, c = divmod(i, 2)
        x, y = m + c * (cw + g), 10 + r * (ch + g)
        b.append(card(x, y, cw, ch))
        b.append(t(x + 22, y + 44, nom, "ink", 22, 700))
        b.extend(chip(x + cw - 20, y + 23, "AGENTE · " + mod, "agente", right=True))
        b.append(t(x + 22, y + 72, cuando, "ink2", 16))
        b.append(f'<line x1="{x + 22}" y1="{y + 92}" x2="{x + cw - 22}" y2="{y + 92}" class="ln" stroke-width="1" opacity=".5"/>')
        for j, ln in enumerate(ventaja):
            b.append(t(x + 22, y + 124 + j * 26, ln, "ink", 17.5))
    svg("agentes.svg", 10 + 3 * ch + 2 * g + 10, "Los seis agentes de cada actividad", b)


configurar(); sesion(); actividad(); agentes()
print("ok")
