---
name: trabajar
description: Avanza solo el plan de un proyecto, actividad por actividad — rama por actividad, puertas de senior-engineer-es, agentes que critican y prueban, un PR por sesión, evidencia en el tracker (uno externo por MCP o el tablero local) y todo documentado en docs/capitan/ para que una conversación nueva sepa exactamente dónde quedó — hasta que algo lo detenga. Úsala cuando el dueño pida avanzar con el plan. Requiere `.claude/capitan.md` (si no existe, /capitan:configurar).
argument-hint: "[presupuesto opcional: «2 actividades», «hasta las 18:00», «solo ACT-020»]"
---

# Capitán · trabajar

Avanzas el desarrollo del proyecto **solo**: tomas la siguiente actividad del
tracker y la llevas hasta su merge en la rama de sesión, con evidencia.
**Sigues con la siguiente hasta que algo te detenga** (§Cuándo te detienes).
No pidas permiso para continuar: lo que necesitas decidir, lo dices y sigues
con lo que no esté bloqueado.

Si el dueño pasó un presupuesto (actividades u hora), gana el límite que llegue
primero entre ese y §Colchón.

## La memoria del proyecto vive en el repo, no en la conversación

Una conversación se llena y se acaba; el proyecto sigue. Todo lo que la
siguiente conversación necesita queda escrito en **`docs/capitan/`**, y el hook
de inicio del plugin se lo inyecta al abrir:

| Archivo | Qué es | Cuándo se escribe |
|---|---|---|
| `estado.md` | **El relevo**: dónde quedó todo, qué sigue, qué espera al dueño, trampas abiertas. Corto (lo lee cada conversación al nacer) | Se **reescribe** al cerrar CADA actividad y al detenerte — no solo al final: si la conversación muere a media sesión, el relevo ya está |
| `decisiones.md` | Las decisiones **vigentes** del dueño: fecha, qué decidió, por qué, a qué aplica. Cuando una se reemplaza, la vieja pasa a `decisiones-historial.md` (que no se inyecta) | En el momento en que el dueño decide, no al cierre. Dos hooks lo cuidan (§Registro de decisiones) |
| `aprendizajes.md` | Lo que salió mal en el proceso (tuyo y de los agentes) y qué regla nació de eso | Al detenerte, desde «Lo que salió mal» del reporte |
| `sesiones/AAAA-MM-DD.md` | El reporte completo de cada sesión | Al detenerte (§Reporte) |
| `tablero.json` / `tablero.html` | El tracker local, si la config lo usa | Solo con `tablero.py` |

**Lo que el hook inyecta tiene tope:** Claude Code deja solo una vista previa
de lo que un hook inyecta si pasa de 10,000 caracteres. El hook no corta nada:
si un archivo no cabe, ordena leerlo completo y pide podarlo. Por eso
`estado.md` es un relevo corto y `decisiones.md` guarda solo lo vigente.

### Registro de decisiones (sin que el dueño lo pida)

- **En cada mensaje del dueño**, `hook_aviso.py` recuerda registrar si trae una
  decisión (regla, criterio, nombre, alcance, corrección, o aprobación de una
  propuesta). Casi gratis.
- **Al cerrar una actividad (`git merge`) y la sesión (`gh pr create`)**,
  `hook_cierre.py` corre el juez (`juez_decisiones.py`, Sonnet): lee lo que el
  dueño escribió desde la última revisión, lo compara con `decisiones.md` y
  **bloquea** el comando si falta alguna. Se registran (o, si el juez se
  equivocó, se anota como falso positivo en `aprendizajes.md`) y se repite el
  comando. Si el juez no puede correr, avisa en pantalla y no bloquea.

**Formato de `estado.md`** (el revisor de reportes lo exige):

```
# Estado del proyecto

**Actualizado:** AAAA-MM-DD HH:MM · sesión AAAA-MM-DD · rama de sesión <rama> · PR <url o «sin PR aún»>

## Dónde quedó
<una línea por actividad tocada: clave · columna · rama · qué falta si quedó a medias>

## Lo que sigue
<la próxima actividad elegible y por qué esa; lo que está bloqueado y por qué>

## Esperando al dueño
<merges, recorridos, decisiones — cada una con su clave>

## Cuidado
<trampas abiertas: un stash ajeno, un ambiente caído, un test inestable, una regla recién decidida>
```

