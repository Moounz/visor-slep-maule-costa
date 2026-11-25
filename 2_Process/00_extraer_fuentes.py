# -*- coding: utf-8 -*-
"""
00_extraer_fuentes.py — Visor Geográfico SLEP Maule Costa
=========================================================
Extrae, de las fuentes crudas de `1_Input/fuentes/`, solo lo que corresponde a los
establecimientos del SLEP Maule Costa y lo deja agregado por RBD en
`3_Output/datos/intermedias/`.

Es un paso de UNA SOLA CORRIDA por año: lee ~2 GB de bases ministeriales
a nivel de alumno y las reduce a tablas de 72 filas. El visor nunca lee
las fuentes crudas.

Fuentes y llave de unión (por RBD, salvo la desvinculación, por comuna):
  junaeb_2026/IVM-Establecimientos-2026.xlsx       JUNAEB, 4 hojas (un ciclo cada una)
  junaeb_2026/IVE_2026.xlsx                        JUNAEB, encabezado en la fila 7
  asistencia_2025/ASISTENCIA_ANUAL_PUBL_2025.csv   MINEDUC, 1 fila por alumno (1,36 GB)
  rendimiento_2025/20260210_Rendimiento_2025_*.csv MINEDUC, 1 fila por alumno-curso (604 MB)
  simce_2025/{4B,8B,2M}/..._rbd_final.csv          Agencia de Calidad, SIMCE 2025 por RBD
  desvinculacion/OFICIAL-Tasa-Incidencia-*.xlsx    MINEDUC, por COMUNA (no tiene RBD)

Uso:  python 2_Process/00_extraer_fuentes.py
"""
from pathlib import Path
import sys
import unicodedata
import pandas as pd

RAIZ   = Path(__file__).resolve().parent.parent
FUENTE = RAIZ / "1_Input" / "fuentes"
BASE   = RAIZ / "1_Input" / "establecimientos_slep_maule_costa.xlsx"
SALIDA = RAIZ / "3_Output" / "datos" / "intermedias"
SALIDA.mkdir(parents=True, exist_ok=True)

CICLOS = {"Parvularia": "parv", "1º Ciclo Básico": "c1",
          "2º Ciclo Básico": "c2", "Media": "media"}


def log(msg):
    print(msg, flush=True)


def limpiar_nombres(df):
    """Quita BOM y espacios de los nombres de columna."""
    df.columns = [str(c).replace("﻿", "").replace("ï»¿", "").strip()
                  for c in df.columns]
    return df


def leer_csv_grande(ruta, usecols, dtype=None, decimal=".", chunksize=400_000):
    """Lee un CSV ministerial por trozos probando codificaciones."""
    for enc in ("utf-8-sig", "latin-1"):
        try:
            trozos = pd.read_csv(
                ruta, sep=";", usecols=usecols, dtype=dtype, decimal=decimal,
                encoding=enc, chunksize=chunksize, na_values=["NA", "", " "],
                low_memory=False,
            )
            return pd.concat([limpiar_nombres(t) for t in trozos], ignore_index=True)
        except (UnicodeDecodeError, ValueError) as e:
            ultimo = e
    raise RuntimeError(f"No se pudo leer {ruta.name}: {ultimo}")


def rbds_del_slep():
    d = pd.read_excel(BASE)
    r = sorted(d.iloc[:, 0].dropna().astype(int).unique())
    log(f"Base central: {len(d)} establecimientos, {len(r)} con RBD")
    return set(r)


