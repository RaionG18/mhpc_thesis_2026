# Plan de tesis — Intercepción transparente de io_uring en CAPIO

**Tesis MHPC 2026 · Jose (RaionG18)**

- Repo de tesis: <https://github.com/RaionG18/mhpc_thesis_2026>
- Repo upstream: <https://github.com/High-Performance-IO/capio>
- Paper de referencia: *CAPIO: a Middleware for Transparent I/O Streaming in Data-Intensive Workflows* (HiPC 2023, DOI 10.1109/HiPC58850.2023.00031)
- Commit base de CAPIO al elaborar este plan: `6b14036` (2026-05-18). Estado verificado el 2026-06-12.

---

## 0. Contexto y estado verificado

**CAPIO upstream (`main` @ `6b14036`):**

- Cero menciones a io_uring en código, issues o PRs → el gap está libre.
- Dispatch de syscalls en `capio/posix/libcapio_posix.cpp` (`build_syscall_table()` + lista que calcula `CAPIO_NR_SYSCALLS`).
- Handlers en `capio/posix/handlers/*.hpp`, firma `int handler(long arg0..5, long *result)`, retorno `0` (manejado) / `1` (pasar al kernel).
- `mmap` **no** está interceptado actualmente — se necesitará para emular los rings.
- Convenciones: `examples/` (p. ej. `mpi_io_examples/`), `benchmarks/` (`lmbench.sh`, el de la Tabla I del paper), tests en `capio/tests/{unit,integration}`.

**Repo de tesis (estado actual):**

- `capio_iouring/`: *observer* mínimo que interpone `io_uring_submit()` de liburing vía `LD_PRELOAD` y vuelca los SQEs (opcode, fd, len, off, user_data) antes de reenviarlos. Es el prototipo motivacional del capítulo de diseño, no trabajo perdido.

**Supuestos:**

- Tesis escrita en inglés, ~3–4 meses de trabajo efectivo.
- Fork desde `main` de CAPIO, fijado al commit `6b14036` (rebases puntuales, no continuos).
- Kernel ≥ 5.6 en la máquina de desarrollo; el clúster solo hace falta para la evaluación final.

---

## 1. El problema técnico real (la novedad de la tesis)

io_uring solo expone **3 syscalls**: `io_uring_setup` (425), `io_uring_enter` (426), `io_uring_register` (427). Las operaciones de I/O **no son syscalls**: son SQEs escritos en anillos de memoria compartida mmapeada, y las completions se leen del CQ ring **sin ninguna syscall** (el fast-path de `io_uring_peek_cqe`/`io_uring_wait_cqe` es `static inline` en `liburing.h` y lee memoria directamente).

Consecuencias:

- Agregar handlers para 425–427 es necesario pero **insuficiente**: aunque se intercepte `enter`, no se controla la memoria donde la app lee las completions.
- La única forma de que la intercepción sea completa es que **CAPIO sea dueño del ring**: un "CAPIO uring" en espacio de usuario detrás de los 3 handlers (la visión del supervisor: *"almost the same implementation of io_uring, but in userspace"*).

**Research gap citable:** las herramientas basadas en intercepción de syscalls (CAPIO incluido, pero también strace, agentes de seguridad/observabilidad) son ciegas a io_uring. Precedente de emulación userspace: gVisor implementa un subconjunto de io_uring en su kernel de espacio de usuario.

---

## 2. Decisión de diseño (define el capítulo 4 entero)

| Opción | Idea | Pros | Contras |
|---|---|---|---|
| **A. Interposición liburing** (el observer actual, extendido) | Sobrescribir `io_uring_submit`, `__io_uring_get_cqe`, … | Simple; prototipo ya existe | `get_sqe`, `cqe_seen` y el fast-path de peek son `static inline` → no existen como símbolos interponibles; el CQ real es memoria gestionada por el kernel → inyectar CQEs propios crea carreras; no cubre liburing estático ni syscalls crudas |
| **B. Emulación completa a nivel syscall** (**recomendada**) | Handler de `io_uring_setup` devuelve fd falso de CAPIO + `io_uring_params` fabricados; handler nuevo de `mmap` (acotado a fds de ring) entrega memoria anónima propia; handler de `enter` drena la SQ, despacha y publica CQEs en memoria propia | Los inline de liburing operan sobre memoria controlada por CAPIO → los peeks funcionan solos; coherente con la arquitectura `syscall_intercept`; cubre apps sin liburing | Más trabajo: fabricar `params` (`sq_off`/`cq_off`/`features`), emular el protocolo SQ/CQ con el ordering correcto |
| **C. Sub-decisión dentro de B**: SQEs a archivos no-CAPIO en el mismo ring | MVP: ejecutarlos síncronamente dentro de `enter`. Evolución: ring kernel real oculto 1:1 como backend | El MVP preserva corrección con mínimo código | Degrada el rendimiento async de archivos no-CAPIO (documentar como limitación) |

