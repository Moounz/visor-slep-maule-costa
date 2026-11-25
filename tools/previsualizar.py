#!/usr/bin/env python3
"""Arma una previsualización del visor con el `assets/visor.css` real.

Por qué existe: revisar un cambio de CSS exige `quarto render`, que necesita R y
Quarto. En un entorno sin ellos —o simplemente para no regenerar 2,1 MB por cada
ajuste de estilo— este script escribe `3_Output/previsualizacion.html` con el CSS
incrustado, las tipografías en base64 y cinco fichas de ejemplo.

El marcado replica el que produce `ficha_html()` en index.qmd. Si el .qmd cambia
de estructura, este archivo hay que actualizarlo: no lo lee, lo imita.

Uso:  python tools/previsualizar.py
Verificar después con:  python tests/probar_previsualizacion.py
"""
import base64
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CSS = RAIZ / "assets" / "visor.css"
FUENTES = (RAIZ / "assets" / "fonts",)
SALIDA = RAIZ / "3_Output" / "previsualizacion.html"

NA = "<span class='sin-info'>Sin información</span>"
PEND = "<span class='pendiente'>Próximamente</span>"
URBANO = "#0072B2"
RURAL = "#D55E00"


# ---- Piezas de la ficha, calcadas de index.qmd -----------------------------

def fila(etiqueta, valor, nota=None, clase=None):
    return (
        "<div class='fila'><dt>" + etiqueta
        + (f"<small>{nota}</small>" if nota else "")
        + "</dt><dd" + (f" class='{clase}'" if clase else "") + ">"
        + valor + "</dd></div>"
    )


def seccion(titulo, *partes):
    return f"<section class='ficha-sec'><h3>{titulo}</h3>{''.join(partes)}</section>"


def bloque(etiqueta, *partes):
    return (f"<div class='fila-bloque'><div class='et'>{etiqueta}</div>"
            + "".join(partes) + "</div>")


def menor(txt):
    return f" <span class='menor'>{txt}</span>"


def cond(ruralidad, color):
    return f"<span class='cond' style='--c:{color}'><i></i>{ruralidad}</span>"


def chips(presentes, universo=("Parvularia", "Básica", "Media H-C", "Media T-P"),
          apagado="no imparte este nivel"):
    todos = list(dict.fromkeys(list(universo) + list(presentes)))
    out = []
    for n in todos:
        if n in presentes:
            out.append(f"<span class='nivel on'>{n}</span>")
        else:
            out.append(f"<span class='nivel off'>{n}"
                       f"<span class='visually-hidden'> ({apagado})</span></span>")
    return "<div class='niveles'>" + "".join(out) + "</div>"


def barra(ins, ade):
    ele = max(0, 100 - ins - ade)
    trozos = ""
    for ancho, clase in ((ins, "std-ins"), (ele, "std-ele"), (ade, "std-ade")):
        if ancho > 0:
            trozos += f"<span class='{clase}' style='width:{ancho:.1f}%'></span>"
    return f"<div class='std-barra'>{trozos}</div>"


def asignatura(etiqueta, puntaje, n, ins=None, ade=None):
    det = f"{puntaje} pts · {n} estudiantes"
    cuerpo = barra(ins, ade) if ins is not None else ""
    return (f"<div class='std'><div class='std-et'><b>{etiqueta}</b> · {det}</div>"
            + cuerpo + "</div>")


STD_LEYENDA = ("<div class='std-leyenda'>"
               "<span><i class='std-ins'></i>Insuficiente</span>"
               "<span><i class='std-ele'></i>Elemental</span>"
               "<span><i class='std-ade'></i>Adecuado</span>"
               "</div>")

NOTA_PIE = ("<p class='ficha-nota'>Matrícula 2026. Vulnerabilidad 2026. "
            "Asistencia y rendimiento 2025. Desvinculación 2024, por comuna. "
            "SIMCE 2025.</p>")