# --------------------------------------------------------------------------- #
# 1. IVM 2026 (JUNAEB) — vulnerabilidad multidimensional por ciclo
# --------------------------------------------------------------------------- #
def extraer_ivm(rbds):
    xl = pd.ExcelFile(FUENTE / "junaeb_2026" / "IVM-Establecimientos-2026.xlsx")
    largo, ancho = [], None
    for hoja, suf in CICLOS.items():
        d = xl.parse(hoja)
        d = d[d["ID_RBD"].isin(rbds)].copy()
        d["ciclo"] = hoja
        largo.append(d[["ID_RBD", "ciclo", "N_MATRÍCULA",
                        "IVM_ESTABLECIMIENTO", "CATEGORIA_IVM"]]
                     .rename(columns={"ID_RBD": "rbd",
                                      "N_MATRÍCULA": "matricula_ivm",
                                      "IVM_ESTABLECIMIENTO": "ivm",
                                      "CATEGORIA_IVM": "categoria_ivm"}))
        # Identificación del establecimiento: la toma el primer ciclo disponible
        ident = (d[["ID_RBD", "DS_TIPO_DEPENDENCIA", "DS_RURALIDAD",
                    "DS_COMUNA_ESTABLE"]]
                 .rename(columns={"ID_RBD": "rbd",
                                  "DS_TIPO_DEPENDENCIA": "dependencia_ivm",
                                  "DS_RURALIDAD": "ruralidad_ivm",
                                  "DS_COMUNA_ESTABLE": "comuna_ivm"}))
        ancho = ident if ancho is None else pd.concat([ancho, ident])
        log(f"  IVM {hoja:<16} {len(d):>3} establecimientos")

    largo = pd.concat(largo, ignore_index=True)

    # Versión ancha: una columna por ciclo
    piv = largo.pivot_table(index="rbd", columns="ciclo",
                            values=["matricula_ivm", "ivm"], aggfunc="first")
    piv.columns = [f"{v}_{CICLOS[c]}" for v, c in piv.columns]
    cat = largo.pivot_table(index="rbd", columns="ciclo",
                            values="categoria_ivm", aggfunc="first")
    cat.columns = [f"categoria_ivm_{CICLOS[c]}" for c in cat.columns]

    ancho = (ancho.drop_duplicates("rbd").set_index("rbd")
             .join(piv).join(cat).reset_index())
    ancho["matricula_ivm_total"] = ancho[[f"matricula_ivm_{s}" for s in CICLOS.values()]].sum(axis=1, min_count=1)
    ancho["tipo_ensenanza_ivm"] = largo.dropna(subset=["matricula_ivm"]).groupby("rbd")["ciclo"].apply(
        lambda s: "; ".join([c.replace("Media", "Enseñanza Media") for c in CICLOS if c in set(s)])
    ).reindex(ancho["rbd"]).values
    ancho.to_csv(SALIDA / "ivm_rbd.csv", index=False, encoding="utf-8")
    return ancho