## La configuración del proyecto

Todo lo específico vive en **`.claude/capitan.md`**. Léelo primero. Si no
existe, **detente** y pide correr **`/capitan:configurar`**.

Trae: el **tracker** (`local`, o el tracker externo por MCP con la clave del
proyecto y su tabla de equivalencias en `## Tracker`: cualquier valor que no sea
`local` es un tracker MCP), el
nombre del **dueño** y cómo se le avisa, el plan general, el registro de
defectos, las reglas del repo, el CI-equivalente local, el ambiente de
verificación (o «no hay»), el entorno local (cómo se levanta y se apaga), el
canal de prueba permitido (el teléfono/correo del dueño, o «no hay envíos»),
el medidor de uso (o «no hay») y las reglas propias que no se negocian.

Abajo, `{PROYECTO}` es la clave del proyecto (`ABC-001`; con tablero local, el
prefijo que la config indique o ninguno), `{PLAN}` el archivo del plan y
`{CAPITAN}` la carpeta del plugin: **dos niveles arriba del directorio base de
este skill** (ahí están `scripts/` y `plantillas/`).

## El tracker: una interfaz, dos motores

Con tracker MCP, **la herramienta de cada operación la dice la sección
`## Tracker` de `.claude/capitan.md`** (la armó `/capitan:configurar` con las
herramientas de ese conector). Úsala tal cual; si una operación dice «no
tiene», usa el sustituto que trae. Si la config no trae esa sección (configs
anteriores a la 0.7.4), usa los nombres de la columna «Por omisión» y, si el
conector no los tiene, **detente** y pide correr el Paso 2 de
`/capitan:configurar`: no adivines herramientas que escriben en el tracker del
dueño.

| Operación | Tracker MCP · por omisión | `local` |
|---|---|---|
| Ver el tablero | `listar-actividades` | `python3 {CAPITAN}/scripts/tablero.py listar --abiertas` |
| Ver una actividad | `ver-actividad` | `tablero.py ver ACT-0xx` |
| Crear | `crear-actividades` (tipo, épica en el título, subtareas, `depende_de`, fechas) | `tablero.py crear "<Mx · título>" --epica Mx --tipo … --criterio … --subtarea … --depende … --inicia … --termina …` |
| Mover (solo a la contigua) | `mover-actividades` | `tablero.py mover ACT-0xx <columna>` |
| Subtareas | `gestionar-subtareas` | `tablero.py subtarea ACT-0xx <n> --hecha` |
| Comentar | `comentar` | `tablero.py comentar ACT-0xx "<texto>"` |
| Bloquear | `actualizar-actividades` (bloqueo con motivo) | `tablero.py bloquear ACT-0xx "<motivo>"` |
| Nombre de rama | `crear-rama` → el canónico que devuelve | `<prefijo>-act-0xx-<titulo-corto>` |

Columnas en los dos: Backlog → Por hacer → En curso → Revisión de código →
Pruebas funcionales → Por desplegar → Listo. Un retroceso es retrabajo y queda
en la bitácora. Con el tablero local **nadie edita el JSON ni el HTML a mano**:
`tablero.py` deja bitácora y regenera la página; el JSON va en git y viaja en
el PR. El tablero local no avanza solo con GitHub: los movimientos que en el
tracker MCP hace el merge, aquí los haces tú.

**Qué muestra la página del tablero local** (`tablero.html`, se regenera sola
con cada comando; `tablero.py html` la rehace a mano):

- **Vistas:** tablero por columnas, lista (búsqueda, filtros por columna y
  épica, orden por cualquier campo; `#lista` en la URL) y **sesiones**: cada
  conversación que trabajó en el proyecto, con su costo, duración y % semanal,
  y **qué actividades tocó** y qué hizo en cada una.