**Decisión tomada (B confirmada por el supervisor):** B con el MVP de C. La opción A **no se completa**: se ejecuta como *spike* time-boxed (F2b) cuyas tres demostraciones de fallo derivan los requisitos de B. Así, A no es una alternativa descartada en abstracto, sino el experimento que deriva la arquitectura — la narrativa central del cap. 4 y de la defensa:

| Fallo demostrado en el spike de A | Requisito de diseño que impone a B |
|---|---|
| Completions leídas inline, sin syscall ni símbolo interponible | CAPIO debe **poseer la memoria del ring** → mmap emulado |
| liburing estático / syscalls crudas invisibles al interposer | Intercepción a **nivel syscall** (`syscall_intercept`) |
| Estado SQ/CQ gestionado por el kernel (head/tail corrompibles) | Ring **fabricado por CAPIO** (fd falso + params propios) |

**Simplificación clave:** procesar los SQEs síncronamente dentro de `io_uring_enter` es **semánticamente correcto**, porque io_uring no garantiza asincronía (el kernel mismo completa inline a menudo). Corrección primero; asincronía como optimización (Fase 5).

---

## 3. Research questions

- **RQ1 (transparencia/corrección):** ¿Puede un middleware de userspace redirigir I/O asíncrona basada en io_uring hacia su propio almacenamiento sin modificar el código de la aplicación, preservando la semántica de la API?
- **RQ2 (overhead):** ¿Cuál es el coste de la emulación userspace frente a io_uring nativo y frente a la ruta POSIX existente de CAPIO?
- **RQ3 (beneficio):** ¿Las semánticas de streaming de CAPIO (CoC/FnU) mantienen sus ganancias de makespan cuando los pasos del workflow usan I/O asíncrona?

---

## 4. Estructura de la tesis (TOC)

1. **Introduction** — motivación (paper CAPIO + adopción de io_uring), contribuciones, RQs.
2. **Background** — workflows file-based y semánticas commit/firing de CAPIO; internals de io_uring (SQ/CQ, mmap, modos); técnicas de intercepción (`LD_PRELOAD`, ptrace, seccomp-unotify, `syscall_intercept`, zpoline).
3. **Related work** — ADIOS / GekkoFS / Damaris (del paper); io_uring como punto ciego del tooling syscall-based; gVisor como emulación userspace. Cierre con tabla de gap.
4. **Design** — spike de la opción A: tres demostraciones de fallo de la interposición liburing y los requisitos que derivan (tabla de §2); arquitectura del CAPIO-uring (B); mapeo SQE → protocolo request/response de CAPIO; proyección de commit/firing sobre operaciones asíncronas.
5. **Implementation** — handlers, estructuras, integración en el codebase; el benchmark/ejemplo.
6. **Evaluation** — ver §8.
7. **Conclusions & future work** — SQPOLL, fixed buffers, backend async real, upstreaming.

---

## 5. Plan de trabajo por fases

### F0 — Reproducir el baseline (~1 semana)

Compilar CAPIO `main`, correr la suite de tests, reproducir el patrón 1-to-1 POSIX bajo `capio_mnt`.

- [ ] Suite de tests verde en la máquina de desarrollo
- [ ] Ejemplo POSIX 1-to-1 correcto bajo `capio_mnt`

### F1 — Entregable A: ejemplo/benchmark io_uring (~1.5 semanas)

Sin tocar CAPIO todavía. Detalle en §6.

- [x] Corre sobre FS plano, checksums producer/consumer idénticos
- [x] Las cuatro configuraciones medidas (FS/CAPIO × posix/uring); CAPIO-uring falla con `EBADF` → el gap que motiva la tesis, medido

*Actualización (2026-08-04): **F1 no lleva PR upstream.** El aparato actual (dos motores, `engine_test.cpp`, `bench.sh` 4-config) es instrumento de medición, no entregable: existe para producir los números del cap. 6 y la evidencia de la defensa. El ejemplo que vaya a `examples/` se limpiará **al final**, cuando CAPIO funcione con uring, y será simple y solo-uring — no tiene sentido publicar un ejemplo que documenta un fallo que para entonces estará arreglado. Nada se borra del fork mientras tanto: el motor POSIX es el grupo de control (prueba que CAPIO funciona y aísla a uring como lo que rompe) y `bench.sh` se re-ejecuta en F6.*