def bloque_desvinculacion(comuna, anio, glob, regular):
    """Imita bloque_desvinculacion() de index.qmd. glob/regular: (tasa, n, base)."""
    return (
        "<div class='fila-bloque bloque-comuna'>"
        f"<div class='et'>Desvinculación {anio}</div>"
        f"<p class='comuna-marca'>Dato general de los establecimientos de la comuna de <b>{comuna}</b></p>"
        "<dl>"
        + fila("Global", f"{glob[0]}%",
               nota=f"No se matricularon al año siguiente<br>{glob[1]} de {glob[2]} "
                    "estudiantes de la comuna")
        + fila("Sistema regular", f"{regular[0]}%",
               nota="No se matricularon o se pasaron a educación de adultos"
                    f"<br>{regular[1]} de {regular[2]} estudiantes de la comuna")
        + "</dl>"
        "</div>"
    )


# Cifras reales de Pelluhue en la base consolidada
DESV_PELLUHUE = bloque_desvinculacion("Pelluhue", 2024, ("1,52", "22", "1.444"),
                                      ("1,66", "24", "1.446"))


# ---- Las cinco fichas de ejemplo -------------------------------------------

def ficha_completa():
    """Liceo Pelluhue, RBD 3609: todos los indicadores con dato."""
    return (
        f"<div class='ficha-cab' style='--c:{URBANO}'><h2>Liceo Pelluhue</h2></div>"
        + seccion(
            "Información general", "<dl>",
            fila("Comuna", "Pelluhue"),
            fila("RBD", "3609"),
            fila("Ruralidad", cond("Urbano", URBANO)),
            fila("Cursos", "36"),
            "</dl>",
            bloque("Niveles que imparte",
                   chips(("Parvularia", "Básica", "Especial", "Media H-C", "Media T-P"))),
        )
        + seccion(
            "Matrícula 2026", "<dl>",
            fila("Total", "972", clase="num-grande"),
            "</dl>",
            bloque("Por nivel", "<dl>",
                   fila("Parvularia", "65"), fila("Básica", "450"),
                   fila("Media H-C", "337"), fila("Media T-P", "102"), "</dl>"),
            bloque("Composición", "<dl>",
                   fila("Mujeres", "513" + menor("(52,8%)")),
                   fila("Hombres", "459" + menor("(47,2%)")),
                   fila("Extranjeros", "37" + menor("(3,8%)")), "</dl>"),
            "<p class='ficha-aviso'>Resumen de Matrícula Oficial 2026 (MINEDUC), "
            "con corte al 30 de abril de 2026.</p>",
        )
        + seccion(
            "Vulnerabilidad", "<dl>",
            fila("Índice de Vulnerabilidad Escolar (IVE)", "87,5%",
                 nota="Alumnos del grupo prioritario"),
            "</dl>",
            bloque("Prioridad acumulada", "<dl>",
                   fila("Prioridad A", "40,6%"), fila("Prioridad B", "53,5%"),
                   fila("Prioridad C", "69,2%"), "</dl>"),
            bloque("Índice de Vulnerabilidad Multidimensional (IVM), por ciclo", "<dl>",
                   fila("Parvularia", "9,1"),
                   fila("1º Ciclo Básico", "9,6"),
                   fila("2º Ciclo Básico", "6,0"),
                   fila("Enseñanza Media", "11,0"), "</dl>"),
            "<p class='ficha-aviso'>Las prioridades del IVE son acumuladas: A está "
            "contenida en B, y B en C. Un valor mayor del IVM indica mayor "
            "concentración de factores de riesgo.</p>",
        )
        + seccion(
            "Trayectorias 2025", "<dl>",
            fila("Asistencia", "86,0%", nota="Días asistidos sobre días trabajados",
                 clase="num-grande"),
            fila("Ausentismo crónico", "30,3%",
                 nota="Alumnos que asisten a menos del 85% de los días"),
            fila("Asistencia esperada", "49,0%",
                 nota="Alumnos que asisten al 90% o más"),
            "</dl>",
            DESV_PELLUHUE,
            bloque("Resultado del año", "<dl>",
                   fila("Aprobación", "95,5%"), fila("Reprobación", "1,9%"),
                   fila("Retiro", "2,6%", nota="No incluye traslados"),
                   fila("Promedio general", "6,0"), "</dl>"),
            "<p class='ficha-aviso'>Sobre 933 estudiantes que aprobaron, reprobaron o "
            "se retiraron en 2025; las tres tasas suman 100%. No se cuentan 46 "
            "traslados, que cierran el año en otro curso o establecimiento.</p>",
        )
        + seccion(
            "Resultados educativos",
            "<div class='grado'><div class='grado-tit'><b>4º básico</b>"
            "<small>Grupo socioeconómico: Medio bajo</small></div>"
            + asignatura("Lectura", "294", "39", 23.1, 59.0)
            + asignatura("Matemática", "264", "41", 34.1, 24.4)
            + STD_LEYENDA + "</div>",
            "<dl>",
            fila("Indicadores de Desarrollo Personal y Social (IDPS)", PEND),
            "</dl>",
        )
        + NOTA_PIE
    )


