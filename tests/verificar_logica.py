#!/usr/bin/env python3
"""Verifica la lógica del visor sin necesidad de R ni Quarto.

Replica, sobre `3_Output/datos/base_consolidada.csv` y sobre el texto de `index.qmd`,
las mismas aserciones que los chunks de control de `index.qmd` corren durante el
render. Existe porque el entorno donde se escriben los cambios no tiene R: así el
ciclo rojo-verde se puede correr acá, y las aserciones de R quedan como guardia
dentro del render.

Uso:  python tests/verificar_logica.py
Sale con código 1 si alguna aserción falla.
"""
import csv
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
QMD = RAIZ / "index.qmd"
BASE = RAIZ / "3_Output" / "datos" / "base_consolidada.csv"
EXTRACTOR = RAIZ / "2_Process" / "00_extraer_fuentes.py"
CSS = RAIZ / "assets" / "visor.css"

fallos = []


def check(ok, nombre, detalle=""):
    print(f"  [{'OK  ' if ok else 'FALLA'}] {nombre}" + (f" — {detalle}" if detalle and not ok else ""))
    if not ok:
        fallos.append(nombre)
    return ok


def num(v):
    v = (v or "").strip().replace(",", ".")
    try:
        return float(v)
    except ValueError:
        return None


def leer_tramos(texto):
    """Extrae la tabla TRAMOS del tribble de index.qmd."""
    m = re.search(r"TRAMOS\s*<-\s*tribble\((.*?)\n\)", texto, re.S)
    if not m:
        return None
    filas = []
    patron = re.compile(
        r"^\s*(\d+)\s*,\s*(\d+|Inf)\s*,\s*\"([^\"]+)\"\s*,\s*([\d.]+)\s*,?\s*(?:#\s*(\d+))?\s*$"
    )
    for linea in m.group(1).splitlines():
        f = patron.match(linea)
        if f:
            filas.append({
                "desde": int(f.group(1)),
                "hasta": float("inf") if f.group(2) == "Inf" else int(f.group(2)),
                "etiqueta": f.group(3),
                "radio": float(f.group(4)),
                "comentario": int(f.group(5)) if f.group(5) else None,
            })
    return filas or None


def niveles_de(celda):
    """Lista de niveles a partir de un campo «Básica; Media H-C»."""
    if not (celda or "").strip():
        return []
    return [x.strip() for x in celda.split(";") if x.strip()]


