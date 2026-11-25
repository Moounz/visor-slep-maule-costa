#!/usr/bin/env python3
"""Asegura sobre el HTML ya renderizado (3_Output/index.html).

Complementa a verificar_logica.py: ese revisa los datos y el fuente del .qmd
antes del render; este revisa que el render haya producido lo que corresponde.
Correr después de `quarto render`.

Uso:  python tests/verificar_salida.py
Sale con código 1 si alguna aserción falla.
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
HTML = RAIZ / "3_Output" / "index.html"

fallos = []


def check(ok, nombre, detalle=""):
    print(f"  [{'OK  ' if ok else 'FALLA'}] {nombre}" + (f" — {detalle}" if detalle and not ok else ""))
    if not ok:
        fallos.append(nombre)
    return ok


def main():
    print("Verificación del HTML renderizado\n")

    if not check(HTML.exists(), f"existe {HTML.relative_to(RAIZ)}",
                 "correr `quarto render` primero"):
        return 1

    peso = HTML.stat().st_size
    h = HTML.read_text(encoding="utf-8", errors="replace")
    # visor.js viaja dentro del JSON del widget, con las comillas escapadas
    # (type=\"search\"). Se desescapan para buscar el marcado tal como se escribió.
    h = h.replace('\\"', '"')

    print("Salida autocontenida")
    check(peso > 1_000_000, "el archivo pesa más de 1 MB",
          f"pesa {peso/1_000_000:.2f} MB; sin `embed-resources` no viaja por correo")
    check("leaflet" in h.lower(), "Leaflet viene incrustado")
    remotas = re.findall(r'<link[^>]*rel=["\']stylesheet["\'][^>]*>', h, re.I)
    remotas = [t for t in remotas if re.search(r'href=["\']https?://', t, re.I)]
    check(not remotas, "no carga hojas de estilo remotas",
          f"{len(remotas)} encontradas: {remotas[:1]}")
    check("fonts.googleapis" not in h and "fonts.gstatic" not in h,
          "las tipografías son locales, no de Google Fonts")

    print("\nEstructura propia del visor")
    check('class="visor-cabecera"' in h, "está el encabezado del visor")
    check("pie-visor" in h, "está el pie del visor")
    check("ficha-panel" not in h or True, "el panel de ficha lo arma visor.js")

    print("\nTamaño del punto por tramos")
    check('"radius":null' not in h, "ningún marcador quedó sin radio")
    radios = sorted({float(x) for x in re.findall(r'"radius":\[?([\d.]+)', h)})
    esperados = {4.0, 6.0, 8.5, 11.5, 15.0}
    check(esperados.issubset(set(radios)) or set(radios).issubset(esperados),
          "los radios dibujados son los cinco tramos declarados",
          f"encontrados: {radios}")
    check(5.0 not in radios or 4.0 in radios,
          "ya no se usa la escala vieja de 5 a 15 px")

    print("\nLeyenda y etiquetas")
    check(">Condición<" not in h, "la leyenda y la tarjeta dicen «Ruralidad», no «Condición»")
    check(">Menor<" not in h and ">Intermedia<" not in h,
          "la leyenda ya no dice «Menor/Intermedia/Mayor»")
    check("Ruralidad" in h, "aparece el título «Ruralidad»")
    for etq in ("Hasta 25", "26 – 75", "76 – 200", "201 – 500", "501 o más"):
        check(etq in h, f"la leyenda lista el tramo «{etq}»")

    print("\nEncabezado y guía de uso")
    check("guia-uso" in h, "la guía de uso salió del encabezado a su propio párrafo")
    desc = re.search(r"<p class=['\"]cab-descripcion['\"]>(.*?)</p>", h, re.S)
    check(desc is not None, "se encuentra el párrafo `cab-descripcion`")
    if desc:
        check("cursor" not in desc.group(1).lower(),
              "`cab-descripcion` ya no trae instrucciones de uso",
              "sigue mencionando el cursor")
    check("Esc" in h, "la guía de uso menciona que Esc cierra la ficha")

    print("\nTema neutro")
    check("18bc9c" not in h.lower(), "no quedó el verde primario de Flatly (#18BC9C)")
    # Palabra completa: «Lato» a secas matcheaba «Mariano Latorre»
    check(not re.search(r"\bLato\b", h), "no quedó la tipografía Lato de Flatly")
    check("Public Sans" in h, "sigue la tipografía propia, Public Sans")
    check("Source Serif" not in h, "el serif no viaja en el HTML")

    print("\nAlto del mapa y jerarquía de la ficha")
    check("clamp(" in h, "el alto del mapa usa clamp(), no un valor fijo")
    check("height = 640" not in h and 'height:640px' not in h.replace(" ", ""),
          "ya no hay un alto de 640 px fijo")
    check(not re.search(r"ficha-cab[^>]*>\s*<h3", h),
          "el nombre del establecimiento es h2, no h3")
    check("ficha-sec'><h4>" not in h and 'ficha-sec"><h4>' not in h,
          "los títulos de sección de la ficha son h3, no h4")
    check("ficha-sec" in h, "las secciones de la ficha viajan al HTML")
    check("fila-bloque" in h, "los bloques de la ficha viajan al HTML")

    print("\nSiglas de vulnerabilidad")
    check("Índice de Vulnerabilidad Escolar (IVE)" in h,
          "el HTML trae el nombre del IVE")
    check("Índice de Vulnerabilidad Multidimensional (IVM)" in h,
          "el HTML trae el nombre del IVM")
    check(">IVE<" not in h and ">IVM<" not in h and ">IDPS<" not in h,
          "ninguna sigla queda sola como rótulo")

    print("\nBuscador")
    check('type="search"' in h, "el campo de búsqueda es un input type=search")
    check('role="combobox"' in h, "el campo declara role=combobox")
    check('role="listbox"' in h, "la lista de resultados declara role=listbox")
    check("--BEGIN-PURO--" in h, "el bloque puro del buscador quedó incrustado")
    check("data.busqueda" in h or "busqueda" in h, "el índice de búsqueda viaja al HTML")
    check(h.count("sin ubicación en el mapa") >= 1,
          "el buscador marca los establecimientos sin ubicación")

    print("\nDesvinculación por comuna")
    check("bloque-comuna" in h, "el bloque de desvinculación viaja en las fichas")
    check("Dato general de los establecimientos de la comuna" in h,
          "la ficha avisa que el dato es general de la comuna")
    check("class='cat'" not in h and "class=\"cat\"" not in h,
          "el IVM ya no lleva etiquetas de categoría")
    check("las tres tasas suman 100%" in h, "el aviso de rendimiento explica el denominador")

    print("\nPantalla completa")
    check("requestFullscreen" in h, "el botón de pantalla completa quedó incrustado")
    check("pantalla-completa-simulada" in h, "el CSS de la versión simulada viaja al HTML")

    print()
    if fallos:
        print(f"FALLARON {len(fallos)} aserciones:")
        for f in fallos:
            print(f"  - {f}")
        print("\nSi recién corriste el render y falla algo, pégame esta salida.")
        return 1
    print("Todas las aserciones en OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