def ficha_sin_datos():
    """Escuela rural sin RBD: la ficha es casi toda ausencia de información."""
    return (
        f"<div class='ficha-cab' style='--c:#7F7F7F'><h2>Escuela Rural Los Maitenes</h2></div>"
        + seccion(
            "Información general", "<dl>",
            fila("Comuna", "Chanco"), fila("RBD", NA),
            fila("Ruralidad", NA), fila("Cursos", NA), "</dl>",
            bloque("Niveles que imparte",
                   "<p class='ficha-aviso'>No imparte ningún nivel a niños y jóvenes</p>"),
        )
        + seccion("Matrícula 2026", "<dl>", fila("Total", NA, clase="num-grande"), "</dl>",
                  "<p class='ficha-aviso'>Resumen de Matrícula Oficial 2026 (MINEDUC), "
                  "con corte al 30 de abril de 2026.</p>")
        + seccion("Vulnerabilidad", "<dl>",
                  fila("Índice de Vulnerabilidad Escolar (IVE)", NA,
                       nota="Alumnos del grupo prioritario"),
                  "</dl>")
        + seccion("Trayectorias 2025", "<dl>",
                  fila("Asistencia", NA, nota="Días asistidos sobre días trabajados",
                       clase="num-grande"),
                  fila("Ausentismo crónico", NA,
                       nota="Alumnos que asisten a menos del 85% de los días"),
                  fila("Asistencia esperada", NA,
                       nota="Alumnos que asisten al 90% o más"), "</dl>")
        + seccion("Resultados educativos",
                  "<p class='grado-nota'>El establecimiento no rinde los grados "
                  "evaluados por el SIMCE 2025.</p>",
                  "<dl>", fila("Indicadores de Desarrollo Personal y Social (IDPS)",
                               PEND), "</dl>")
        + NOTA_PIE
    )


def ficha_solo_adultos():
    """Liceo T-P Mariano Latorre: toda su matrícula es nivelación de adultos."""
    return (
        f"<div class='ficha-cab' style='--c:{URBANO}'><h2>Liceo Técnico Profesional "
        "Mariano Latorre</h2>"
        "<p class='marca-adultos solo'>Establecimiento de educación de adultos: toda su "
        "matrícula corresponde a nivelación de estudios para personas adultas.</p></div>"
        + seccion(
            "Información general", "<dl>",
            fila("Comuna", "Curepto"), fila("RBD", "3612"),
            fila("Ruralidad", cond("Urbano", URBANO)), fila("Cursos", "8"), "</dl>",
            bloque("Niveles que imparte",
                   "<p class='ficha-aviso'>No imparte ningún nivel a niños y jóvenes</p>"),
            bloque("Niveles en educación de adultos",
                   chips(("Básica", "Media H-C"),
                         universo=("Básica", "Media H-C", "Media T-P"),
                         apagado="no imparte este nivel en modalidad adultos")),
        )
        + seccion(
            "Matrícula 2026", "<dl>",
            fila("Total", "236", clase="num-grande"), "</dl>",
            bloque("Educación de adultos, por nivel", "<dl>",
                   fila("Básica", "71"), fila("Media H-C", "165"), "</dl>",
                   "<p class='ficha-aviso'>Nivelación de estudios para personas adultas. "
                   "MINEDUC la cuenta aparte del nivel regular: el total de arriba incluye "
                   "las dos modalidades, y los niveles no se suman entre sí.</p>"),
            bloque("Composición", "<dl>",
                   fila("Mujeres", "128" + menor("(54,2%)")),
                   fila("Hombres", "108" + menor("(45,8%)")),
                   fila("Extranjeros", "2" + menor("(0,8%)")),
                   fila("Educación de adultos", "236" + menor("(100,0%)"),
                        nota="Ya desglosada arriba, no se suma"), "</dl>"),
        )
        + seccion("Vulnerabilidad", "<dl>",
                  fila("Índice de Vulnerabilidad Escolar (IVE)", "92,1%",
                       nota="Alumnos del grupo prioritario"),
                  "</dl>")
        + NOTA_PIE
    )