- **Por actividad:** creada, plan, inició (entró a En curso), terminó (llegó a
  Listo), tiempo de ejecución, tiempo en la columna actual, consumo mientras
  estuvo en curso, retrabajos y dependencias pendientes. Todo se calcula de la
  bitácora; cada entrada guarda la sesión y su consumo.
- **Consumo = solo el de las sesiones del proyecto**, desde el medidor por
  sesión (§Colchón de uso usa el de la cuenta, que es otra cosa). Costo
  exacto; % semanal aproximado porque incluye lo que se haga en paralelo.
- **Temas** de admin-kit (Esmeralda, Índigo, Naranja) en claro, oscuro o
  sistema; la elección vive en el navegador de quien mira.
- **Migrar de otro tracker:** `tablero.py crear … --importada --columna <c>`
  hace nacer la actividad en su columna, marcada como importada y sin
  movimientos, para no inventar tiempos. Solo al migrar; lo nuevo nace en
  Backlog.

## Las dos guías, siempre alineadas

| Fuente | Qué manda |
|---|---|
| El tracker | El QUÉ SIGUE: orden, estado, dependencias, fechas, evidencia |
| `{PLAN}` | El plan general: épicas, alcance, orden. **Las épicas cerradas NO se editan** |
| Registro de defectos | Evidencia técnica de cada defecto; cada uno cita su clave |

**Conciliar al arrancar y al cerrar cada actividad:** toda actividad abierta
lleva su épica en el título (`M9 · …`) y esa épica existe en `{PLAN}`; todo lo
pendiente de `{PLAN}` tiene su actividad. Si no cuadra, no inventes: va al
resumen y a `Necesito de ti`.

**Cuando el plan crece** (el dueño agrega alcance, o descubres trabajo):
**no basta con crearla, se ACOMODA donde va.** Una actividad mandada al final
deja que lo relacionado se cierre sin ella y luego hay que reabrirlo.

1. **Busca su vecina:** la actividad abierta que toca lo mismo (módulo,
   pantalla, canal, regla). Decide si va **antes** (la vecina la necesita),
   **junto** o **después**.
2. En `{PLAN}` va en la épica ABIERTA de su vecina, en ese lugar — **nunca**
   dentro de una épica cerrada.
3. En el tracker se crea con tipo, épica en el título, subtareas de prueba,
   dependencias y **fecha** según su lugar (antes → termina cuando arranca la
   vecina; junto → misma ventana; después → arranca cuando termina la vecina).
   La duración sale de tu **velocidad medida**, en días hábiles. Si la vecina
   no tiene fecha, tampoco la inventes.
4. Se avisa: *«agregué ACT-0xx — <título>, junto a ACT-0yy, fecha … → …, por
   qué ahí»*.

Las fechas de las actividades **que ya existían no se mueven nunca** (el
tablero local se niega sin `--forzar`, y `--forzar` solo con el OK del dueño):
si la nueva aprieta a una existente, se avisa y el dueño decide.

## Arranque (cada vez)

1. Lee `.claude/capitan.md`, **`docs/capitan/estado.md` y
   `docs/capitan/decisiones.md`** (el hook ya te los dio; si no aparecen en tu
   contexto, léelos tú) y lo que la config nombra.
2. **Carga las skills** de `senior-engineer-es` por nombre completo,
   `senior-engineer-es:orquestador` primero. Si no cargan, **detente**: sin
   ellas las puertas son de palabra.
3. **Lee el uso** (§Colchón) y la hora (`date +%H:%M`).
4. Trae el tablero (§El tracker), abiertas.
5. **¿Se mergeó el PR de la sesión anterior?** (`gh pr list --state merged`).
   Con el tracker MCP, las claves completas en el título del PR mueven las
   tarjetas solas al mergear; comprueba y mueve solo la que no. Con tablero
   local, muévelas tú a Pruebas funcionales.
6. **Resultados de la sesión anterior, ANTES de elegir actividad:** lee lo que
   el dueño marcó y contestó en la página de la sesión anterior (`ArtifactData
   list` de sus colecciones `resultados` y `necesito`) y escríbelo en su `sesiones/…md` y en
   `estado.md`; lo que falló se vuelve actividad nueva con la prueba que lo
   mostró.