def verificar_adultos(filas, texto):
    """La educación de adultos no se suma al nivel regular.

    Regresión del caso Liceo Constitución (RBD 3165): la fuente le daba 2
    estudiantes en MAT_ENS_3 (Básica Adultos) y 0 en MAT_ENS_2 (Básica Niños
    y Jóvenes). El extractor sumaba las dos columnas, así que el visor
    afirmaba que el liceo impartía básica. El dato era correcto; la etiqueta,
    no. Estas aserciones fijan la separación.
    """
    print("\nEducación de adultos separada del nivel regular")

    # Guardia sobre el extractor: la suma que causó el error no debe volver
    if EXTRACTOR.exists():
        src = EXTRACTOR.read_text(encoding="utf-8")
        check('d["MAT_ENS_2"] + d["MAT_ENS_3"]' not in src,
              "`mat_basica` no vuelve a sumar básica de adultos (MAT_ENS_3)",
              "00_extraer_fuentes.py suma ENS_2 + ENS_3")
        check('d["MAT_ENS_5"] + d["MAT_ENS_6"]' not in src,
              "`mat_media_hc` no vuelve a sumar media H-C de adultos (MAT_ENS_6)")
        check('d["MAT_ENS_7"] + d["MAT_ENS_8"]' not in src,
              "`mat_media_tp` no vuelve a sumar media T-P de adultos (MAT_ENS_8)")

    con_mat = [r for r in filas if num(r.get("matricula")) is not None]
    check(bool(con_mat), "hay establecimientos con matrícula para verificar")

    # Identidad: niños y jóvenes + adultos = total oficial, fila por fila
    desajuste = []
    for r in con_mat:
        nj, ad, tot = (num(r.get("mat_ninos_jovenes")), num(r.get("mat_adultos")),
                       num(r.get("matricula")))
        if None in (nj, ad, tot) or round(nj + ad) != round(tot):
            desajuste.append(f"RBD {r.get('rbd')} ({nj} + {ad} != {tot})")
    check(not desajuste,
          "niños y jóvenes + adultos = matrícula total, en cada establecimiento",
          "; ".join(desajuste[:4]))

    # El total del territorio sigue siendo el oficial: excluir adultos de las
    # etiquetas no debe haber bajado la matrícula que publica el visor.
    total = round(sum(num(r["matricula"]) for r in con_mat))
    total_nj = round(sum(num(r.get("mat_ninos_jovenes")) or 0 for r in con_mat))
    total_ad = round(sum(num(r.get("mat_adultos")) or 0 for r in con_mat))
    check(total == total_nj + total_ad,
          "el total del territorio incluye las dos modalidades",
          f"{total} != {total_nj} + {total_ad}")
    print(f"    total {total} = {total_nj} niños y jóvenes + {total_ad} adultos")

    # Los chips de nivel se encienden solo con matrícula de niños y jóvenes
    COLS = {"Parvularia": "mat_parvularia", "Básica": "mat_basica",
            "Especial": "mat_especial", "Media H-C": "mat_media_hc",
            "Media T-P": "mat_media_tp"}
    COLS_AD = {"Básica": "mat_basica_adultos", "Media H-C": "mat_media_hc_adultos",
               "Media T-P": "mat_media_tp_adultos"}

    malos = []
    for r in con_mat:
        etiquetados = set(niveles_de(r.get("niveles_oficiales")))
        esperados = {n for n, c in COLS.items() if (num(r.get(c)) or 0) > 0}
        if etiquetados != esperados:
            malos.append(f"RBD {r.get('rbd')}: dice {sorted(etiquetados)}, "
                         f"tiene {sorted(esperados)}")
    check(not malos,
          "`niveles_oficiales` coincide con la matrícula de niños y jóvenes",
          "; ".join(malos[:4]))

    malos_ad = []
    for r in con_mat:
        etiquetados = set(niveles_de(r.get("niveles_adultos")))
        esperados = {n for n, c in COLS_AD.items() if (num(r.get(c)) or 0) > 0}
        if etiquetados != esperados:
            malos_ad.append(f"RBD {r.get('rbd')}")
    check(not malos_ad, "`niveles_adultos` coincide con la matrícula adulta",
          "; ".join(malos_ad[:4]))

    # `solo_adultos` marca exactamente a quien no tiene régimen regular
    malos_solo = []
    for r in con_mat:
        marcado = str(r.get("solo_adultos", "")).strip().upper() in ("TRUE", "VERDADERO", "1")
        esperado = (num(r.get("mat_ninos_jovenes")) or 0) == 0 and (num(r.get("mat_adultos")) or 0) > 0
        if marcado != esperado:
            malos_solo.append(f"RBD {r.get('rbd')}")
    check(not malos_solo, "`solo_adultos` marca a los establecimientos correctos",
          "; ".join(malos_solo[:4]))

    # Regresión puntual: el caso que originó el cambio
    lc = next((r for r in filas if (num(r.get("rbd")) or 0) == 3165), None)
    if check(lc is not None, "el Liceo Constitución (RBD 3165) está en la base"):
        check((num(lc.get("mat_basica")) or 0) == 0,
              "Liceo Constitución: 0 en básica de niños y jóvenes",
              f"tiene {lc.get('mat_basica')}")
        check("Básica" not in niveles_de(lc.get("niveles_oficiales")),
              "Liceo Constitución: ya no aparece impartiendo básica",
              f"niveles_oficiales = {lc.get('niveles_oficiales')!r}")
        check((num(lc.get("mat_basica_adultos")) or 0) == 2,
              "Liceo Constitución: los 2 estudiantes quedan en básica de adultos",
              f"tiene {lc.get('mat_basica_adultos')}")

    # La ficha del visor tiene que mostrar los dos desgloses, sin sumarlos
    check("filas_matricula_adultos" in texto,
          "index.qmd desglosa la matrícula adulta por nivel")
    check("Educación de adultos, por nivel" in texto,
          "index.qmd rotula el bloque de educación de adultos")
    check("marca_adultos" in texto,
          "index.qmd marca los establecimientos con educación de adultos")
    check("no se suma" in texto,
          "index.qmd advierte que la fila de adultos no se suma al desglose")


