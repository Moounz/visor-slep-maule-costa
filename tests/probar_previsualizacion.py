#!/usr/bin/env python3
"""Asegura que tools/previsualizar.py produjo una previsualización utilizable.

El entorno de desarrollo no tiene R ni Quarto, así que `quarto render` no se
puede correr para revisar un cambio de CSS. tools/previsualizar.py arma una página
con el `assets/visor.css` real y cinco fichas de ejemplo; este script verifica
que esa página sirva como banco de pruebas.

Uso:  python tests/probar_previsualizacion.py
Sale con código 1 si alguna aserción falla.
"""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "3_Output" / "previsualizacion.html"

# Los cinco casos que el foco de revisión del plan exige poder mirar
FIXTURES = ("fx-completo", "fx-sin-datos", "fx-solo-adultos",
            "fx-adultos-mixto", "fx-nombre-largo", "fx-sin-simce")

# Clases que la página debe ejercitar para que el CSS se vea completo
CLASES = ("visor-cabecera", "guia-uso", "tt-leaflet", "leyenda-mapa",
          "ficha-panel", "ficha-cab", "ficha-sec", "fila-bloque",
          "sin-ubicacion", "pie-visor", "marca-adultos", "sin-info",
          "tt-adultos")

fallos = []


def check(ok, nombre, detalle=""):
    print(f"  [{'OK  ' if ok else 'FALLA'}] {nombre}" + (f" — {detalle}" if detalle and not ok else ""))
    if not ok:
        fallos.append(nombre)
    return ok


def main():
    print("Verificación de la previsualización\n")

    if not check(SALIDA.exists(), f"existe {SALIDA.relative_to(RAIZ)}",
                 "correr `python tools/previsualizar.py` primero"):
        return 1

    h = SALIDA.read_text(encoding="utf-8", errors="replace")

    print("Casos de prueba")
    for fx in FIXTURES:
        check(f'id="{fx}"' in h, f"está la ficha de ejemplo «{fx}»")

    print("\nAutonomía de la página")
    check("data:font/woff2;base64," in h, "las tipografías van incrustadas en base64")
    check("fonts.googleapis" not in h and "fonts.gstatic" not in h,
          "no pide tipografías a Google Fonts")
    check('url("fonts/' not in h and "url('fonts/" not in h,
          "no quedó ninguna ruta relativa a fonts/ sin incrustar")

    print("\nCobertura del CSS")
    for clase in CLASES:
        check(clase in h, f"la página ejercita «{clase}»")

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