7. `git fetch` y parte de la rama principal al día. Árbol limpio; si no lo
   está, no toques lo ajeno — repórtalo.

**Mide cada actividad con el reloj, no de memoria:** al empezarla y al
cerrarla corre `date +%H:%M` y lee el medidor **de la sesión**
(`~/.claude/capitan-sesiones/<proyecto>.json`), y anótalo en ese momento.
**Se reporta lo GASTADO por esta sesión** (cierre − inicio), nunca el % de la
cuenta: ese incluye trabajo ajeno al proyecto. Con tablero local, los
movimientos ya guardan esas fotos solos.

## Elegir la actividad

La primera, en el orden del plan, que: no esté bloqueada · tenga sus
dependencias en Listo (o su código ya en la rama principal) · esté en Backlog o
Por hacer. Si todas esperan algo, **detente**.

**¿Cabe antes del corte? Con TU velocidad medida**, no con la estimación del
tracker: la de las actividades que ya cerraste (inicio → cierre). Solo paras
por tiempo si, con esa velocidad y margen para las revisiones, no cierra. Si
dudas, empieza por la parte que deja un punto limpio temprano.

## El ciclo de una actividad

| # | Paso | Cómo | Puerta |
|---|---|---|---|
| 1 | **Rama propia** | nombre canónico (§El tracker) desde la rama principal | una actividad = una rama. **El PR es por SESIÓN**: la rama de actividad se sube SIN PR y al cerrarla se mergea con `--no-ff` a la rama de sesión (`{proyecto}-sesion-AAAA-MM-DD`, desde la principal al día); al detenerte, UN PR de la rama de sesión contra la principal. Nada de PRs apilados |
| 2 | Moverla a En curso | contigua | — |
| 3 | **Plan** | tú, con `senior-engineer-es:planeacion`: el plan COMPLETO (problema, archivos y capas, decisiones con alternativas, riesgos, orden, cómo sabrás que quedó) | sin plan escrito no hay código |
| 4 | **Crítica** + **seguridad del plan** (en paralelo) | agente fresco **opus** con `senior-engineer-es:critico`: recibe TODO el contexto (la actividad completa · su épica y specs · reglas del repo · el código que toca · hallazgos relacionados) y el plan — NO tu defensa. Seguridad (`senior-engineer-es:seguridad`, opus) cuando toca auth, PII, secretos, consentimiento o algo externo | cada punto se corrige en el plan o se justifica por escrito, ANTES del código |
| 5 | **Plan de pruebas** | agente fresco **opus** con `senior-engineer-es:pruebas`: recibe SOLO los criterios textuales (y los defectos relacionados). **Ni tu plan ni tu código**: prueba lo que se pidió, no lo que tú pensaste. Adversariales primero, y qué debe fallar hoy | — |
| 6 | **Si es bug: reproducir** | `senior-engineer-es:reparador`: test que FALLA hoy, salida pegada | sin reproducción no hay arreglo |
| 7 | **Implementar** | tú, con las convenciones del repo. Lleva una **lista de desvíos** respecto al plan, con su porqué | reglas del repo intactas |
| 8 | **UI** | design system y puerta visual que nombre la config | medida en el navegador, no leída en el código; emergentes ABIERTOS; foco y accesibilidad medidos |
| 9 | **Actualizar el plan de pruebas** (si hubo desvíos) | agente fresco **opus** (`pruebas`): plan original + criterios + desvíos; sin ver el código | — |
| 10 | **Ejecutar las pruebas** | agente fresco **sonnet** (`pruebas` + `verificador`): tests de código Y **recorridos E2E** en el entorno local (usuario de prueba del repo, nunca credenciales reales), con **captura de cada paso**, emergentes abiertos, claro/oscuro, dos anchos y consola. **El E2E local no se salta**: si el usuario de prueba no entra, arreglarlo ES parte de la actividad. Cada test **verde con el cambio y ROJO contra la principal**. PROHIBIDO cambiar un resultado esperado. Recibe el diff y señala lo raro | test que no se vio fallar sin el cambio no cuenta |
| 11 | **Seguridad sobre el diff** | agente **opus** con `senior-engineer-es:seguridad`, en TODA actividad | cada hallazgo se cierra o se justifica por escrito |
| 12 | **Verificador** | tú, con `senior-engineer-es:verificador`: CI-equivalente local + puerta visual con evidencia ejecutada | todo verde o no se sube |
| 13 | **Entregar** | `senior-engineer-es:entrega-git`: commits citando `{PROYECTO}/ACT-0xx`, push de LA RAMA, merge `--no-ff` a la rama de sesión (`Merge {PROYECTO}/ACT-0xx …`) | nunca la principal, nunca merge a la principal, nunca squash |
| 14 | **Documentar en el tracker** | subtareas; comentario (plantilla abajo); mover a **Revisión de código** | — |
| 15 | Hallazgos | al registro de defectos con su clave y, si hay trabajo, actividad nueva | cada uno con **qué pasa, dónde (archivo:línea), evidencia, el test que lo reproduciría y la SOLUCIÓN RECOMENDADA COMPLETA** (§La solución recomendada) |
| 16 | **Relevo y notas** | reescribe `docs/capitan/estado.md`; las decisiones del dueño, a `decisiones.md` en el momento; y anota para el reporte (en `{scratchpad}/sesion.json`): horas y uso de inicio y cierre, agentes, hallazgos, trabajo nuevo y dónde se acomodó, lo no probado, resultados y capturas, qué ver, pendientes del dueño | `estado.md` al día ANTES de tomar la siguiente |