# --------------------------------------------------------------------------- #
# 2. IVE 2026 (JUNAEB) — vulnerabilidad escolar
# --------------------------------------------------------------------------- #
def extraer_ive(rbds):
    d = pd.read_excel(FUENTE / "junaeb_2026" / "IVE_2026.xlsx",
                      sheet_name="IVE ESTABLECIMIENTO 2026", skiprows=6)
    d = d[d["ID_RBD"].isin(rbds)].copy()
    cols = {
        "ID_RBD": "rbd",
        "PRIORIDAD A (en %)": "ive_prioridad_a",
        "PRIORIDAD B (en %)": "ive_prioridad_b",
        "PRIORIDAD C (en %)": "ive_prioridad_c",
        "GRUPO PRIORITARIO IVE 2026 (en %)": "ive",
        "NO PRIORITARIOS (en %)": "ive_no_prioritarios",
        "TOTAL MATRICULA ENS BÁSICA Y MEDIA REGULAR DIC2025": "matricula_ive_dic2025",
    }
    d = d[list(cols)].rename(columns=cols)
    for c in d.columns.drop("rbd"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d.to_csv(SALIDA / "ive_rbd.csv", index=False, encoding="utf-8")
    log(f"  IVE 2026         {len(d):>3} establecimientos")
    return d


# --------------------------------------------------------------------------- #
# 3. Asistencia anual 2025 (MINEDUC) — nivel alumno -> tasa por RBD
# --------------------------------------------------------------------------- #
def extraer_asistencia(rbds):
    ruta = FUENTE / "asistencia_2025" / "ASISTENCIA_ANUAL_PUBL_2025.csv"
    log(f"  Leyendo {ruta.name} ({ruta.stat().st_size/2**30:.2f} GB) por trozos…")
    d = leer_csv_grande(
        ruta,
        usecols=["RBD", "DIAS_ASISTIDOS_ANUAL", "DIAS_TRABAJADOS_ANUAL",
                 "TASA_ASISTENCIA_ANUAL", "CATEGORIA_ASIS_ANUAL"],
        dtype={"RBD": "Int64", "CATEGORIA_ASIS_ANUAL": "Int64"},
        decimal=",",
    )
    d = d[d["RBD"].isin(rbds)].copy()
    log(f"  Asistencia 2025  {len(d):>5} alumnos en {d.RBD.nunique()} establecimientos")

    # Qué significa cada categoría: se deduce de los datos, no se supone
    ref = (d.dropna(subset=["CATEGORIA_ASIS_ANUAL", "TASA_ASISTENCIA_ANUAL"])
           .groupby("CATEGORIA_ASIS_ANUAL")["TASA_ASISTENCIA_ANUAL"]
           .agg(["min", "max", "size"]).round(4))
    log("  Categorías de asistencia (rango observado de la tasa):\n"
        + ref.to_string().replace("\n", "\n    "))

    # Categorías oficiales (docs/fuentes/ER_Asistencia_anual_PUB.pdf, CATEGORIA_ASIS_ANUAL):
    #   1 Inasistencia crítica    (< 50% de los días)
    #   2 Inasistencia grave      (50% a 84%)
    #   3 Inasistencia reiterada  (85% a 89%)
    #   4 Asistencia esperada     (90% o más)
    g = d.groupby("RBD").agg(
        n_alumnos_asistencia=("TASA_ASISTENCIA_ANUAL", "size"),
        dias_asistidos=("DIAS_ASISTIDOS_ANUAL", "sum"),
        dias_trabajados=("DIAS_TRABAJADOS_ANUAL", "sum"),
        tasa_asistencia_prom=("TASA_ASISTENCIA_ANUAL", "mean"),
    )
    # Tasa del establecimiento: días asistidos sobre días trabajados (ponderada
    # por la permanencia de cada alumno, no promedio simple de tasas).
    g["tasa_asistencia"] = (g.dias_asistidos / g.dias_trabajados * 100).round(2)
    g["tasa_asistencia_prom"] = (g.tasa_asistencia_prom * 100).round(2)

    cat = (d.dropna(subset=["CATEGORIA_ASIS_ANUAL"])
           .assign(uno=1)
           .pivot_table(index="RBD", columns="CATEGORIA_ASIS_ANUAL",
                        values="uno", aggfunc="sum")
           .reindex(columns=[1, 2, 3, 4]).fillna(0))
    cat = cat.div(cat.sum(axis=1), axis=0).mul(100).round(1)
    cat.columns = ["pct_inasistencia_critica", "pct_inasistencia_grave",
                   "pct_inasistencia_reiterada", "pct_asistencia_esperada"]
    # Ausentismo crónico: la definición de política pública, asistir a menos
    # del 85% de los días (categorías 1 y 2 juntas).
    cat["pct_ausentismo_cronico"] = (cat.pct_inasistencia_critica
                                     + cat.pct_inasistencia_grave).round(1)

    g = g.join(cat).reset_index().rename(columns={"RBD": "rbd"})
    g.to_csv(SALIDA / "asistencia_rbd.csv", index=False, encoding="utf-8")
    return g


# --------------------------------------------------------------------------- #
# 4. Rendimiento 2025 (MINEDUC) — nivel alumno -> aprobación/reprobación/retiro
# --------------------------------------------------------------------------- #
def extraer_rendimiento(rbds):
    ruta = FUENTE / "rendimiento_2025" / "20260210_Rendimiento_2025_20260202_WEB.csv"
    log(f"  Leyendo {ruta.name} ({ruta.stat().st_size/2**30:.2f} GB) por trozos…")
    d = leer_csv_grande(
        ruta,
        usecols=["RBD", "PROM_GRAL", "SIT_FIN", "SIT_FIN_R"],
        dtype={"RBD": "Int64", "SIT_FIN": "string", "SIT_FIN_R": "string"},
        decimal=",",
    )
    d = d[d["RBD"].isin(rbds)].copy()
    log(f"  Rendimiento 2025 {len(d):>5} registros en {d.RBD.nunique()} establecimientos")

    # SIT_FIN   : P promovido · R reprobado · Y retirado · en blanco sin información.
    # SIT_FIN_R : desglosa la Y de SIT_FIN en Y (retiro efectivo) y T (traslado:
    #             el alumno se cambió de establecimiento, o de curso dentro del
    #             mismo establecimiento, durante el año).
    # Por eso el retiro se cuenta con SIT_FIN_R: usar SIT_FIN lo sobreestima
    # al sumarle los traslados (en esta base, 778 traslados frente a 278 retiros).
    d["aprobado"]   = d.SIT_FIN.eq("P")
    d["reprobado"]  = d.SIT_FIN.eq("R")
    d["retirado"]   = d.SIT_FIN_R.eq("Y")
    d["trasladado"] = d.SIT_FIN_R.eq("T")
    # El promedio general viene en 0,0 para los retirados y para buena parte de
    # educación de adultos y especial (documentado en la ficha técnica MINEDUC)
    prom = d.assign(PROM_GRAL=d.PROM_GRAL.where(d.PROM_GRAL > 0))

    g = d.groupby("RBD").agg(
        n_matricula_rendimiento=("aprobado", "size"),
        n_aprobados=("aprobado", "sum"),
        n_reprobados=("reprobado", "sum"),
        n_retirados=("retirado", "sum"),
        n_trasladados=("trasladado", "sum"),
    )
    # Las tres tasas comparten denominador: aprobados + reprobados + retirados.
    # Así suman 100 % y la aprobación no se infla al dejar fuera a los retirados
    # (en Mariano Latorre la diferencia era de 70 % a 45 %). Los trasladados
    # quedan fuera porque cierran el año en otro curso o establecimiento; 125 de
    # ellos son cambios de curso dentro del mismo RBD, que contarían dos veces.
    g["n_base_rendimiento"] = g.n_aprobados + g.n_reprobados + g.n_retirados
    base = g.n_base_rendimiento.where(g.n_base_rendimiento > 0)
    g["tasa_aprobacion"]  = (g.n_aprobados  / base * 100).round(2)
    g["tasa_reprobacion"] = (g.n_reprobados / base * 100).round(2)
    g["tasa_retiro"]      = (g.n_retirados  / base * 100).round(2)
    g["promedio_general"] = prom.groupby("RBD").PROM_GRAL.mean().round(2)

    g = g.reset_index().rename(columns={"RBD": "rbd"})
    g.to_csv(SALIDA / "rendimiento_rbd.csv", index=False, encoding="utf-8")
    return g


# --------------------------------------------------------------------------- #
# 5. SIMCE 2025 (Agencia de Calidad) — ya viene por RBD
# --------------------------------------------------------------------------- #
def extraer_simce(rbds):
    grados = {"4B": "4b", "8B": "8b", "2M": "2m"}
    salida = None
    for carpeta, g in grados.items():
        ruta = FUENTE / "simce_2025" / carpeta / f"simce{g}2025_rbd_final.csv"
        d = pd.read_csv(ruta, sep=";", encoding="latin-1", dtype={"rbd": "Int64"},
                        na_values=["", " ", "."], low_memory=False)
        d = d[d["rbd"].isin(rbds)].copy()

        asigs = ["lect", "mate"] + (["hist"] if g == "8b" else [])
        ren = {"cod_grupo": f"gse_{g}"}
        # marca_*: razón por la que la Agencia no reporta el puntaje
        #   1 = 6 o menos estudiantes evaluados · 2 y 3 = resultados no
        #   representativos · 4 = la prueba extendida no evalúa la asignatura
        for a in ("lect", "mate"):
            ren[f"marca_{a}{g}_rbd"] = f"marca_{a}_{g}"
        for a in asigs:
            ren[f"nalu_{a}{g}_rbd"] = f"n_{a}_{g}"
            ren[f"prom_{a}{g}_rbd"] = f"prom_{a}_{g}"
        for a in ("lect", "mate"):
            for std in ("ins", "ele", "ade"):
                ren[f"palu_eda_{std}_{a}{g}_rbd"] = f"pct_{std}_{a}_{g}"
        cols = [c for c in ren if c in d.columns]
        w = d[["rbd"] + cols].rename(columns=ren)
        for c in w.columns.drop("rbd"):
            w[c] = pd.to_numeric(w[c], errors="coerce")
        salida = w if salida is None else salida.merge(w, on="rbd", how="outer")

        log(f"  SIMCE {carpeta}         {len(d):>3} establecimientos")

    # Etiquetas del grupo socioeconómico (glosas de la Agencia de Calidad)
    GSE = {1: "Bajo", 2: "Medio bajo", 3: "Medio", 4: "Medio alto", 5: "Alto"}
    for g in grados.values():
        if f"gse_{g}" in salida.columns:
            salida[f"gse_{g}_etq"] = salida[f"gse_{g}"].map(GSE)

    salida.to_csv(SALIDA / "simce_rbd.csv", index=False, encoding="utf-8")
    return salida


# --------------------------------------------------------------------------- #
# 6. Matrícula oficial 2026 (MINEDUC) — resumen por establecimiento
# --------------------------------------------------------------------------- #
def extraer_matricula(rbds):
    """Matrícula oficial 2026. Columnas MAT_ENS_1..8, según la ficha técnica:
       1 Parvularia · 2 Básica niños · 3 Básica adultos · 4 Especial
       5 Media H-C niños · 6 Media H-C adultos · 7 Media T-P niños · 8 Media T-P adultos

    Decisión: la modalidad de adultos NO se suma al nivel regular. MINEDUC la
    cuenta aparte (ENS_3, 6 y 8) porque es otra cosa: nivelación de estudios
    para personas adultas, no el ciclo escolar de niños y jóvenes. Sumarlas
    hacía que un liceo sin básica apareciera impartiendo básica por tener dos
    adultos nivelando (caso Liceo Constitución, RBD 3165). Cada nivel queda
    con la matrícula de niños y jóvenes, y los adultos en columnas propias.
    """
    ruta = FUENTE / "matricula_2026" / "20261016_Resumen_Matricula_EE_Oficial_2026_20260430.csv"
    if not ruta.exists():
        log("  Matrícula oficial 2026: no está el CSV "
            "(bajarlo del portal de Datos Abiertos MINEDUC). Se omite.")
        return None
    d = pd.read_csv(ruta, sep=",", encoding="utf-8-sig", low_memory=False)
    d = limpiar_nombres(d)
    d = d[d["RBD"].isin(rbds)].copy()
    for c in d.columns:
        if c.startswith(("MAT_", "CUR_")):
            d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0)

    g = pd.DataFrame({
        "rbd": d["RBD"],
        "estado_establecimiento": d["ESTADO_ESTAB"],
        "nombre_oficial": d["NOM_RBD"].astype(str).str.strip(),
        # RURAL_RBD: 0 urbano, 1 rural. Cobertura completa, a diferencia del IVM.
        "ruralidad_oficial": d["RURAL_RBD"].map({0: "Urbano", 1: "Rural"}),
        "matricula_oficial": d["MAT_TOTAL"],
        # Niveles regulares: solo niños y jóvenes
        "mat_parvularia": d["MAT_ENS_1"],
        "mat_basica": d["MAT_ENS_2"],
        "mat_especial": d["MAT_ENS_4"],
        "mat_media_hc": d["MAT_ENS_5"],
        "mat_media_tp": d["MAT_ENS_7"],
        # Educación de adultos, por nivel
        "mat_basica_adultos": d["MAT_ENS_3"],
        "mat_media_hc_adultos": d["MAT_ENS_6"],
        "mat_media_tp_adultos": d["MAT_ENS_8"],
        "mat_hombres": d["MAT_HOM_TOT"],
        "mat_mujeres": d["MAT_MUJ_TOT"],
        "mat_extranjeros": d["MAT_EXT"],
        # Cursos combinados: señal de multigrado, frecuente en escuelas rurales
        "cursos_simples": d["CUR_SIM_TOT"],
        "cursos_combinados": d["CUR_COMB_TOT"],
    }).sort_values("rbd")
    g["mat_media"] = g.mat_media_hc + g.mat_media_tp
    g["mat_media_adultos"] = g.mat_media_hc_adultos + g.mat_media_tp_adultos
    g["mat_adultos"] = g.mat_basica_adultos + g.mat_media_adultos
    g["mat_ninos_jovenes"] = (g.mat_parvularia + g.mat_basica + g.mat_especial
                              + g.mat_media_hc + g.mat_media_tp)

    # Control: niños y jóvenes + adultos tiene que dar el total oficial
    desajuste = g[(g.mat_ninos_jovenes + g.mat_adultos) != g.matricula_oficial]
    if len(desajuste):
        log(f"  ! {len(desajuste)} establecimientos donde los niveles no suman "
            "el total oficial (revisar la fuente):")
        for _, f in desajuste.iterrows():
            log(f"      RBD {f.rbd}: niveles {int(f.mat_ninos_jovenes + f.mat_adultos)} "
                f"vs MAT_TOTAL {int(f.matricula_oficial)}")

    # Niveles que imparte, según matrícula > 0. Dos listas separadas: el
    # régimen regular y la modalidad de adultos nunca se mezclan.
    etiquetas = [("mat_parvularia", "Parvularia"), ("mat_basica", "Básica"),
                 ("mat_especial", "Especial"), ("mat_media_hc", "Media H-C"),
                 ("mat_media_tp", "Media T-P")]
    etiquetas_ad = [("mat_basica_adultos", "Básica"),
                    ("mat_media_hc_adultos", "Media H-C"),
                    ("mat_media_tp_adultos", "Media T-P")]
    g["niveles_oficiales"] = [
        "; ".join(et for col, et in etiquetas if fila[col] > 0) or None
        for _, fila in g.iterrows()
    ]
    g["niveles_adultos"] = [
        "; ".join(et for col, et in etiquetas_ad if fila[col] > 0) or None
        for _, fila in g.iterrows()
    ]
    # Establecimientos cuya matrícula es íntegramente de adultos: se mantienen
    # en el visor, pero marcados, para que nadie los lea como escuela regular.
    g["solo_adultos"] = (g.mat_ninos_jovenes == 0) & (g.mat_adultos > 0)
    g.to_csv(SALIDA / "matricula_rbd.csv", index=False, encoding="utf-8")
    log(f"  Matrícula 2026   {len(g):>3} establecimientos · "
        f"total {int(g.matricula_oficial.sum()):,}".replace(",", "."))
    log(f"  Educación de adultos: {int(g.mat_adultos.sum())} estudiantes en "
        f"{int(g.mat_adultos.gt(0).sum())} establecimientos "
        f"({int(g.solo_adultos.sum())} de ellos, solo adultos)")
    return g