### F2 — Tracing a nivel syscall + spike de la opción A (~2 semanas)

**F2a · Tracing (~1 semana).** Registrar 425–427 con handlers de solo-log que devuelven `1` (pasan al kernel). Es el observer elevado a nivel syscall, y revela exactamente qué offsets de mmap pide liburing antes de emularlos.

- [ ] El demo bajo CAPIO loguea setup/enter
- [ ] Documentados los offsets/flags de mmap observados

**F2b · Spike de la opción A (~1 semana, time-box estricto).** No se intenta completar A: el objetivo es producir las tres demostraciones de fallo que justifican B (material directo para el cap. 4 y la defensa). Reglas de contención: time-box de una semana, y el código vive en el repo de tesis (`spikes/liburing-interposition/`), **nunca en el fork de CAPIO** — el fork queda limpio para la limpieza final de `examples/` y el PR que salga de ella.

- [ ] **Símbolos inline:** `nm -D` sobre `liburing.so` muestra que `get_sqe`/`cqe_seen`/fast-path de peek no existen como símbolos; un bucle de `io_uring_peek_cqe` puro nunca pasa por el interposer
- [ ] **Enlace estático:** el demo compilado con liburing estático deja al observer completamente ciego
- [ ] **Corrupción del ring:** servir un SQE en userspace y entregar el CQE sintético vía `__io_uring_get_cqe` → el `io_uring_cqe_seen` inline de la app avanza el head del CQ real del kernel para un CQE nunca publicado; head adelanta a tail y, por aritmética unsigned, el siguiente peek ve ~2³² completions disponibles (reproducido y documentado con logs)

### F3 — MVP CAPIO-uring (~3–4 semanas) · *núcleo de la tesis*

Fd falso, mmap emulado, params fabricados, `enter` síncrono. Opcodes: `NOP`, `OPENAT`, `READ(V)`, `WRITE(V)`, `CLOSE`, `STATX`, `FSYNC`. Detalle en §7.

- [ ] El benchmark de F1 pasa bajo `capio_mnt` con checksums idénticos
- [ ] Tests POSIX existentes sin regresiones
- [ ] `strace` confirma 0 `io_uring_enter` reales para archivos CAPIO

### F4 — Semánticas de streaming en la ruta uring (~1–2 semanas)

Reads que bloquean hasta *fireable*, EOF al *commit* (reusa la lógica de los dos escenarios de la Sec. IV-A del paper).

- [ ] 1-to-1 con S y Q concurrentes y `on_close` + `no_update` termina correcto

### F5 — Completions asíncronas (*stretch*, ~1–2 semanas)

Hilo que drena respuestas del server CAPIO y publica CQEs.

- [ ] Solape de I/O medible; makespan < versión síncrona

### F6 — Evaluación experimental (~2 semanas)

Detalle en §8.

- [ ] Tablas y gráficas con media ± desviación (10 runs)

### F7 — Escritura (~3–4 semanas, solapada desde F3)

- [ ] Borrador completo revisado por el supervisor

---

## 6. Entregable A: el banco de medición (y, al final, el ejemplo)

*Revisado el 2026-08-04.* Este entregable tiene **dos vidas**, y conviene no confundirlas:

1. **Ahora — banco de medición** (`examples/io_uring/` en el fork, sin PR). Dos motores en un binario, `engine_test.cpp` y `bench.sh` 4-config. Su trabajo es producir números y evidencia: la tabla de cuatro filas del cap. 6 y de la defensa, y la demostración del `EBADF`. El motor POSIX es el **grupo de control** — sin él no se puede afirmar que CAPIO funciona y que lo que rompe es específicamente io_uring. Se conserva íntegro y se re-ejecuta en F6.
2. **Al final — el ejemplo publicable.** Cuando F3+ haga que CAPIO funcione con uring, se limpia `examples/` y queda un ejemplo **simple y solo-uring**, sin motor POSIX, sin batería de tests, sin benchmark. Publicar antes carecería de sentido: el ejemplo de hoy documenta un fallo que para entonces estará arreglado.

Lo que sigue describe el banco actual; los puntos marcados *(→ ejemplo)* son los que sobreviven a la limpieza final.

Ubicación: `examples/io_uring/` (siguiendo la convención de `examples/mpi_io_examples/`).