def ficha_nombre_largo():
    """El nombre más largo que puede traer la base, para probar el desborde."""
    nombre = "Escuela Básica Particular Subvencionada Nuestra Señora del Carmen de Chanco"
    return (
        f"<div class='ficha-cab' style='--c:{RURAL}'><h2>{nombre}</h2></div>"
        + seccion(
            "Información general", "<dl>",
            fila("Comuna", "Chanco"), fila("RBD", "3598"),
            fila("Ruralidad", cond("Rural", RURAL)),
            fila("Cursos", "9" + menor("(3 combinados)"),
                 nota="Combinados: más de un nivel en la misma sala"), "</dl>",
            bloque("Niveles que imparte", chips(("Parvularia", "Básica"))),
        )
        + seccion("Matrícula 2026", "<dl>", fila("Total", "87", clase="num-grande"),
                  "</dl>", bloque("Por nivel", "<dl>", fila("Parvularia", "18"),
                                  fila("Básica", "69"), "</dl>"))
        + NOTA_PIE
    )


def ficha_sin_simce():
    """Sección «Resultados educativos» con un solo párrafo y ningún bloque."""
    return (
        f"<div class='ficha-cab' style='--c:{RURAL}'><h2>Escuela Las Dunas</h2></div>"
        + seccion("Información general", "<dl>",
                  fila("Comuna", "Chanco"), fila("RBD", "3604"),
                  fila("Ruralidad", cond("Rural", RURAL)), fila("Cursos", "2"), "</dl>")
        + seccion("Resultados educativos",
                  "<p class='grado-nota'>El establecimiento no rinde los grados "
                  "evaluados por el SIMCE 2025.</p>",
                  "<dl>", fila("Indicadores de Desarrollo Personal y Social (IDPS)",
                               PEND), "</dl>")
        + NOTA_PIE
    )


def ficha_adultos_mixto():
    """Liceo Constitución (RBD 3165): régimen regular y además adultos.

    Es la variante sin `.solo` de la marca, con filete arena: la que quedaba
    invisible cuando el encabezado de la ficha pasó a blanco.
    """
    return (
        f"<div class='ficha-cab' style='--c:{URBANO}'><h2>Liceo Constitución</h2>"
        "<p class='marca-adultos'>Imparte además educación de adultos: 2 "
        "estudiantes en nivelación de estudios.</p></div>"
        + seccion(
            "Información general", "<dl>",
            fila("Comuna", "Constitución"), fila("RBD", "3165"),
            fila("Ruralidad", cond("Urbano", URBANO)), fila("Cursos", "24"), "</dl>",
            bloque("Niveles que imparte", chips(("Media H-C", "Media T-P"))),
            bloque("Niveles en educación de adultos",
                   chips(("Básica",), universo=("Básica", "Media H-C", "Media T-P"),
                         apagado="no imparte este nivel en modalidad adultos")),
        )
        + seccion(
            "Matrícula 2026", "<dl>",
            fila("Total", "614", clase="num-grande"), "</dl>",
            bloque("Niños y jóvenes, por nivel", "<dl>",
                   fila("Media H-C", "398"), fila("Media T-P", "214"), "</dl>"),
            bloque("Educación de adultos, por nivel", "<dl>",
                   fila("Básica", "2"), "</dl>",
                   "<p class='ficha-aviso'>Nivelación de estudios para personas "
                   "adultas. MINEDUC la cuenta aparte del nivel regular: el total "
                   "de arriba incluye las dos modalidades, y los niveles no se "
                   "suman entre sí.</p>"),
            bloque("Composición", "<dl>",
                   fila("Mujeres", "301" + menor("(49,0%)")),
                   fila("Educación de adultos", "2" + menor("(0,3%)"),
                        nota="Ya desglosada arriba, no se suma"), "</dl>"),
        )
        + NOTA_PIE
    )


