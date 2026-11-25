# Visor geográfico · establecimientos del SLEP Maule Costa

**Ver el visor:** <https://moounz.github.io/visor-slep-maule-costa/>

Mapa interactivo de los **84 establecimientos** del territorio del SLEP Maule
Costa. Cada punto abre una ficha con identificación, matrícula, vulnerabilidad,
trayectorias y resultados educativos.

> **No es una publicación oficial.** Este visor es una elaboración
> independiente a partir de datos públicos. No es una publicación del SLEP
> Maule Costa ni de las instituciones citadas como fuente, y no representa su
> posición. Las cifras oficiales son las que publica cada institución.

Este repositorio contiene todo lo necesario para revisar cómo se calcula cada
cifra y para reconstruir el visor: el código, la base consolidada y las
pruebas. Lo único que no incluye son las bases ministeriales crudas (~1,9 GB),
que se descargan de los portales oficiales.

---

## Requisitos

- **Python 3.10+** con `pip install -r requirements.txt` (pandas, openpyxl).
- **R** con los paquetes `tidyverse`, `readxl`, `leaflet`, `htmltools`,
  `htmlwidgets` y `scales`.
- **Quarto** para el render. Sirve el que trae RStudio: `build.ps1` lo encuentra
  aunque no esté en el PATH, y hace lo mismo con R.
- **Node.js**, opcional: solo para `tests/probar_buscador.py`. Sin Node, esa
  prueba se omite con un aviso y el resto sigue.