**Actividad chica** (solo textos o estilos): se puede saltar la crítica (4) —
nunca el plan de pruebas, la ejecución ni la seguridad del diff.

**Modelos:** `opus` para crítica, plan de pruebas y seguridad; `sonnet` para
ejecutar pruebas. **Jamás Fable 5.** El sesgo que queda (todos somos el mismo
tipo de modelo) lo cierra el recorrido del dueño: por eso sus pendientes van en
el reporte.

**Entorno local:** levanta solo lo que la actividad necesita y **apágalo al
terminar**.

## Encargos a agentes: el brief base, mecánico

**Los hooks del plugin lo hacen cumplir** en todo repo con `.claude/capitan.md` (además de los de §Registro de decisiones):

- `hook_brief.py` **bloquea** lanzar un agente que pueda escribir si su encargo
  no trae el brief base.
- `hook_git_agentes.py` **bloquea a cualquier subagente** los git que cambian
  estado (Claude Code marca sus comandos con `agent_id`; la sesión principal sí
  hace commits y merges).
- `hook_push.py` **bloquea `git push` de una rama con PR abierto** si el CI
  local no pasó sobre ese mismo commit. Con PR abierto cada push corre el CI
  completo de GitHub y se cobra en minutos de Actions. Se corre
  `python3 {CAPITAN}/scripts/ci_local.py` (usa la fila `| CI local |` de la
  config, exige árbol limpio y anota el commit) y luego se sube. **Con el PR
  abierto, los cambios se juntan** (docs, relevo, reporte) en un solo commit y
  un solo push: cada push es una corrida completa.

Todo encargo empieza pegando TAL CUAL `{CAPITAN}/plantillas/brief-agente.md` y
debajo va lo propio de la tarea. Por qué existe cada regla:

- **Git prohibido al agente**: un probador aplicó un stash viejo de otra sesión
  y dejó el repo en conflicto. Para ver un test fallar contra el código
  anterior: respaldo en /tmp, `git show <ref>:<ruta> > <ruta>`, correr,
  restaurar con `cp`.
- **El probador corre también el build**: sus pruebas rompieron el build de la
  rama de sesión sin que la suite se enterara.
- **Al recibir el reporte, confirma que el agente terminó** sin nada vivo en
  segundo plano.
- **El reporte de un agente es una hipótesis.** Antes del commit, comprueba en
  disco cada afirmación que vaya a quedar en un commit, doc o comentario, y
  corre TAL CUAL cada paso nuevo de CI o deploy, y míralo fallar cuando debe.
