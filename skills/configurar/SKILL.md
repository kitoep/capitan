---
name: configurar
description: Deja un repo listo para el método Capitán — revisa herramientas, elige el tracker (uno externo conectado por MCP o el tablero local), ubica o manda a hacer el plan, detecta las pruebas, escribe `.claude/capitan.md`, crea `docs/capitan/` (estado, decisiones, aprendizajes, sesiones) y concilia plan contra tracker. Guía y pregunta en cada decisión. Úsala al adoptar el método en un repo, o si /capitan:trabajar se detuvo por falta de configuración.
---

# Capitán · configurar

Dejas el repo listo para `/capitan:trabajar`. **Guías y preguntas**; no supones.
Cada paso termina con algo verificado, no con «debería estar». Si un paso no
se puede completar, lo dices y dices cómo resolverlo.

Al final el repo tiene **`.claude/capitan.md`** (la config) y
**`docs/capitan/`** (la memoria del proyecto), el plan está ligado a su
tracker, y el dueño sabe exactamente qué falta.

`{CAPITAN}` es la carpeta del plugin: **dos niveles arriba del directorio base
de este skill**.

## Paso 0 — ¿Ya hay configuración?

- Si `.claude/capitan.md` existe: enseña un resumen y pregunta si se **revisa**
  (repasar cada paso contra lo que dice) o se **rehace**. No la sobrescribas
  sin respuesta.
- Si existe una config de la versión anterior del método
  (`.claude/work-tracker-plan.md`) o reportes en `docs/sesiones/`: ofrece
  **migrar** (§Migrar) en vez de empezar de cero.

## Paso 1 — Herramientas (verificadas, no supuestas)

| Qué | Cómo se verifica | Si falla |
|---|---|---|
| Skills `senior-engineer-es` | cargar `senior-engineer-es:orquestador` con la herramienta Skill | sin ellas no hay puertas: que instale el plugin y reinicie Claude Code |
| GitHub | `gh auth status` y que el repo tenga remoto | `gh auth login` (con `!` en el prompt) |
| Git limpio | `git status` | cambios ajenos se reportan, no se tocan |
| Python 3 | `python3 --version` | lo necesitan los hooks y el tablero |
| Medidor de uso (recomendado) | `~/.claude/usage-now.json` y `~/.claude/capitan-sesiones/<proyecto>.json` con `written_at` de menos de 10 min | ver §El medidor. Sin él, el colchón de uso no funciona y el tablero no mide sesiones; anótalo |
| Hooks del plugin | `claude plugin list` muestra `capitan` habilitado | si hay copias personales de los mismos hooks en `~/.claude/settings.json`, avísalo: correrían dos veces. **Pregunta antes de tocar su configuración** |

Reporta la tabla con ✅/❌. Con algún ❌ bloqueante, detente aquí.

### El medidor

Claude Code le pasa a la barra de estado el uso de la cuenta y el costo de la
conversación; `{CAPITAN}/scripts/medidor.py` lo lee y escribe dos archivos:

- `~/.claude/usage-now.json` — uso de **toda la cuenta** (5 h y semanal). Solo
  para el colchón de uso de `/capitan:trabajar`.
- `~/.claude/capitan-sesiones/<proyecto>.json` — consumo de **la conversación
  que trabaja en ese proyecto**: costo y duración exactos y el % semanal que
  subió desde que empezó (aproximado). Es lo único que mide el tablero; jamás
  muestra el consumo de toda la cuenta.

Si falta, ofrécelo y **pide permiso antes de tocar su configuración**:

1. Copia `{CAPITAN}/scripts/medidor.py` a `~/.claude/capitan/medidor.py`
   (ruta estable: la carpeta del plugin cambia con cada versión; el hook de
   inicio mantiene esa copia al día).
2. En `~/.claude/settings.json`, envuelve su barra de estado actual sin
   reemplazarla: `"command": "python ~/.claude/capitan/medidor.py -- <su
   comando actual>"` (sin barra previa: sin `--`). Usa el Python que respondió
   en el Paso 1.
3. Verifica: tras el siguiente refresco de la barra, los dos archivos existen
   con `written_at` reciente.

## Paso 2 — ¿Con qué tracker?

Pregunta con `AskUserQuestion`:

- **Tracker externo (MCP)** — si hay un conector de tracker que responda
  (p. ej. `contexto-actual`). Busca el proyecto (`listar-proyectos` con el
  nombre del repo, el del README y `solo_mios`), sugiere los candidatos (clave ·
  nombre · owner · avance) con el más probable primero, y confirma con
  `ver-proyecto`. Se guarda la **clave** (`ABC-001`), no el nombre. Si no
  existe, crearlo es decisión del dueño.
- **Tablero local** — para proyectos sin tracker. Se crea con
  `python3 {CAPITAN}/scripts/tablero.py init "<nombre>"` en `docs/capitan/`:
  un JSON versionado en git y una página `tablero.html` que se abre en el
  navegador. Pregunta el prefijo de ramas (por omisión, el nombre del repo).