FIXTURES = (
    ("fx-completo", "Ficha completa — Liceo Pelluhue, todos los indicadores con dato",
     ficha_completa, 1150),
    ("fx-sin-datos", "Ficha sin datos — casi todas las filas dicen «Sin información»",
     ficha_sin_datos, 760),
    ("fx-solo-adultos", "Establecimiento de pura educación de adultos",
     ficha_solo_adultos, 860),
    ("fx-adultos-mixto", "Régimen regular más educación de adultos (marca con filete arena)",
     ficha_adultos_mixto, 920),
    ("fx-nombre-largo", "Nombre largo — 74 caracteres en un panel de 396 px",
     ficha_nombre_largo, 560),
    ("fx-sin-simce", "Sección con un solo párrafo y ningún bloque",
     ficha_sin_simce, 520),
)


# ---- Piezas de fuera de la ficha -------------------------------------------

CABECERA = """<header class='visor-cabecera'>
<div class='cab-texto'>
<p class='cab-marca'>Visor geográfico</p>
<h1>Establecimientos del SLEP Maule Costa</h1>
<p class='cab-descripcion'>Dónde están los establecimientos del territorio y cómo se
caracterizan: matrícula, vulnerabilidad, trayectorias y resultados educativos.
De los 84 establecimientos, 72 tienen coordenadas y aparecen en el mapa.</p>
</div>
<ul class='cab-cifras'>
<li><span class='cifra'>84</span><span class='cifra-etq'>establecimientos</span></li>
<li><span class='cifra'>7</span><span class='cifra-etq'>comunas</span></li>
<li><span class='cifra'>13.397</span><span class='cifra-etq'>matrícula total</span></li>
</ul>
</header>
<p class='guia-uso'>Busca un establecimiento por su nombre o su RBD, o pasa el
cursor sobre un punto para ver un resumen. Haz clic en el punto para abrir su
ficha completa; la tecla Esc la cierra.</p>"""

TRAMOS = ((8, "Hasta 25", 30), (12, "26 – 75", 8), (17, "76 – 200", 9),
          (23, "201 – 500", 18), (30, "501 o más", 7))

def leyenda():
    cats = "".join(
        f"<span class='leyenda-item'><span class='leyenda-color' style='background:{c}'>"
        f"</span><span>{t}</span></span>"
        for c, t in ((RURAL, "Rural (46)"), (URBANO, "Urbano (26)")))
    escala = "".join(
        f"<span class='leyenda-escala'><span class='circulo-caja'>"
        f"<i class='circulo-escala' style='width:{d}px;height:{d}px'></i></span>"
        f"<span class='escala-etq'>{etq} <span class='escala-n'>({n})</span></span></span>"
        for d, etq, n in TRAMOS)
    return ("<div class='leyenda-mapa' role='group' aria-label='Leyenda del mapa'>"
            "<div class='leyenda-titulo'>Ruralidad</div>"
            f"<div class='leyenda-categorias'>{cats}</div>"
            "<div class='leyenda-divisor'></div>"
            "<div class='leyenda-titulo'>Matrícula (alumnos)</div>"
            f"<div class='leyenda-matricula'>{escala}</div></div>")

def etiqueta():
    return (f"<div class='leaflet-tooltip tt-leaflet'><div class='tt' style='--c:{URBANO}'>"
            "<div class='tt-nombre'>Liceo Pelluhue</div>"
            "<div class='tt-datos'>"
            "<div class='tt-dato'><span>Comuna</span><b>Pelluhue</b></div>"
            "<div class='tt-dato'><span>RBD</span><b>3609</b></div>"
            "<div class='tt-dato'><span>Matrícula</span><b class='grande'>972</b></div>"
            f"<div class='tt-dato'><span>Ruralidad</span><b>{cond('Urbano', URBANO)}</b></div>"
            "</div>"
            "<div class='tt-pista'>Haz clic para ver la ficha completa</div>"
            "</div></div>")