- **Al desarrollador, lo que seguridad suele encontrar**: filas ajenas que se
  pisan, PII en errores, valores de quien llama que llegan a un atributo o URL
  sin validar, guardas que fallan abiertas con un vacío, instalaciones sin
  endurecer.
- **E2E de una actividad que depende de otra de la misma sesión**: sobre la
  rama de sesión con las dos ya mergeadas, antes del PR.

## Comentario de cierre en la actividad

```
Qué se hizo: <una o dos líneas>
Rama / PR: <rama> · merge en <rama de sesión> · <url del PR de sesión o «PR al cerrar la sesión»>
Pruebas: <tests nuevos y qué invariante cubre cada uno> — se vieron rojos contra la principal: <cómo>
Resultado: <salida resumida · CI local verde>
Pantalla: <capturas y juicio, o «no aplica»>
Seguridad: <veredicto>
Crítica: <hallazgos del crítico y qué se hizo con cada uno>
NO se probó: <lo honesto>
Velocidad: <inicio → cierre> · uso gastado: 5 h +<x> · semana +<y> · estimado vs real
Para el dueño: <merge · recorrido · decisión>
```

## Después del merge: las pruebas funcionales son tuyas

En cuanto el deploy del merge sale verde, **recorres tú** cada actividad en el
ambiente de verificación contra sus criterios, con capturas, y lo dejas en su
comentario. Si pide iniciar sesión, no tecleas credenciales: le picas al botón
o le pides al dueño que entre. Lo que solo el dueño puede juzgar («¿se
entiende?») va a su página de pendientes. **Envíos de prueba: SOLO al canal de
prueba que la config permite**; jamás a otro.

**Listo = desplegado y verificado en el ambiente de verificación.** Producción
tiene su propia actividad de despliegue. Con tus pruebas pasadas: Pruebas
funcionales → Por desplegar → Listo, con nota en la bitácora. Sin ambiente de
verificación, la config dice qué cuenta como Listo.

## Lo que NUNCA haces

- Merge o push a la rama principal, force-push a ramas ajenas, squash.
- **Mover fechas de actividades que ya existían.**
- Editar épicas cerradas del plan.
- Escribir en otro proyecto del tracker que no sea `{PROYECTO}`.
- Publicar en nombre del dueño (updates, mensajes): solo **borradores**.
- Lo que prohíban las reglas propias de la config.

## Colchón de uso

Si la config nombra un medidor (p. ej. `~/.claude/usage-now.json` con
`five_hour_pct`, `seven_day_pct`, `written_at`), léelo **al empezar cada
actividad, después de cada paso y antes de lanzar cualquier agente**:

- Cualquiera de los dos ≥ **85** → no empieces otra; punto limpio y detente.
  El semanal también cuenta: deja al dueño sin poder trabajar en otra cosa.
- Cruzas 85 a mitad de una actividad → al punto limpio más cercano (commit en
  su rama + push + comentario de dónde quedó + `estado.md`) y detente.
- Medidor ausente o viejo (más de 10 min) → termina la actividad en curso y
  detente preguntando.

Sin medidor en la config, el límite es el presupuesto del dueño o el corte que
indique.

**Punto limpio** = nada a medias sin documentar: la rama, el tracker y
`estado.md` dicen hasta dónde llegó.

## Cuándo te detienes y avisas

Avisa con `PushNotification` (el dueño puede no estar viendo) y **sigue con la
siguiente actividad no bloqueada** cuando: necesitas una decisión suya · una
pantalla necesita su recorrido · una actividad no va a llegar a su fecha (dilo
con la causa; no la muevas) · algo falla fuera del alcance de la actividad.

**Te detienes del todo** cuando: el colchón o el presupuesto se agota · no queda
actividad sin bloqueo · las skills no cargan · falta la config · el árbol trae
cambios ajenos que no entiendes.

## Al detenerte: el reporte de la sesión

Tres piezas, siempre las tres:

1. **`docs/capitan/sesiones/AAAA-MM-DD.md`** (dentro del PR de sesión). Arriba
   el resumen (qué se terminó, PR, tiempo y uso GASTADO, necesito de ti, fechas
   en riesgo, resultado de la sesión anterior); luego POR ACTIVIDAD, **cada
   sección en simple (que el dueño entienda sin preguntar) y en técnico**:
   qué se hizo · hallazgos (dónde, evidencia, gravedad, estado, solución
   recomendada) · trabajo nuevo (de dónde salió y por qué va en ese lugar) ·
   tiempo y uso · pruebas en tres partes (1. **Ejecutadas** por los agentes,
   con capturas y cómo se vieron fallar contra el código viejo — el dueño NO
   las repite; 2. **Para que lo veas**: qué cambió y dónde verlo; 3.
   **Pendientes para el dueño**: SOLO lo que no puedes tú — su login, que algo
   llegue de verdad a su teléfono o bandeja, su criterio, terceros; con pasos
   en simple, qué debe pasar y resultado vacío) · qué no se probó y por qué.
   Al final, **«Lo que salió mal»**: errores tuyos y de los agentes, y qué
   cambiar en el método.
2. **La página de la sesión** (Artifact con base de datos): lo mismo en vista
   amable, con las capturas y su juicio escrito. **No se escribe a mano: sale
   de la plantilla del plugin**, igual en todos los proyectos (§La plantilla).
   Su enlace va en el PR, en el resumen y en `estado.md`.
3. **`estado.md` reescrito** y **`aprendizajes.md`** con lo de «Lo que salió
   mal» (una entrada por lección: fecha, qué pasó, regla que nace).

### La solución recomendada, completa (siempre)

Una línea técnica suelta («la fila con ID solo cambia por el otro flujo») no le
dice al dueño qué va a pasar ni por qué importa. En
el registro de defectos, en la tarjeta y en la página, todo hallazgo ABIERTO
lleva seis partes, en simple:

| Parte | Qué contesta |
|---|---|
| Qué cambiaría | El arreglo en una o dos frases, sin jerga |
| Cómo, paso a paso | Los cambios concretos, en orden (lista) |
| Qué vas a notar tú | Lo que el dueño o quien usa la consola ve distinto |
| Qué pasa si no se hace | El daño real y a quién, con un ejemplo |
| Cómo sabremos que quedó | La prueba que hoy falla y mañana pasa |
| Cuándo y en qué actividad | La clave y por qué en ese momento (antes de qué) |

En `sesion.json` va como `"solucion": {"que_cambia", "como": [...], "para_ti",
"si_no", "prueba", "cuando"}`. La página la muestra a la vista (no plegada) y
`revisar_reporte.py` rechaza un hallazgo abierto al que le falte alguna.

### La plantilla: `sesion.json` → `.md` y página

El `.md` y la página salen de **una sola fuente**, `{scratchpad}/sesion.json`,
que se va llenando en el paso 16 de cada actividad. `python3
{CAPITAN}/scripts/reporte.py --ejemplo` imprime su forma completa.

```
python3 {CAPITAN}/scripts/reporte.py {scratchpad}/sesion.json \
  --md docs/capitan/sesiones/AAAA-MM-DD.md --html {scratchpad}/reporte-AAAA-MM-DD.html
```

La página (estilos y scripts fijos en `{CAPITAN}/plantillas/reporte-sesion.html`;
no se editan por proyecto) trae siempre:

- **Pestañas fijas:** Resumen (con cuántos puntos faltan por responder) ·
  Actividades (N/M leídas) · Hallazgos · Pendientes · Lo que salió mal.
- **«Necesito de ti» que se contesta ahí mismo.** Cada punto explica **por
  qué** y **qué harías tú** (el dueño no debe tener que preguntar), y trae sus
  botones: `"respuesta": "si_no"` (Sí / No), `"hecho"` (Ya lo hice) u
  `"opciones"` propias (a / b, «Otro número»…); siempre «Tengo dudas» y un
  comentario. Se guarda en la colección `necesito` de la página.
- **Cada propuesta dice dónde aplica**, en la página y en el chat: **«solo en
  este proyecto»** (su `.claude/capitan.md`, su código o sus docs) o **«en
  Capitán, para todos los proyectos»** (el plugin). Sin eso el dueño no sabe
  qué está aprobando.
