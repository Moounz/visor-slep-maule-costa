#!/usr/bin/env python3
"""Prueba la lógica del buscador con Node, sin navegador y sin render.

`assets/visor.js` delimita con los comentarios `--BEGIN-PURO--` y `--END-PURO--`
un bloque que no toca el DOM ni Leaflet: la normalización de texto y la fábrica
del filtro. Este script extrae ese bloque, lo corre en Node con los datos reales
de `3_Output/datos/base_consolidada.csv` y asegura el comportamiento.

Se prueba el archivo fuente y no el HTML renderizado porque `index.qmd` lo
incrusta literal (`readLines` + `paste`), así que son el mismo texto, y así las
pruebas corren sin necesitar Quarto.

Uso:  python tests/probar_buscador.py
Sale con código 1 si alguna prueba falla.
"""
import csv
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent
JS = RAIZ / "assets" / "visor.js"
BASE = RAIZ / "3_Output" / "datos" / "base_consolidada.csv"

INICIO = "/* --BEGIN-PURO-- */"
FIN = "/* --END-PURO-- */"

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


def indice():
    """Reproduce el índice de búsqueda que index.qmd pasa a onRender."""
    filas = list(csv.DictReader(BASE.open(encoding="utf-8-sig")))
    items = []
    for r in filas:
        en_mapa = num(r.get("lat")) is not None and num(r.get("lon")) is not None
        rbd = num(r.get("rbd"))
        items.append({
            "nombre": r.get("establecimiento") or "",
            "comuna": r.get("comuna") or "",
            "rbd": "" if rbd is None else str(int(rbd)),
            "idx": "x" if en_mapa else "",
            "enMapa": en_mapa,
        })
    items.sort(key=lambda it: it["nombre"])
    return items