def etiqueta_adultos():
    """La misma tarjeta, para un establecimiento de pura nivelación de adultos."""
    return (f"<div class='leaflet-tooltip tt-leaflet'><div class='tt' style='--c:{URBANO}'>"
            "<div class='tt-nombre'>Liceo T-P Mariano Latorre</div>"
            "<div class='tt-adultos'>Educación de adultos</div>"
            "<div class='tt-datos'>"
            "<div class='tt-dato'><span>Comuna</span><b>Curepto</b></div>"
            "<div class='tt-dato'><span>RBD</span><b>3612</b></div>"
            "<div class='tt-dato'><span>Matrícula</span><b class='grande'>236</b></div>"
            f"<div class='tt-dato'><span>Ruralidad</span><b>{cond('Urbano', URBANO)}</b></div>"
            "</div>"
            "<div class='tt-pista'>Haz clic para ver la ficha completa</div>"
            "</div></div>")


BUSCADOR = """<div class='buscador'>
<input type='search' class='buscador-campo' role='combobox' aria-expanded='true'
 placeholder='Buscar establecimiento o RBD' value='pell'
 aria-label='Buscar un establecimiento por nombre o RBD'>
<ul class='buscador-lista' role='listbox'>
<li class='buscador-op resaltado' role='option' aria-selected='true'>
<span class='op-nombre'>Liceo Pelluhue</span>
<span class='op-meta'>Pelluhue · RBD 3609</span></li>
<li class='buscador-op sin-mapa' role='option' aria-selected='false'>
<span class='op-nombre'>Sala Cuna Pelluhue</span>
<span class='op-meta'>Pelluhue · sin ubicación en el mapa</span></li>
</ul></div>"""

SIN_UBICACION = """<details class='sin-ubicacion' open>
<summary>Establecimientos sin ubicación en el mapa (12)</summary>
<div class='su-cuerpo'>
<p>La base no incluye sus coordenadas, por eso no aparecen como puntos.
Tampoco tienen RBD, de modo que no es posible asociarles indicadores
de matrícula, vulnerabilidad, asistencia, rendimiento ni SIMCE.</p>
<table><thead><tr><th scope='col'>Establecimiento</th><th scope='col'>Comuna</th>
<th scope='col'>RBD</th></tr></thead><tbody>
<tr><td>Sala Cuna Pelluhue</td><td>Pelluhue</td><td><span class='sin-info'>Sin información</span></td></tr>
<tr><td>Jardín Infantil Las Dunas</td><td>Chanco</td><td><span class='sin-info'>Sin información</span></td></tr>
</tbody></table></div></details>"""

PIE = """<div class='pie-visor'>
<p><b>Nota.</b> El mapa muestra los 72 establecimientos con coordenadas
disponibles. La matrícula total considera los 72 establecimientos con dato de
matrícula oficial. La llave que une todas las fuentes es el RBD.</p>
<p><b>Fuentes.</b> Base de establecimientos del SLEP Maule Costa;
MINEDUC, Resumen de Matrícula Oficial 2026, Asistencia anual 2025 y
Rendimiento por estudiante 2025; JUNAEB, IVE 2026 e IVM 2026;
Agencia de Calidad de la Educación, SIMCE 2025.</p>
<p>Elaboración: Alonso Cotal, noviembre de 2026.</p>
</div>"""