# --------------------------------------------------------------------------- #
# 7. Desvinculación (MINEDUC) — por comuna, no por establecimiento
# --------------------------------------------------------------------------- #
def norm_comuna(s):
    """Mayúsculas sin tildes: «Constitución» y «CONSTITUCION» son la misma."""
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).upper().strip()


def extraer_desvinculacion():
    """Tasa de incidencia de la desvinculación del último año, por comuna.

    El archivo no tiene RBD: trae tablas separadas por dependencia, curso,
    enseñanza, región, provincia y comuna. La hoja de comuna repite tres
    bloques (total, mujeres, hombres); se toma solo el primero, el total.
    El dato es de la comuna completa, todas las dependencias incluidas.
    """
    ruta = FUENTE / "desvinculacion" / "OFICIAL-Tasa-Incidencia-Desvinculacion-2010-2024.xlsx"
    if not ruta.exists():
        log("  Desvinculación: no está el archivo. Se omite.")
        return None
    t = pd.read_excel(ruta, sheet_name="Tasas a nivel de Comuna", header=None)

    # Cabeceras por contenido, no por posición: fila 1 años, fila 2 medida,
    # fila 3 columna. Se ubica el último año y sus dos grupos de tres columnas.
    fila_anio = t.index[t[0].astype(str).str.startswith("Comuna")][0]
    anios = t.iloc[fila_anio].ffill()
    medidas = t.iloc[fila_anio + 1].ffill()
    columnas = t.iloc[fila_anio + 2]
    anio = int(pd.to_numeric(anios, errors="coerce").max())

    def col(medida, prefijo):
        for j in t.columns:
            if (pd.to_numeric(anios[j], errors="coerce") == anio
                    and str(medidas[j]).strip() == medida
                    and str(columnas[j]).startswith(prefijo)):
                return j
        raise RuntimeError(f"Desvinculación: no se encontró «{medida} / {prefijo}» de {anio}")

    cols = {
        "desv_global_n":           col("Global", "Desvinculados"),
        "desv_global_mat_teorica": col("Global", "Matrícula teórica"),
        "desv_global_tasa":        col("Global", "Tasa de incidencia"),
        "desv_regular_n":           col("Sistema regular", "Desvinculados"),
        "desv_regular_mat_teorica": col("Sistema regular", "Matrícula teórica"),
        "desv_regular_tasa":        col("Sistema regular", "Tasa de incidencia"),
    }

    # Primer bloque: desde la fila de datos hasta la primera nota «Fuente:»
    ini = fila_anio + 3
    fin = t.index[(t.index > ini) & t[0].astype(str).str.startswith("Fuente")][0]
    b = t.iloc[ini:fin]
    b = b[b[0].notna()]

    comunas = pd.read_excel(BASE)
    col_comuna = [c for c in comunas.columns if "comuna" in str(c).lower()][0]
    objetivo = {norm_comuna(c) for c in comunas[col_comuna].dropna()}

    out = pd.DataFrame({"comuna_norm": b[0].map(norm_comuna)})
    for nombre, j in cols.items():
        out[nombre] = pd.to_numeric(b[j], errors="coerce")
    out = out[out.comuna_norm.isin(objetivo)].copy()
    for c in ("desv_global_tasa", "desv_regular_tasa"):
        out[c] = (out[c] * 100).round(2)
    out.insert(1, "desv_anio", anio)

    faltan = objetivo - set(out.comuna_norm)
    if faltan:
        sys.exit(f"Desvinculación: no aparecen las comunas {sorted(faltan)}")
    if out.comuna_norm.duplicated().any():
        sys.exit("Desvinculación: hay comunas repetidas en el primer bloque")

    out.to_csv(SALIDA / "desvinculacion_comuna.csv", index=False, encoding="utf-8")
    for _, r in out.iterrows():
        log(f"  {r.comuna_norm:<14} global {r.desv_global_tasa:>5.2f} %   "
            f"regular {r.desv_regular_tasa:>5.2f} %")
    return out


# --------------------------------------------------------------------------- #
def main():
    if not FUENTE.exists():
        sys.exit(f"No se encontró la carpeta de fuentes: {FUENTE}")
    rbds = rbds_del_slep()
    log("\n== IVM 2026 ==");          extraer_ivm(rbds)
    log("\n== IVE 2026 ==");          extraer_ive(rbds)
    log("\n== Asistencia 2025 ==");   extraer_asistencia(rbds)
    log("\n== Rendimiento 2025 ==");  extraer_rendimiento(rbds)
    log("\n== SIMCE 2025 ==");        extraer_simce(rbds)
    log("\n== Matrícula oficial 2026 =="); extraer_matricula(rbds)
    log("\n== Desvinculación (por comuna) =="); extraer_desvinculacion()
    log(f"\nListo. Tablas intermedias en {SALIDA.relative_to(RAIZ)}")
    for f in sorted(SALIDA.glob("*.csv")):
        log(f"  {f.name:<34} {sum(1 for _ in open(f, encoding='utf-8'))-1:>5} filas")


if __name__ == "__main__":
    main()