def main():
    print("Pruebas del buscador (Node)\n")

    if not shutil.which("node"):
        print("  [OMITIDO] no hay `node` en esta máquina.")
        print("  Instalar Node.js para correrla, o verificar a mano en la consola")
        print("  del navegador los casos que asegura este script.")
        return 2

    fuente = JS.read_text(encoding="utf-8")
    if not check(INICIO in fuente and FIN in fuente,
                 "visor.js delimita el bloque puro del buscador",
                 f"faltan los marcadores {INICIO} / {FIN}"):
        return 1

    puro = fuente.split(INICIO, 1)[1].split(FIN, 1)[0]
    items = indice()

    # Caso de tildes tomado de los datos, no inventado: se busca la palabra más
    # larga con diacríticos del índice y se consulta su versión sin ellos.
    objetivo, consulta_sin_tilde = None, None
    for it in items:
        for palabra in it["nombre"].split():
            plano = normalizar_py(palabra)
            if len(palabra) >= 6 and plano != palabra.lower():
                objetivo, consulta_sin_tilde = it["nombre"], plano
                break
        if objetivo:
            break

    # Comuna de prueba tomada de los datos: el territorio cambia de comunas
    # según el año y escribirla a mano hace fallar la prueba sin que haya un bug.
    from collections import Counter
    comuna_prueba = Counter(it["comuna"] for it in items if it["comuna"]).most_common(1)
    comuna_prueba = comuna_prueba[0][0] if comuna_prueba else ""
    comuna_q = normalizar_py(comuna_prueba)

    guion = f"""
{puro}
const items = {json.dumps(items, ensure_ascii=False)};
const filtrar = hacerFiltro(items);
const salida = {{
  norm_enie:    normalizar("Peñuelas"),
  norm_mayus:   normalizar({json.dumps(comuna_prueba.upper(), ensure_ascii=False)}),
  norm_nulo:    normalizar(null),
  vacio:        filtrar(""),
  una_letra:    filtrar("e"),
  inexistente:  filtrar("zzzzqqq"),
  escuela:      filtrar("escuela"),
  rbd_28:       filtrar("28"),
  por_comuna:   filtrar({json.dumps(comuna_q, ensure_ascii=False)}),
  sin_tilde:    filtrar({json.dumps(consulta_sin_tilde or "", ensure_ascii=False)}),
  tope:         filtrar("escuela").length,
}};
console.log(JSON.stringify(salida));
"""
    with tempfile.TemporaryDirectory() as d:
        g = pathlib.Path(d) / "probar.js"
        g.write_text(guion, encoding="utf-8")
        p = subprocess.run(["node", str(g)], capture_output=True, text=True)
    if p.returncode != 0:
        check(False, "el bloque puro corre en Node", p.stderr.strip().splitlines()[-1] if p.stderr.strip() else "sin salida")
        return 1
    r = json.loads(p.stdout)
    check(True, "el bloque puro corre en Node")

    print("\nNormalización")
    check(r["norm_enie"] == "penuelas", "normalizar(\"Peñuelas\") -> \"penuelas\"", f'dio "{r["norm_enie"]}"')
    check(r["norm_mayus"] == comuna_q,
          f'normalizar("{comuna_prueba.upper()}") -> "{comuna_q}"', f'dio "{r["norm_mayus"]}"')
    check(r["norm_nulo"] == "", "normalizar(null) -> \"\" sin lanzar", f'dio "{r["norm_nulo"]}"')

    print("\nFiltrado")
    check(r["vacio"] == [], "consulta vacía devuelve lista vacía, no la base completa",
          f'devolvió {len(r["vacio"])}')
    check(r["una_letra"] == [], "una sola letra devuelve lista vacía (umbral de 2)",
          f'devolvió {len(r["una_letra"])}')
    check(r["inexistente"] == [], "una cadena inexistente devuelve lista vacía",
          f'devolvió {len(r["inexistente"])}')
    check(0 < r["tope"] <= 8, "nunca devuelve más de 8 resultados", f'devolvió {r["tope"]}')

    print("\nBúsqueda sin tildes")
    if check(objetivo is not None, "el índice trae algún nombre con diacríticos"):
        hallados = [x["nombre"] for x in r["sin_tilde"]]
        check(objetivo in hallados,
              f'buscar «{consulta_sin_tilde}» encuentra «{objetivo}»',
              f"devolvió {hallados[:3]}")

    print("\nBúsqueda por comuna")
    esperados = sorted(it["nombre"] for it in items
                       if normalizar_py(it["comuna"]) == comuna_q)
    obtenidos = [x for x in r["por_comuna"]]
    if check(bool(esperados),
             f"hay establecimientos en la comuna de prueba ({comuna_prueba})"):
        # El contrato es coincidir por nombre O por comuna, así que un resultado
        # vale si está en la comuna o si trae la consulta en el nombre. Exigir
        # solo la comuna haría fallar la prueba el día que renombren un liceo.
        fuera = [x["nombre"] for x in obtenidos
                 if normalizar_py(x["comuna"]) != comuna_q
                 and comuna_q not in normalizar_py(x["nombre"])]
        check(bool(obtenidos) and not fuera,
              f'buscar «{comuna_q}» solo devuelve coincidencias por comuna o por nombre',
              f"ajenos: {fuera[:3]}")

    print("\nBúsqueda por RBD")
    check(all(str(x["rbd"]).startswith("28") for x in r["rbd_28"]),
          "buscar «28» devuelve solo RBD que empiezan con 28",
          f'devolvió {[x["rbd"] for x in r["rbd_28"]]}')
    reales = [it["rbd"] for it in items if it["rbd"].startswith("28")]
    check(len(r["rbd_28"]) == min(len(reales), 8),
          "encuentra todos los RBD que empiezan con 28 (hasta el tope)",
          f"hay {len(reales)}, devolvió {len(r['rbd_28'])}")

    print("\nOrden de los resultados")
    nom = [normalizar_py(x["nombre"]) for x in r["escuela"]]
    empiezan = [n.startswith("escuela") for n in nom]
    check(empiezan == sorted(empiezan, reverse=True),
          "los que coinciden al inicio del nombre van primero", f"{empiezan}")

    print("\nMarcado de los sin ubicación")
    sin = [it for it in items if not it["enMapa"]]
    check(len(sin) == 12, "el índice trae los 12 establecimientos sin coordenadas",
          f"trae {len(sin)}")
    check(all(it["idx"] == "" for it in sin), "los sin coordenadas no traen idx")

    print()
    if fallos:
        print(f"FALLARON {len(fallos)} pruebas:")
        for f in fallos:
            print(f"  - {f}")
        return 1
    print("Todas las pruebas en OK.")
    return 0


def normalizar_py(t):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", t or "")
                   if not unicodedata.combining(c)).lower().strip()



if __name__ == "__main__":
    sys.exit(main())