# Estilos propios de la previsualización. Prefijo pv- para no chocar con visor.css.
PV_CSS = """
body.pv { margin:0; padding:0 }
.pv-wrap { max-width:1120px; margin:0 auto; padding:28px 24px 80px }
.pv-aviso { margin:0 0 28px; padding:14px 16px; background:#fff7e0;
  border:1px solid #e3cf97; font-size:14.5px; line-height:1.5 }
.pv-h { margin:40px 0 12px; padding-bottom:8px; border-bottom:2px solid #0e3a47;
  font-size:13px; font-weight:700; letter-spacing:.1em; text-transform:uppercase;
  color:#0e3a47 }
.pv-sub { margin:0 0 12px; font-size:14px; color:#566870 }
/* Simula el contenedor de Leaflet: posición relativa y el gris del mapa */
.pv-mapa { position:relative; overflow:hidden; background:#e7ecee }
.pv-mapa.pv-chico { height:460px }
.pv-flot { position:absolute; z-index:1200 }
.pv-flot.pv-tt { top:90px; left:140px }
.pv-flot.pv-tt2 { top:90px; left:470px }
.pv-flot.pv-ley { bottom:8px; left:10px }
.pv-escenario { position:relative; overflow:hidden; background:#e7ecee;
  border:1px solid #dadfe1; margin:0 0 28px }
.pv-ancho { width:100%; max-width:980px }
"""


def css_con_fuentes():
    """Lee visor.css y reemplaza cada url("fonts/x.woff2") por un data: URI."""
    css = CSS.read_text(encoding="utf-8")

    def reemplazo(m):
        nombre = m.group(2)
        for carpeta in FUENTES:
            ruta = carpeta / nombre
            if ruta.exists():
                b64 = base64.b64encode(ruta.read_bytes()).decode("ascii")
                return f"url(data:font/woff2;base64,{b64})"
        raise SystemExit(
            f"No se encontró la tipografía «{nombre}» en "
            + " ni en ".join(str(c.relative_to(RAIZ)) for c in FUENTES)
        )

    return re.sub(r'url\((["\']?)fonts/([^"\')]+)\1\)', reemplazo, css)


def main():
    if not CSS.exists():
        raise SystemExit(f"No existe {CSS.relative_to(RAIZ)}")

    escenarios = []
    for fid, titulo, constructor, alto in FIXTURES:
        escenarios.append(
            f"<h2 class='pv-h'>{titulo}</h2>"
            f"<div class='pv-escenario' style='height:{alto}px' id=\"{fid}\">"
            "<aside class='ficha-panel abierta' aria-label='Ficha del establecimiento'>"
            "<button type='button' class='ficha-cerrar' aria-label='Cerrar ficha'>&times;</button>"
            f"<div class='ficha-cuerpo' tabindex='-1'>{constructor()}</div>"
            "</aside></div>"
        )

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Previsualización · Visor SLEP Maule Costa</title>
<style>{css_con_fuentes()}</style>
<style>{PV_CSS}</style>
</head>
<body class="pv">
<div class="pv-wrap">
<p class="pv-aviso"><b>Previsualización de estilos.</b> La arma
<code>tools/previsualizar.py</code> con el <code>assets/visor.css</code> real,
sin pasar por R ni Quarto. No es el visor: el mapa es un rectángulo gris y los
datos son de ejemplo. Sirve para revisar tipografía, bordes, jerarquía y colores.</p>

<h2 class="pv-h">Fuera del mapa — encabezado y guía de uso</h2>
{CABECERA}

<h2 class="pv-h">Dentro del mapa — buscador, etiqueta del cursor y leyenda</h2>
<p class="pv-sub">El rectángulo gris ocupa el lugar del mapa. Las tres piezas están
en su posición real dentro del contenedor.</p>
<div class="marco-mapa pv-ancho">
  <div class="leaflet-container pv-mapa pv-chico">
    {BUSCADOR}
    <div class="pv-flot pv-tt">{etiqueta()}</div>
    <div class="pv-flot pv-tt2">{etiqueta_adultos()}</div>
    <div class="pv-flot pv-ley legend-control leaflet-control">{leyenda()}</div>
  </div>
</div>

<h2 class="pv-h">Fuera del mapa — establecimientos sin ubicación y pie</h2>
{SIN_UBICACION}
{PIE}

{''.join(escenarios)}
</div>
</body>
</html>
"""

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(html, encoding="utf-8")
    print(f"Escrito {SALIDA.relative_to(RAIZ)} — {len(html)/1000:.0f} KB, "
          f"{len(FIXTURES)} fichas de ejemplo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