def verificar_css(css):
    """Aserciones sobre la capa visual (assets/visor.css).

    El CSS no pasa por R, así que se puede verificar en el mismo ciclo
    rojo-verde que el .qmd, sin renderizar.
    """
    print("\nCapa visual · tipografía")
    check("Source Serif" not in css, "el serif salió del CSS")
    check("--serif:" not in css, "la variable --serif ya no se declara")
    check(css.count("@font-face") == 2,
          "quedan dos @font-face, los de Public Sans",
          f"hay {css.count('@font-face')}")
    check("font-size: 17px" in css, "la base del documento es 17 px")
    for gris in ("#7a888e", "#6b7a80", "#77858b", "#8a999f"):
        check(gris not in css, f"el gris {gris} fue reemplazado por --suave")

    print("\nCapa visual · bordes y sombras")
    check("border-radius: 999px" not in css, "no quedan píldoras redondas")
    check("border-radius: 4px" not in css and "border-radius: 6px" not in css,
          "no quedan radios de 4 ni 6 px")
    check("border-radius: 2px" not in css,
          "no queda el radio de 2 px de la leyenda SIMCE")
    check("border-radius: 0 4px 4px 0" not in css,
          "la marca de adultos quedó recta")
    check(css.count("border-radius: 50%") == 3,
          "solo tres círculos: .leyenda-color, .circulo-escala y .cond i",
          f"hay {css.count('border-radius: 50%')}")
    for sel in (".leyenda-color", ".circulo-escala", ".cond i"):
        check(sel in css, f"{sel} sigue declarado")
    check("--sombra:" in css, "hay un token único de sombra")

    print("\nCapa visual · jerarquía de la ficha")
    check("1px dotted" not in css,
          "los separadores punteados pasaron a continuos",
          f"quedan {css.count('1px dotted')}")
    check("font-style: italic" not in css, "«Sin información» ya no va en cursiva")
    check("border-left: 1px solid #e6ecec" in css,
          "las filas del bloque van con sangría y filete vertical")
    check("border-bottom: 2px solid var(--marea)" in css,
          "el título de sección lleva filete de 2 px")
    check(".nivel.off" in css and "dashed" not in css,
          "los niveles no impartidos usan fondo gris, no línea de guiones",
          f"quedan {css.count('dashed')} bordes de guiones")
    check(".num-grande .sin-info" in css,
          "la ausencia no se muestra al tamaño del número destacado")
    check(".visually-hidden" in css,
          "el texto solo para lectores de pantalla no depende del tema de Quarto")

    print("\nCapa visual · encabezado, etiqueta y animaciones")
    check("transform .22s" not in css, "la transición del panel se actualizó")
    check("transform .2s ease-out" in css, "el panel entra en 200 ms ease-out")
    check("opacity .12s" in css, "la etiqueta del cursor aparece con desvanecido")
    check("prefers-reduced-motion" in css, "sigue el respeto por reducir movimiento")
    check(".tt-nombre::before" in css, "la etiqueta lleva el punto de color propio")
    check("font-size: 28px" in css, "el título baja de tamaño en pantallas chicas")
    check("gap: 14px 1.6rem" in css,
          "las tres cifras se reparten con gap y envuelven en pantallas angostas")
    check(".tt-dato > span" in css and ".tt-dato span {" not in css,
          "el rótulo de la etiqueta se estila por hijo directo, no por descendencia",
          "`.tt-dato span` también alcanza al valor y lo encoge")
    check(".74rem" not in css and ".68rem" not in css,
          "la leyenda en pantalla chica usa la misma escala en px que el resto")
    check("font-weight: 500" not in css,
          "no se declara un peso que las tipografías del proyecto no tienen")
    check("background: var(--niebla);\n  border-left: 3px solid var(--arena)" in css,
          "la marca de adultos se distingue del encabezado, ahora que es blanco")