- **Un solo par producer/consumer en C++** que replica el benchmark *1-to-1* del paper (Fig. 5), con flags `-r producer|consumer` (rol), `-n` (nº archivos), `-f` (tamaño de archivo), `-c` (chunk), `-q` (queue depth), `-e posix|io_uring` y `-d` (directorio). Ambos motores en el mismo binario → comparación A/B limpia. *(→ ejemplo: sobrevive el par producer/consumer sobre uring; desaparecen el flag `-e` y el motor POSIX.)* *Nota (2026-07-21): originalmente planeado en C plano; se pasó a C++ (C++17) para mimetizarse con el resto del repo, que es todo C++. liburing (API de C) se usa sin fricción desde C++.*
- **Verificación por checksum** integrada (como los benchmarks del paper): hace del banco un verificador de corrección, no solo un cronómetro. *(→ ejemplo: sobrevive.)* *Nota (2026-08-04): la comparación se hace por `memcmp` contra el patrón regenerado; FNV-1a queda solo como checksum publicado por el productor. Un hash de 64 bits admite colisiones, y un verificador con falsos negativos no verifica.*
- **JSON de configuración** calcado al de Fig. 5 (`on_close` + `no_update`) para conectar el ejemplo con la semántica. *(→ ejemplo: sobrevive.)*
- **README didáctico**: qué es io_uring en 10 líneas, cómo lanzarlo con y sin CAPIO, salida esperada. *(→ ejemplo: sobrevive, reescrito — hoy documenta el fallo `EBADF`, que para entonces estará arreglado.)*
- Restricción deliberada: **sin** fixed files/buffers, **sin** SQPOLL — solo lo que el MVP soportará. *(→ ejemplo: sobrevive.)*
- `engine_test.cpp` (batería de auto-verificación, 8 checks por motor + equivalencia cruzada) y `bench.sh` (4 configuraciones, mediana, CSV): **instrumento**, no entregable. *(→ ejemplo: se quedan fuera.)*

**Sin PR upstream para F1.** El PR único llega al final, con el ejemplo limpio y ya sobre CAPIO-uring funcionando. El objetivo original de "establecer al autor como contribuidor antes del PR grande" ya está cubierto por otra vía: el **PR #243 se mergeó el 2026-07-22** (`5a6097d`, aprobado por GlassOfWhiskey), que salió de reproducir el baseline en F0.

---

## 7. Entregable B: handlers + runtime uring

**Archivos nuevos** (convención del repo):

- `capio/posix/handlers/io_uring.hpp` — `io_uring_setup_handler`, `io_uring_enter_handler`, `io_uring_register_handler` + dispatcher interno de opcodes.
- `capio/posix/handlers/mmap.hpp` — handlers de `mmap`/`munmap` que **solo** actúan si el fd es un ring CAPIO (si no, retornan `1` y pasan al kernel — cambio quirúrgico).

**Registro:** añadir `SYS_io_uring_*` y `SYS_mmap`/`SYS_munmap` a la lista de `CAPIO_NR_SYSCALLS` y a `build_syscall_table()` en `libcapio_posix.cpp`; incluir los headers en `handlers.hpp`. La tabla crece de ~333 a 428 entradas; coste nulo.

**Estructura central:** tabla global por proceso (con mutex — el hilo que hace submit puede no ser el que recoge completions) de:

```text
CapioRing { fake_fd, sq/cq/sqes mem, params, head/tail }
```

**Detalles duros para el capítulo de diseño** (anticiparlos antes de F3):

- Fabricar `io_uring_params` coherentes; anunciar `IORING_FEAT_SINGLE_MMAP` → liburing hace solo 2 mmaps en vez de 3.
- Rechazar limpio en setup los flags `SQPOLL`/`IOPOLL` (`-EINVAL`).
- Ordering de memoria al actualizar `cq.tail`/`sq.head` (stores release, como hace el kernel).
- `cq_entries = 2 × sq_entries` para no tratar overflow.
- En `enter`, respetar el contrato de `to_submit`/`min_complete` (trivial con procesamiento síncrono).

**Mapeo de opcodes → lógica existente** ("translate requests to io_uring events"):

| Opcode | Reusar | Nota |
|---|---|---|
| `IORING_OP_OPENAT` | lógica de `open.hpp` | devuelve fd CAPIO en `cqe.res` |
| `IORING_OP_READ/READV` | `read.hpp` | `off == -1` → posición actual; `off ≥ 0` → semántica pread |
| `IORING_OP_WRITE/WRITEV` | `write.hpp` | ídem |
| `IORING_OP_CLOSE` | `close.hpp` | dispara la cuenta de closes del commit rule CoC |
| `IORING_OP_STATX` | `statx.hpp` | |
| `IORING_OP_FSYNC`, `NOP` | no-op, `res = 0` | la durabilidad la da el commit rule, no fsync |
| resto | `cqe.res = -EINVAL` | documentado como limitación |