## Cómo se reconstruye

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1             # verifica, renderiza y prueba
powershell -ExecutionPolicy Bypass -File .\build.ps1 -Fuentes    # además rearma la base desde 1_Input/fuentes/
```

`-ExecutionPolicy Bypass` permite correr el script solo esa vez, sin cambiar la
configuración de Windows, que por defecto bloquea los scripts de PowerShell.
Si ya permitiste los scripts en tu equipo, basta con `.\build.ps1`.

`build.ps1` corre estos pasos en orden y se detiene en el primero que falle.
Los dos primeros solo hace falta repetirlos cuando se actualiza alguna fuente:

```bash
python 2_Process/00_extraer_fuentes.py     # ~25 s · lee los ~2 GB de 1_Input/fuentes/
python 2_Process/01_consolidar_base.py     # ~2 s  · arma la base única
python tests/verificar_logica.py           # tramos, columnas y etiquetas
quarto render                              # genera 3_Output/index.html
python tests/verificar_salida.py           # asegura sobre el HTML renderizado
python tests/probar_buscador.py            # prueba el buscador con Node
```

El visor **nunca** lee las fuentes crudas: solo
`3_Output/datos/base_consolidada.xlsx`. Si esa base no existe, el `.qmd` se detiene
con un mensaje que indica qué correr.

### Verificación

Ningún script de `tests/` necesita navegador:

| Script | Cuándo | Qué asegura |
|---|---|---|
| `verificar_logica.py` | antes del render | que los tramos de tamaño cubran a todos sin huecos ni solapes, que las columnas obligatorias existan y que no reaparezcan las etiquetas viejas |
| `verificar_salida.py` | después del render | que `3_Output/index.html` sea autocontenido, no traiga restos del tema Flatly, y liste los cinco tramos y el buscador |
| `probar_buscador.py` | en cualquier momento | extrae de `assets/visor.js` el bloque entre `--BEGIN-PURO--` y `--END-PURO--` y lo corre en Node: normalización sin tildes, umbral de 2 caracteres, tope de 8 resultados, búsqueda por RBD y orden |
| `probar_previsualizacion.py` | después de `tools/previsualizar.py` | que la previsualización traiga las fichas de ejemplo |

Los chunks `control-calidad` y `control-radio` del `.qmd` repiten las aserciones
críticas con `stopifnot()`, así que un render que pasa ya las cumplió.

El render deja el visor en `3_Output/index.html`. El `index.html` de la raíz es
una copia de ese archivo: es la que publica GitHub Pages.

### Previsualizar cambios de estilo sin render

`python tools/previsualizar.py` escribe `3_Output/previsualizacion.html` con el
`assets/visor.css` real y seis fichas de ejemplo. Sirve para revisar CSS sin R
ni Quarto. Imita el marcado de `ficha_html()` en `index.qmd`: si ese marcado
cambia, hay que actualizarlo.

## Estructura

```
visor-slep-maule-costa/
├── index.html                 Copia publicada del visor (la que muestra GitHub Pages)
├── index.qmd                  El visor. Un documento, nueve chunks.
├── _quarto.yml                Dirige la salida a 3_Output/
├── build.ps1                  Reconstruye todo en orden
├── requirements.txt           Dependencias de Python
├── 1_Input/                   Lo que entra
│   ├── establecimientos_slep_maule_costa.xlsx   Lista maestra: 84 filas, 4 columnas
│   │                          (RBD, nombre, comuna, coordenadas). La única que se
│   │                          edita a mano; ningún indicador se copia aquí.
│   └── fuentes/               Bases ministeriales crudas (~1,9 GB). No se incluyen:
│   │                          se descargan de los portales oficiales (ver abajo).
│       ├── matricula_2026/    Resumen de Matrícula Oficial EE (MINEDUC)
│       ├── asistencia_2025/   Asistencia anual por alumno (MINEDUC)
│       ├── rendimiento_2025/  Rendimiento por estudiante (MINEDUC)
│       ├── junaeb_2026/       IVE e IVM por establecimiento
│       ├── simce_2025/        4B · 8B · 2M, un CSV por nivel de agregación
│       └── desvinculacion/    Tasa de incidencia 2010-2024, por comuna
├── 2_Process/                 Solo código
│   ├── 00_extraer_fuentes.py  Reduce las fuentes crudas a tablas por RBD
│   └── 01_consolidar_base.py  Une todo a la base de establecimientos
├── 3_Output/                  Todo lo que se genera
│   ├── datos/
│   │   ├── intermedias/       Una tabla por fuente (se regeneran, no se versionan)
│   │   ├── base_consolidada.xlsx  84 × 111 · hojas "Establecimientos" y "Diccionario".
│   │   │                      Es la que lee el visor. No editar: se regenera.
│   │   └── base_consolidada.csv   La misma tabla, para ver diferencias en git
│   └── index.html             El visor renderizado
├── assets/                    visor.css · visor.js · tipografías locales
├── tests/                     Verificaciones (ver arriba)
└── tools/                     previsualizar.py
```

La hoja **Diccionario** de `base_consolidada.xlsx` lista las 111 variables con
su fuente y su cobertura. Es el registro de trazabilidad del proyecto.

## Fuentes y cobertura

Todas se unen por **RBD**, sobre los 72 establecimientos que lo tienen, salvo
la desvinculación, que se une por **comuna**.

| Fuente | Año | Aporta | Cobertura |
|---|---|---|---|
| Resumen de Matrícula Oficial, MINEDUC | 2026 | Matrícula total y por nivel, sexo, extranjeros, cursos, ruralidad | 72/72 |
| Asistencia anual, MINEDUC | 2025 | Tasa de asistencia, ausentismo crónico | 72/72 |
| Rendimiento por estudiante, MINEDUC | 2025 | Aprobación, reprobación, retiro, promedio general | 72/72 |
| IVE, JUNAEB | 2026 | Grupo prioritario y prioridades A, B y C | 67/72 |
| IVM Establecimientos, JUNAEB | 2026 | Índice y categoría por ciclo | 62/72 (1.º ciclo) |
| SIMCE, Agencia de Calidad | 2025 | Puntajes y estándares de 4.º, 8.º y 2.º medio | 45 · 32 · 10 |
| Tasa de incidencia de la desvinculación, MINEDUC | 2024 | Desvinculación global y del sistema regular **de la comuna** | 5/5 comunas |

---

### Dónde descargar las fuentes

- MINEDUC, Centro de Estudios: <https://centroestudios.mineduc.cl/> y datos
  abiertos en <https://datosabiertos.mineduc.cl/> (matrícula, asistencia,
  rendimiento y desvinculación).
- JUNAEB: <https://www.junaeb.cl/> (IVE e IVM).
- Agencia de Calidad de la Educación:
  <https://informacionestadistica.agenciaeducacion.cl/> (SIMCE).

Para reconstruir la base desde cero, se guardan en `1_Input/fuentes/` con la
estructura descrita arriba y se corre `.\build.ps1 -Fuentes`. Sin las fuentes,
`.\build.ps1` usa la base consolidada que ya viene en el repositorio.

---

## Decisiones metodológicas

Las que cambian las cifras, y por qué:

- **Retiro ≠ traslado.** `SIT_FIN` marca con `Y` tanto al retirado como al
  trasladado. El retiro se calcula con `SIT_FIN_R`, que los separa. Usar
  `SIT_FIN` lo multiplica: en esta base hay 778 traslados frente a 278 retiros.
- **Un solo denominador para el rendimiento.** Aprobación, reprobación y retiro
  se calculan sobre aprobados + reprobados + retirados (`n_base_rendimiento`),
  así que suman 100 %. Antes la aprobación dejaba fuera a los retirados y se
  inflaba: en el territorio, 96,6 % frente al 94,5 % correcto; en la Escuela
  Penitenciaria Mariano Latorre, 70 % frente a 45 %. Los trasladados no entran
  a la base porque cierran el año en otro curso o establecimiento (125 de los
  778 son cambios de curso dentro del mismo RBD, que contarían dos veces).
- **Retiro no es desvinculación.** El retiro (base de rendimiento) es quien
  dejó de asistir durante el año y no pudo ser evaluado. La desvinculación
  (archivo aparte) es quien no aparece matriculado al año siguiente en ninguna
  parte sin haberse graduado. Un retirado que vuelve el año siguiente no es
  desvinculado, y un aprobado que no se matricula sí lo es.
- **Desvinculación por comuna.** El archivo de MINEDUC no trae RBD; su nivel
  más fino útil es la comuna, que incluye a todas las dependencias, no solo al
  SLEP. Cada ficha muestra el dato de su comuna en un bloque aparte, con fondo
  propio y la leyenda «Dato general de los establecimientos de la comuna de …». Se usa
  el último año (desvinculados 2024 sin matrícula 2025) y el primer bloque de la
  hoja (total; los otros dos son mujeres y hombres). Las salas cuna sin RBD no
  reciben el dato: la metodología excluye parvularia.
- **Lista maestra sin indicadores.** `establecimientos_slep_maule_costa.xlsx`
  traía, además de RBD, nombre, comuna y coordenadas, siete columnas copiadas
  del IVM (ruralidad, matrícula, tipo de enseñanza y el índice por ciclo). Eran
  idénticas al archivo del IVM, que el extractor ya lee; se quitaron para que
  una actualización del IVM no deje cifras viejas escritas a mano. La base
  consolidada quedó idéntica byte a byte.
- **Matrícula oficial, no la del IVM.** La base traía la suma de `N_MATRÍCULA`
  del IVM por nivel (13.091). La principal pasó a ser la oficial 2026 (13.397);
  la del IVM queda en `matricula_ivm_total`.
- **Educación de adultos aparte del nivel regular.** MINEDUC cuenta la
  modalidad adultos en columnas propias (`MAT_ENS_3`, `6` y `8`). Sumarlas al
  nivel regular hacía que un liceo sin básica apareciera impartiéndola: el
  Liceo Constitución (RBD 3165) tiene 0 en básica de niños y 2 adultos
  nivelando, y el visor mostraba «Básica». Ahora `mat_basica`, `mat_media_hc` y
  `mat_media_tp` cuentan solo niños y jóvenes; los adultos viven en
  `mat_*_adultos`, y `mat_ninos_jovenes + mat_adultos = matricula`. El total
  del territorio sigue siendo el oficial, 13.397 (12.980 niños y jóvenes más
  417 adultos), para no perder comparabilidad con lo que publica MINEDUC.
  Los chips de nivel se encienden solo con matrícula regular, y la ficha
  desglosa las dos modalidades en bloques separados que nunca se suman.
- **Establecimientos de pura educación de adultos.** Dos lo son: el Liceo T-P
  Mariano Latorre (236) y la Escuela Las Dunas de Chanco (5). Se mantienen en
  el mapa con su matrícula y sus indicadores, pero marcados en la tarjeta del
  cursor y en la ficha, para que no se lean como escuela regular. Cuidado al
  interpretar su asistencia y su rendimiento: están calculados sobre población
  adulta, igual que la parte adulta de Constitución y Antonio Varas.
- **Ruralidad del registro oficial.** Cubre los 72; el IVM solo 68. No hay
  ninguna discrepancia entre ambas donde las dos tienen dato. `ruralidad_fuente`
  deja la huella.
- **Categorías de asistencia.** Las define el MINEDUC por tramo: crítica
  (menos de 50%), grave (50 a 84%), reiterada (85 a 89%) y esperada (90% o
  más). El ausentismo crónico es la suma de las dos primeras.
- **Asistencia ponderada.** Días asistidos sobre días trabajados del
  establecimiento, no el promedio simple de las tasas individuales.
- **SIMCE sin puntaje.** Cuando la Agencia no publica un resultado, la ficha
  dice por qué (casi siempre: 6 o menos estudiantes evaluados) en vez de
  dejarlo en blanco. Los estándares de aprendizaje se publican para menos
  establecimientos que los puntajes: 25 de 45 en 4.º básico.
- **Validación por nombre.** Tanto el consolidador como el `.qmd` comprueban
  los títulos de las columnas, no su posición. Reordenar la base en Excel ya
  no desplaza los datos en silencio.

## Pendiente

- **IDPS.** No hay fuente en `1_Input/fuentes/`; sigue marcado como «Próximamente».
- **Desvinculación por establecimiento.** Hoy se muestra la de la comuna.
  Calcularla por RBD exigiría cruzar el rendimiento 2025 con la base
  *Matrícula por estudiante 2026* (con MRUN), que no está en `1_Input/fuentes/`. Sería
  una estimación propia: MINEDUC además ajusta por fallecidos con datos del
  Registro Civil, que no son públicos.
- **Las 12 salas cuna** seguirán sin indicadores mientras no tengan RBD.

## Licencia

- **Código** (scripts, `index.qmd`, `assets/visor.css`, `assets/visor.js`,
  pruebas): licencia MIT, ver [LICENSE](LICENSE).
- **Base consolidada** (`3_Output/datos/`) y lista de establecimientos
  (`1_Input/`): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.es).
  Se pueden reutilizar citando esta fuente. Los datos originales son de
  MINEDUC, JUNAEB y la Agencia de Calidad de la Educación, y quien los reutilice
  debe citarlos también.
- **Tipografía** Public Sans (`assets/fonts/`): SIL Open Font License 1.1.

---

Elaboración: Alonso Cotal · noviembre de 2026