def main():
    print("Verificación de lógica del visor\n")

    if not QMD.exists() or not BASE.exists():
        print(f"  [FALLA] faltan archivos de entrada: {QMD}, {BASE}")
        return 1

    texto = QMD.read_text(encoding="utf-8")
    filas = list(csv.DictReader(BASE.open(encoding="utf-8-sig")))
    en_mapa = [r for r in filas
               if num(r.get("lat")) is not None and num(r.get("lon")) is not None]

    print("Columnas obligatorias")
    m = re.search(r"requeridas\s*<-\s*c\((.*?)\n\)", texto, re.S)
    requeridas = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    check(bool(requeridas), "el vector `requeridas` se puede leer")
    usadas_en_control = re.findall(
        r"prom_lect_4b|tasa_asistencia|tasa_aprobacion", texto)
    check("prom_lect_4b" in requeridas,
          "`prom_lect_4b` está en `requeridas`",
          "el chunk control-calidad la usa pero la validación no la exige")
    faltan = [c for c in requeridas if c not in (filas[0].keys() if filas else [])]
    check(not faltan, "todas las `requeridas` existen en la base",
          f"faltan: {faltan}")

    print("\nTramos de tamaño del punto")
    tramos = leer_tramos(texto)
    if not check(tramos is not None, "`TRAMOS` está definido en index.qmd",
                 "no se encontró el tribble TRAMOS"):
        return 1

    n = len(tramos)
    check(n >= 3, "hay al menos tres tramos", f"hay {n}")
    check(tramos[0]["desde"] == 0, "el primer tramo parte en 0",
          f"parte en {tramos[0]['desde']}")
    check(tramos[-1]["hasta"] == float("inf"), "el último tramo queda abierto")
    check(all(tramos[i + 1]["desde"] == tramos[i]["hasta"] + 1 for i in range(n - 1)),
          "los tramos no dejan huecos ni se solapan")
    check(all(tramos[i + 1]["radio"] > tramos[i]["radio"] for i in range(n - 1)),
          "el radio crece con el tramo")

    check(re.search(r"RADIO_SIN_DATO\s*<-\s*[\d.]+", texto) is not None,
          "`RADIO_SIN_DATO` está definido")

    print("\nCobertura de los tramos sobre la base")
    def tramo_de(mat):
        for t in tramos:
            if t["desde"] <= mat <= t["hasta"]:
                return t
        return None

    sin_mat = [r for r in en_mapa if num(r.get("matricula")) is None]
    con_mat = [r for r in en_mapa if num(r.get("matricula")) is not None]
    asignados = [tramo_de(num(r["matricula"])) for r in con_mat]
    check(all(a is not None for a in asignados),
          "todo establecimiento con matrícula cae en un tramo",
          f"{sum(1 for a in asignados if a is None)} sin tramo")

    conteo = {t["etiqueta"]: 0 for t in tramos}
    for a in asignados:
        if a:
            conteo[a["etiqueta"]] += 1
    check(sum(conteo.values()) + len(sin_mat) == len(en_mapa),
          "los tramos suman los establecimientos del mapa",
          f"{sum(conteo.values())} + {len(sin_mat)} != {len(en_mapa)}")

    print("\n  Reparto medido:")
    for t in tramos:
        c = conteo[t["etiqueta"]]
        marca = ""
        if t["comentario"] is not None and t["comentario"] != c:
            marca = f"  <-- el comentario de index.qmd dice {t['comentario']}"
            fallos.append(f"conteo del tramo «{t['etiqueta']}» desactualizado")
        print(f"    r={t['radio']:>5}px  {t['etiqueta']:<12} {c:>3}{marca}")
    print(f"    {'':>10}  {'sin dato':<12} {len(sin_mat):>3}")

    verificar_adultos(filas, texto)

    print("\nSiglas de vulnerabilidad: primero el nombre")
    check('fila("Índice de Vulnerabilidad Escolar (IVE)"' in texto,
          "la fila del IVE trae el nombre antes de la sigla")
    check("Índice de Vulnerabilidad Multidimensional (IVM), por ciclo" in texto,
          "el bloque del IVM trae el nombre antes de la sigla")
    check("Indicadores de Desarrollo Personal y Social (IDPS)" in texto,
          "la fila del IDPS trae el nombre antes de la sigla")
    check('fila("IVE"' not in texto and 'bloque("IVM por ciclo"' not in texto
          and 'fila("IDPS"' not in texto,
          "no quedan siglas a secas como rótulo")

    print("\nEtiquetas que el mapa no debe seguir mostrando")
    check("Condición" not in texto,
          "«Condición» ya no se usa como etiqueta de ruralidad",
          "aparece en la leyenda, en la tarjeta del cursor o en la ficha")
    check("'Menor'" not in texto and ">Menor<" not in texto,
          "la leyenda ya no dice «Menor/Intermedia/Mayor»")

    if CSS.exists():
        verificar_css(CSS.read_text(encoding="utf-8"))
    else:
        check(False, f"existe {CSS.name}", "no se encontró assets/visor.css")

    print("\nRendimiento: un solo denominador")
    con_rbd = [f for f in filas if (f.get("rbd") or "").strip()]
    malas_suma, malas_base = [], []
    for f in con_rbd:
        ap, rp, rt = num(f.get("tasa_aprobacion")), num(f.get("tasa_reprobacion")), num(f.get("tasa_retiro"))
        if None not in (ap, rp, rt) and abs(ap + rp + rt - 100) > 0.05:
            malas_suma.append(f["establecimiento"])
        n = [num(f.get(c)) for c in ("n_aprobados", "n_reprobados", "n_retirados", "n_base_rendimiento")]
        if None not in n and n[0] + n[1] + n[2] != n[3]:
            malas_base.append(f["establecimiento"])
    check(not malas_suma, "aprobación + reprobación + retiro = 100 %", ", ".join(malas_suma[:5]))
    check(not malas_base, "la base es aprobados + reprobados + retirados", ", ".join(malas_base[:5]))
    ext = EXTRACTOR.read_text(encoding="utf-8")
    check('SIT_FIN_R.eq("Y")' in ext and 'SIT_FIN.eq("Y")' not in ext,
          "el retiro se cuenta con SIT_FIN_R, que separa los traslados")
    check("cerrados" not in ext, "no queda el denominador viejo (aprobados + reprobados)")

    print("\nDesvinculación por comuna")
    por_comuna = {}
    for f in con_rbd:
        por_comuna.setdefault(f["comuna"], set()).add(
            (f.get("desv_anio"), f.get("desv_global_tasa"), f.get("desv_regular_tasa")))
    check(all(len(v) == 1 for v in por_comuna.values()),
          "todos los establecimientos de una comuna llevan el mismo dato")
    check(all(None not in [num(x) for x in next(iter(v))] for v in por_comuna.values()),
          "las cinco comunas tienen tasa global y regular")
    sin_rbd = [f for f in filas if not (f.get("rbd") or "").strip()]
    check(all(not (f.get("desv_global_tasa") or "").strip() for f in sin_rbd),
          "las salas cuna sin RBD no reciben dato (la metodología excluye parvularia)")
    check("bloque_desvinculacion(e)" in texto and "Dato general de los establecimientos de la comuna" in texto,
          "la ficha dice de qué comuna es el dato")
    i_esp = texto.find('fila("Asistencia esperada"')
    i_des = texto.find("bloque_desvinculacion(e)", i_esp)
    i_res = texto.find('"Resultado del año"', i_esp)
    check(-1 < i_esp < i_des < i_res,
          "el bloque va bajo la asistencia esperada y antes del resultado del año")
    i_bd = texto.find("bloque_desvinculacion <- function")
    cuerpo_bd = texto[i_bd:texto.find("\n}\n", i_bd)]
    check("ficha-aviso" not in cuerpo_bd,
          "el bloque de desvinculación no lleva nota al final")
    check("No se matricularon al año siguiente" in cuerpo_bd
          and "No se matricularon o se pasaron a educación de adultos" in cuerpo_bd
          and "estudiantes de la comuna" in cuerpo_bd,
          "cada medida explica en qué se diferencia de la otra")

    print("\nIVM sin etiquetas de categoría")
    check("pastilla(" not in texto and "COLOR_CAT" not in texto,
          "el .qmd ya no arma las etiquetas bajo/medio/alto")
    check(".cat {" not in CSS.read_text(encoding="utf-8"),
          "no queda el estilo .cat en el CSS")

    print("\nPantalla completa")
    js = (RAIZ / "assets" / "visor.js").read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8") if CSS.exists() else ""
    check("requestFullscreen" in js and "webkitRequestFullscreen" in js,
          "usa la API de pantalla completa, con el prefijo de Safari")
    check("pantalla-completa-simulada" in js and "pantalla-completa-simulada" in css,
          "tiene respaldo simulado donde no hay API")
    check("map.invalidateSize()" in js,
          "avisa a Leaflet del cambio de tamaño")
    check('setAttribute("aria-pressed"' in js and 'setAttribute("aria-label"' in js,
          "el botón declara su estado y su nombre accesible")
    check(":fullscreen" in css and ":-webkit-full-screen" in css,
          "el CSS anula el alto fijo del mapa en pantalla completa")
    ini, fin = js.find("--BEGIN-PURO--"), js.find("--END-PURO--")
    check(ini != -1 and "Fullscreen" not in js[ini:fin],
          "la pantalla completa no entra en el bloque puro del buscador")

    print()
    if fallos:
        print(f"FALLARON {len(fallos)} aserciones:")
        for f in fallos:
            print(f"  - {f}")
        return 1
    print("Todas las aserciones en OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