Errores siempre como `-errno` en `cqe.res` (convención io_uring), preservando `user_data`.

---

## 8. Evaluación

**Cuatro configuraciones** (RQ2 y RQ3 salen del mismo experimento): FS-POSIX, FS-uring, CAPIO-POSIX, CAPIO-uring.

**Tres niveles**, calcando la metodología del paper (10 runs, media ± desviación):

1. **Micro-overhead** (análogo a la Tabla I): latencia de `io_uring_enter` con NOPs, nativo vs interceptado. Encaja con el `benchmarks/lmbench.sh` existente.
2. **Patrón sintético 1-to-1** con los tamaños del paper (100×100 MB, 10×1 GB, 1×10 GB; `ws` de 1 KB y 1 MB), usando el ejemplo de F1. Si da tiempo, 1-to-Many.
3. **Validación externa:** `fio --ioengine=io_uring` sobre `capio_mnt` (sin `fixedbufs`/`registerfiles`/`sqthread_poll`). Riesgo conocido: fio hace layout con `fallocate` — probarlo pronto. Demuestra que funciona con código no escrito por el autor (corazón de RQ1).

Con 1–2 nodos basta para la tesis; el clúster es bonus, no bloqueante.

---

## 9. Alcance, limitaciones y riesgos

**Fuera de alcance explícito** (capítulo de limitaciones, no fallos): SQPOLL, IOPOLL, fixed files/buffers (`io_uring_register` devuelve `-ENOTSUP` salvo casos triviales), SQEs encadenados (`IOSQE_IO_LINK`/drain), eventfd, multishot, timeouts.

**Riesgos y mitigaciones:**

- Upstream se mueve rápido → fijar el fork al commit `6b14036`, rebases puntuales.
- La contabilidad de mmap es donde suele subestimarse el esfuerzo → F2 (tracing) va antes de F3 para observar exactamente qué pide liburing.
- fio puede usar syscalls no soportadas (`fallocate`) → probar la integración temprano, degradar a "limitación documentada" si hace falta.

---

## 10. Mapeo con la guía de 6 pasos

| Paso de la guía | Dónde se cubre |
|---|---|
| 1. Tema y supervisor | Hecho |
| 2. Literatura / estado del arte | Caps. 2–3 + lecturas durante F0–F1 |
| 3. Research questions | §3 |
| 4. Proceso y estructura | §4–§5 (este documento) |
| 5. Material y datos empíricos | F1–F6 |
| 6. Escritura | F7 |

Sobre *"novelty over length"*: el claim de novedad es preciso y defendible — **primera redirección transparente de io_uring en un middleware de I/O para workflows**. Una tesis contenida que lo demuestre con el MVP + evaluación vale más que cubrir todos los opcodes.

---

## 11. Punto a validar con el supervisor / próximos pasos

**Resuelto:** el supervisor confirma la opción **B** (emulación a nivel syscall). A se conserva como spike time-boxed (F2b) para derivar los requisitos de B y sostener la narrativa de la defensa.

**Aplazado (2026-08-04):** si el ejemplo vive solo en `examples/` o también como integration test en `capio/tests/integration` se decide **al limpiar `examples/` al final**, no ahora — el ejemplo publicable aún no existe.

**Estado (2026-08-04):** F1 cerrado. Los cuatro hitos hechos y verificados: CLI, FNV-1a + patrón determinista, motor POSIX, motor io_uring con batching. Las cuatro configuraciones medidas (`bench_results.csv`), batería de auto-verificación verde en ambos motores, y el fallo `CAPIO-uring → EBADF` reproducido y documentado. Slides de la charla de avance montadas (`capio_iouring_defense.pptx`).

**Próxima acción:** F2a — tracing de 425–427 con handlers de solo-log que devuelven `1`. Requiere **recompilar CAPIO con `-DCAPIO_LOG=TRUE`**: el build actual tiene `CAPIO_LOG:BOOL=OFF` y el servidor no registra el manejo de peticiones.

---

## Referencias rápidas

- CAPIO: <https://github.com/High-Performance-IO/capio>
- liburing: <https://github.com/axboe/liburing>
- syscall_intercept: <https://github.com/pmem/syscall_intercept>
- J. Axboe, *Efficient IO with io_uring* (documento de diseño de io_uring)
- zpoline: binary-rewriting syscall hooking (USENIX ATC '23) — para el cap. de técnicas de intercepción
- gVisor: emulación parcial de io_uring en userspace — precedente para related work