- **«Cómo fue la sesión»** por partes, con horas, uso y las actividades de cada
  una.
- **Una tarjeta por actividad** en el orden en que se atendió, con filtros
  (por parte, con decisión para el dueño, sin leer) y «Marcar como leída».
  El detalle: en simple, lo técnico plegado, «Para ti», **fichas de prueba**
  (qué se hizo, esperado, real, Pasó/Falló y «Contra el código anterior»),
  capturas con su juicio, hallazgos, trabajo nuevo, para que lo veas,
  pendientes y qué no se probó.
- **Hallazgos** como fichas (gravedad, estado, en simple; dónde, evidencia y
  solución plegados) y el **trabajo nuevo** con dónde va y por qué.
- **Pendientes** con Pasó / Falló, comentario y evidencia (imágenes).

Se publica con `capabilities: {db: {}, assets: {}, user: {}}`. Las capturas van
incrustadas (`--no-incrustar` para publicarlas con `files`). Al arrancar la
sesión siguiente (paso 6) se leen las tres colecciones: `resultados`
(`{estado: paso|fallo, comentario, evidencias}`), `necesito` (`{respuesta,
dudas, comentario}`) y `lectura`. Una respuesta con `dudas: true` se contesta
en el chat antes de actuar sobre ella.

**El reporte no se publica sin pasar el revisor** (mecánico, no de memoria):

```
python3 {CAPITAN}/scripts/revisar_reporte.py \
  docs/capitan/sesiones/AAAA-MM-DD.md <pagina.html> docs/capitan/sesiones/<anterior>.md
```

Revisa el `.md`, la página y que `estado.md` se haya reescrito hoy. Con código
1, se completa lo que lista y se vuelve a correr. Marcas que busca: `##
Resumen`, `**Fechas en riesgo:**`, `**Necesito de ti:**`, `**Resultado de la
sesión anterior:**`, `## Trabajo nuevo`, `## Hallazgos`, `**Pendientes para el
dueño**`, `## Lo que salió mal`, y lo **gastado** del uso; por actividad `##
ACT-0xx · título` con `**Tiempo y consumo:**` (HH:MM → HH:MM), `**Agentes:**`,
`### Qué se hizo` (`**En simple:**`, `**Técnico:**`), `### Hallazgos`, `###
Trabajo nuevo`, `### Pruebas` (`**1. Ejecutadas…**` diciendo cómo se vieron
rojas, `**2. Para que lo veas:**`) y `### Qué no se probó`. En la página, cada
actividad es un `<section class="act">` cuyo primer elemento es `<p
class="eyebrow">` con la clave, con «Pruebas ejecutadas» y sus `<figure>` con
`<figcaption>` de juicio (o «Sin capturas: no tiene pantalla»); los pendientes
van en elementos `class="pend"` con botón `class="b-paso"` y `<textarea>`; la
página trae la marca de la plantilla y cada punto de «Necesito de ti» sus
botones, «Tengo dudas» y comentario. Prohibido el juicio «se ve bien». Todo
eso ya lo cumple lo que genera `reporte.py`: si el revisor se queja, falta un
dato en `sesion.json`, no se parcha el HTML.

## Al detenerte: el resumen en el chat

```
Terminé: <ACT-0xx — título>   (una por línea) · PR de sesión: <url>
Agregué: <ACT-0xx — título · junto a ACT-0yy · fecha · por qué ahí>
Quedó a medias: <ACT, rama, qué falta>
Uso gastado: 5 h +<x> · semana +<y> (<inicio> → <cierre>)
Velocidad: <por actividad: estimado vs real> — para que el dueño ajuste fechas (tú no las mueves)
Fechas en riesgo: <ACT — por qué>
Reporte: <enlace de la página> · docs/capitan/sesiones/AAAA-MM-DD.md
Necesito de ti: <merges · recorridos · decisiones>
```

Si el tracker MCP pide un update semanal con fecha de corte, deja además,
antes del corte, el **borrador** del update (p. ej. `sugerir-update-semanal`)
para que el dueño lo capture él.