## Paso 3 — El plan

Busca el plan general (`TRACKER.md`, `PLAN.md`, `ROADMAP.md`, `docs/plan*`, lo
que `CLAUDE.md` o el README señalen). Cuenta como plan: **épicas con alcance y
orden**, no una lista suelta.

- **Hay plan** → confírmalo.
- **Hay algo, pero no es plan** → dilo y ofrece convertirlo con
  `senior-engineer-es:planeacion`.
- **No hay plan** → **no lo improvises aquí.** Idea difusa →
  `senior-engineer-es:aterrizar`; repo vacío → `senior-engineer-es:arranque`;
  idea clara → `senior-engineer-es:planeacion`. Con el plan aprobado, se vuelve
  a correr esta configuración. Termina aquí diciendo eso.

## Paso 4 — Lo demás que el plan necesita saber

Encuéntralo tú y **pide confirmación en bloque**:

| Campo | Dónde buscar |
|---|---|
| El dueño | quién decide y prueba; cómo se le avisa (`PushNotification`) |
| Registro de defectos | `docs/hallazgos.md`, `BUGS.md`… — si no hay, proponer uno con sus puertas |
| Reglas del repo | `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md` |
| Puerta visual y design system | docs de UI, paquete de design system |
| CI-equivalente local | `Makefile`, `package.json`, `pyproject.toml`, `.github/workflows/` — **los comandos que corre el CI**, no los que parecen |
| CI local (un comando) | El mismo CI-equivalente en UN comando (p. ej. `make ci`); si el repo no lo tiene, proponer crearlo. Va en la config como fila `| CI local | `<comando>` |`: lo usa el candado de push |
| Rama principal | `git symbolic-ref refs/remotes/origin/HEAD` |
| Ambiente de verificación | docs de deploy, workflows — o «no hay» y qué cuenta como Listo |
| Entorno local | `docker-compose*`, `Makefile` — y cómo se apaga |
| Canal de prueba permitido | el teléfono o correo del propio dueño, o «no hay envíos» |
| Alcance vigente | qué entra en la próxima release, qué está pausado |
| Reglas propias que no se negocian | `CLAUDE.md` |

Lo que no encuentres se pregunta; lo que el dueño no sepa queda como
`(pendiente)`, nunca inventado.

## Paso 5 — Escribir la configuración y la memoria

**Enséñalo antes de escribirlo.**

1. `.claude/capitan.md`: tabla de campos (incluido `Tracker: mcp
   <clave>` o `Tracker: local · prefijo <x>`), CI-equivalente, alcance vigente
   y reglas propias. Su existencia es lo que **enciende los hooks** del plugin
   en este repo.
2. `docs/capitan/`:
   - `estado.md` con el formato de `/capitan:trabajar` (§La memoria del proyecto):
     `**Actualizado:**`, `## Dónde quedó`, `## Lo que sigue`, `## Esperando al
     dueño`, `## Cuidado`;
   - `decisiones.md` con las decisiones que ya existan (en `CLAUDE.md`, en la
     memoria, en lo que el dueño diga ahora), cada una con fecha y porqué;
   - `decisiones-historial.md` y `aprendizajes.md` vacíos con su encabezado;
   - `sesiones/` (con un `.gitkeep`);
   - con tablero local, `tablero.json` y `tablero.html` (Paso 2).
3. No commitees: eso lo decide el dueño.

## Paso 6 — Conciliar plan contra tracker

Trae las actividades y compáralas con el plan:

- actividades que el plan no menciona;
- pendientes del plan sin actividad;
- vencidas, o con un estado que el código contradice;
- de alcance pausado que siguen abiertas.

Propón los cambios (crear, bloquear con motivo, renombrar con su épica,
subtareas de prueba) y **no escribas nada en el tracker sin su OK**. Las fechas
las decide el dueño. Con tablero local recién creado, ofrece poblarlo desde el
plan (una épica por épica del plan, una actividad por pendiente).

## Migrar desde la versión anterior

Si el repo venía con `.claude/work-tracker-plan.md`:

1. Su contenido pasa a `.claude/capitan.md` (añadiendo la línea del tracker).
2. `docs/sesiones/*` se mueve con `git mv` a `docs/capitan/sesiones/`, y se
   actualizan las referencias (`grep -rn "docs/sesiones"`).
3. `estado.md` se escribe desde la última sesión y el tracker;
   `decisiones.md`, desde `CLAUDE.md`, la config y la memoria.
4. La config vieja se borra solo con el OK del dueño.

## Paso 7 — Cierre

```
Listo para /capitan:trabajar: sí / no
Tracker: mcp <clave> — <nombre>  |  local (docs/capitan/tablero.html)
Config: .claude/capitan.md (sin commit) · Memoria: docs/capitan/
Herramientas: <✅/❌ por línea>
Falta: <lo pendiente, con quién lo resuelve>
Siguiente paso: /capitan:trabajar
```
