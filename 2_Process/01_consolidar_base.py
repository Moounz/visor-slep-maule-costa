# -*- coding: utf-8 -*-
"""
01_consolidar_base.py — Visor Geográfico SLEP Maule Costa
=========================================================
Une la base central de establecimientos con las tablas intermedias que dejó
`00_extraer_fuentes.py` y produce la base única que lee el visor:

    3_Output/datos/base_consolidada.xlsx   hoja "Establecimientos" + hoja "Diccionario"
    3_Output/datos/base_consolidada.csv    misma tabla, para control de versiones

La base central (1_Input) trae solo identificación: RBD, nombre, comuna y
coordenadas. Todo indicador viene de una fuente, nunca copiado a mano en ella.

Reglas de la unión:
  · La llave es el RBD. Los 12 establecimientos sin RBD (salas cuna) se
    conservan con su identificación y quedan sin indicadores.
  · La matrícula principal es la oficial 2026 (MINEDUC). La del IVM se
    conserva como respaldo en `matricula_ivm_total`.
  · La educación de adultos no se suma a los niveles regulares: `mat_basica`,
    `mat_media_hc` y `mat_media_tp` cuentan solo niños y jóvenes, y la
    modalidad de adultos vive en `mat_*_adultos`. El total `matricula` sigue
    siendo el oficial e incluye ambas. Ver la hoja "Diccionario".
  · La ruralidad principal es la del registro oficial de matrícula, que cubre
    los 72 RBD; el IVM solo cubre 68. `ruralidad_fuente` deja la huella.
  · Las columnas se validan por nombre, no por posición.

Uso:  python 2_Process/01_consolidar_base.py
"""
from pathlib import Path
import sys
import unicodedata
import pandas as pd

RAIZ   = Path(__file__).resolve().parent.parent
BASE   = RAIZ / "1_Input" / "establecimientos_slep_maule_costa.xlsx"
INTER  = RAIZ / "3_Output" / "datos" / "intermedias"
SALIDA = RAIZ / "3_Output" / "datos"
SALIDA.mkdir(parents=True, exist_ok=True)

# Nombre normalizado de la columna de origen -> nombre interno
ESPERADAS = {
    "rbd": "rbd",
    "establecimiento": "establecimiento",
    "comuna": "comuna",
    "coordenadas latitud longitud": "coordenadas",
}
# Ruralidad, matrícula, tipo de enseñanza e IVM ya no están en la base central:
# eran copias del archivo del IVM y se toman de él (ivm_rbd.csv), para que una
# actualización del IVM no deje valores viejos escritos a mano.


def norm(s):
    """Minúsculas, sin tildes ni signos: para comparar títulos de columna."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return " ".join("".join(c if c.isalnum() else " " for c in s).split())


def leer_base():
    d = pd.read_excel(BASE)
    halladas = {norm(c): c for c in d.columns}
    faltan = [e for e in ESPERADAS if e not in halladas]
    if faltan:
        sys.exit("La base central no tiene las columnas esperadas.\n"
                 f"  Faltan: {faltan}\n"
                 f"  Hay: {list(halladas)}")
    d = d.rename(columns={halladas[k]: v for k, v in ESPERADAS.items()})
    d = d[list(ESPERADAS.values())]

    # Coordenadas: "lat, lon" en un solo campo. Se separan acá, no al renderizar.
    par = d["coordenadas"].astype(str).str.extract(
        r"(-?\d+[.,]?\d*)\s*,\s*(-?\d+[.,]?\d*)")
    d["lat"] = pd.to_numeric(par[0].str.replace(",", ".", regex=False), errors="coerce")
    d["lon"] = pd.to_numeric(par[1].str.replace(",", ".", regex=False), errors="coerce")
    d = d.drop(columns="coordenadas")
    d["rbd"] = pd.to_numeric(d["rbd"], errors="coerce").astype("Int64")
    print(f"Base central: {len(d)} establecimientos · {d.rbd.notna().sum()} con RBD · "
          f"{d.lat.notna().sum()} con coordenadas")
    return d


def leer_intermedia(nombre):
    f = INTER / nombre
    if not f.exists():
        print(f"  ! falta {nombre}: se omite (correr 00_extraer_fuentes.py)")
        return None
    d = pd.read_csv(f, encoding="utf-8")
    d["rbd"] = pd.to_numeric(d["rbd"], errors="coerce").astype("Int64")
    return d


def main():
    d = leer_base()

    mat  = leer_intermedia("matricula_rbd.csv")
    ivm  = leer_intermedia("ivm_rbd.csv")
    ive  = leer_intermedia("ive_rbd.csv")
    asis = leer_intermedia("asistencia_rbd.csv")
    rend = leer_intermedia("rendimiento_rbd.csv")
    sim  = leer_intermedia("simce_rbd.csv")

    # IVM: aporta los índices por ciclo, el tipo de enseñanza y la ruralidad y
    # matrícula de respaldo. La comuna se descarta: manda la de la base central.
    if ivm is None:
        sys.exit("Falta ivm_rbd.csv: correr 2_Process/00_extraer_fuentes.py")
    ivm = ivm.drop(columns=["comuna_ivm"], errors="ignore").rename(
        columns={"ruralidad_ivm": "ruralidad_ivm_base"})

    for tabla in (mat, ivm, ive, asis, rend, sim):
        if tabla is not None:
            d = d.merge(tabla, on="rbd", how="left")

    # ---- Desvinculación: por COMUNA, no por establecimiento -----------------
    # El archivo de MINEDUC no tiene RBD. Cada establecimiento recibe el dato de
    # su comuna, que incluye a todas las dependencias (no solo al SLEP). Solo a
    # los que tienen RBD: la metodología excluye parvularia, y las salas cuna
    # sin RBD son justamente las de parvularia.
    f_desv = INTER / "desvinculacion_comuna.csv"
    if f_desv.exists():
        desv = pd.read_csv(f_desv, encoding="utf-8")
        clave = d["comuna"].map(lambda s: "".join(
            c for c in unicodedata.normalize("NFKD", str(s))
            if not unicodedata.combining(c)).upper().strip())
        d = d.assign(comuna_norm=clave).merge(desv, on="comuna_norm", how="left")
        d.loc[d.rbd.isna(), list(desv.columns.drop("comuna_norm"))] = pd.NA
        d = d.drop(columns="comuna_norm")
        sin = d[d.rbd.notna() & d.desv_global_tasa.isna()]
        if len(sin):
            sys.exit(f"Desvinculación: sin dato para las comunas {sorted(sin.comuna.unique())}")
    else:
        print("  ! falta desvinculacion_comuna.csv: se omite (correr 00_extraer_fuentes.py)")

    # ---- Ruralidad: oficial primero, IVM como relleno ----------------------
    d["ruralidad"] = d.get("ruralidad_oficial")
    d["ruralidad_fuente"] = d["ruralidad"].notna().map(
        {True: "Matrícula oficial 2026", False: None})
    faltante = d["ruralidad"].isna() & d["ruralidad_ivm_base"].notna()
    d.loc[faltante, "ruralidad"] = d.loc[faltante, "ruralidad_ivm_base"]
    d.loc[faltante, "ruralidad_fuente"] = "IVM 2026"

    discrepan = d[d.ruralidad_oficial.notna() & d.ruralidad_ivm_base.notna()
                  & (d.ruralidad_oficial != d.ruralidad_ivm_base)]
    if len(discrepan):
        print(f"\n  Aviso: {len(discrepan)} establecimientos con ruralidad distinta "
              "entre matrícula oficial e IVM (manda la oficial):")
        for _, f in discrepan.iterrows():
            print(f"    RBD {f.rbd} {f.establecimiento[:38]:<38} "
                  f"oficial={f.ruralidad_oficial} · IVM={f.ruralidad_ivm_base}")

    # ---- Matrícula: oficial como principal --------------------------------
    d["matricula"] = d["matricula_oficial"] if "matricula_oficial" in d else d["matricula_ivm_total"]
    d["matricula_fuente"] = d["matricula"].notna().map(
        {True: "Matrícula oficial 2026", False: None})

    # ---- Orden final de columnas ------------------------------------------
    orden = [
        "rbd", "establecimiento", "nombre_oficial", "comuna", "lat", "lon",
        "ruralidad", "ruralidad_fuente", "dependencia_ivm",
        "estado_establecimiento", "niveles_oficiales", "tipo_ensenanza_ivm",
        "cursos_simples", "cursos_combinados",
        "matricula", "matricula_fuente",
        "mat_ninos_jovenes", "mat_parvularia", "mat_basica",
        "mat_especial", "mat_media_hc", "mat_media_tp", "mat_media",
        "mat_adultos", "mat_basica_adultos", "mat_media_hc_adultos",
        "mat_media_tp_adultos", "mat_media_adultos",
        "niveles_adultos", "solo_adultos",
        "mat_hombres", "mat_mujeres", "mat_extranjeros",
        "matricula_ivm_total",
        "ive", "ive_prioridad_a", "ive_prioridad_b", "ive_prioridad_c",
        "ive_no_prioritarios", "matricula_ive_dic2025",
        "ivm_parv", "ivm_c1", "ivm_c2", "ivm_media",
        "categoria_ivm_parv", "categoria_ivm_c1", "categoria_ivm_c2",
        "categoria_ivm_media",
        "tasa_asistencia", "tasa_asistencia_prom", "pct_ausentismo_cronico",
        "pct_inasistencia_critica", "pct_inasistencia_grave",
        "pct_inasistencia_reiterada", "pct_asistencia_esperada",
        "n_alumnos_asistencia",
        "tasa_aprobacion", "tasa_reprobacion", "tasa_retiro",
        "promedio_general", "n_matricula_rendimiento", "n_base_rendimiento",
        "n_aprobados", "n_reprobados", "n_retirados", "n_trasladados",
        "desv_anio", "desv_global_tasa", "desv_global_n", "desv_global_mat_teorica",
        "desv_regular_tasa", "desv_regular_n", "desv_regular_mat_teorica",
        "gse_4b", "gse_4b_etq", "n_lect_4b", "prom_lect_4b", "marca_lect_4b",
        "pct_ins_lect_4b", "pct_ade_lect_4b",
        "n_mate_4b", "prom_mate_4b", "marca_mate_4b", "pct_ins_mate_4b", "pct_ade_mate_4b",
        "gse_8b", "gse_8b_etq", "n_lect_8b", "prom_lect_8b", "marca_lect_8b",
        "pct_ins_lect_8b", "pct_ade_lect_8b",
        "n_mate_8b", "prom_mate_8b", "marca_mate_8b", "pct_ins_mate_8b", "pct_ade_mate_8b",
        "n_hist_8b", "prom_hist_8b",
        "gse_2m", "gse_2m_etq", "n_lect_2m", "prom_lect_2m", "marca_lect_2m",
        "pct_ins_lect_2m", "pct_ade_lect_2m",
        "n_mate_2m", "prom_mate_2m", "marca_mate_2m", "pct_ins_mate_2m", "pct_ade_mate_2m",
    ]
    orden = [c for c in orden if c in d.columns]
    sobran = [c for c in d.columns if c not in orden
              and c not in ("ruralidad_oficial", "ruralidad_ivm_base",
                            "matricula_ivm_base", "matricula_oficial",
                            "dias_asistidos", "dias_trabajados")
              and not c.startswith(("matricula_ivm_", "pct_ele_"))]
    d = d[orden + sobran].sort_values(["comuna", "establecimiento"])

    # ---- Diccionario de variables -----------------------------------------
    FUENTES = {
        "identificacion": "Base del SLEP Maule Costa (1_Input)",
        "matricula": "Resumen de Matrícula Oficial 2026, MINEDUC",
        "ive": "IVE 2026, JUNAEB",
        "ivm": "IVM Establecimientos 2026, JUNAEB",
        "asistencia": "Asistencia anual 2025, MINEDUC",
        "rendimiento": "Rendimiento por estudiante 2025, MINEDUC",
        "simce": "SIMCE 2025, Agencia de Calidad de la Educación",
        "desvinculacion": "Tasa de incidencia de la desvinculación 2010-2024, "
                          "MINEDUC (hoja por comuna)",
    }
    def fuente_de(c):
        if c in ("rbd", "establecimiento", "comuna", "lat", "lon"): return FUENTES["identificacion"]
        if c.startswith(("mat", "cursos", "nombre_oficial", "niveles_oficiales",
                         "estado_", "ruralidad")): return FUENTES["matricula"]
        if c.startswith("ive") or c == "matricula_ive_dic2025": return FUENTES["ive"]
        if c.startswith(("ivm", "categoria_ivm", "tipo_ensenanza", "dependencia")): return FUENTES["ivm"]
        if c.startswith(("tasa_asistencia", "pct_inasistencia", "pct_asistencia",
                         "pct_ausentismo", "n_alumnos")): return FUENTES["asistencia"]
        if c.startswith(("tasa_aprob", "tasa_reprob", "tasa_retiro", "promedio_general",
                         "n_matricula_rend", "n_base_rend", "n_aprob", "n_reprob",
                         "n_retir", "n_trasl")): return FUENTES["rendimiento"]
        if c.startswith("desv_"): return FUENTES["desvinculacion"]
        if c.endswith(("_4b", "_8b", "_2m")): return FUENTES["simce"]
        return "—"

    # Definición explícita donde la distinción niños/adultos puede engañar.
    # El resto de las variables queda sin definición: se documenta lo que de
    # verdad se presta a confusión, no se rellena por completitud.
    DEFINICIONES = {
        "matricula": "Matrícula total oficial 2026. Incluye niños y jóvenes "
                     "más educación de adultos.",
        "mat_ninos_jovenes": "Matrícula de niños y jóvenes: suma de parvularia, "
                             "básica, especial y media. Excluye adultos.",
        "mat_parvularia": "Educación Parvularia (MAT_ENS_1).",
        "mat_basica": "Enseñanza Básica Niños y Jóvenes (MAT_ENS_2). "
                      "No incluye básica de adultos.",
        "mat_especial": "Educación Especial (MAT_ENS_4).",
        "mat_media_hc": "Enseñanza Media H-C Niños y Jóvenes (MAT_ENS_5). "
                        "No incluye media H-C de adultos.",
        "mat_media_tp": "Enseñanza Media T-P Niños y Jóvenes (MAT_ENS_7). "
                        "No incluye media T-P de adultos.",
        "mat_media": "Media H-C más Media T-P, solo niños y jóvenes.",
        "mat_basica_adultos": "Enseñanza Básica Adultos (MAT_ENS_3).",
        "mat_media_hc_adultos": "Enseñanza Media H-C Adultos (MAT_ENS_6).",
        "mat_media_tp_adultos": "Enseñanza Media T-P Adultos (MAT_ENS_8).",
        "mat_media_adultos": "Media H-C más Media T-P, solo adultos.",
        "mat_adultos": "Educación de adultos en todos los niveles "
                       "(MAT_ENS_3 + 6 + 8).",
        "niveles_oficiales": "Niveles que imparte a niños y jóvenes, según "
                             "matrícula mayor que cero.",
        "niveles_adultos": "Niveles que imparte en modalidad adultos, según "
                           "matrícula mayor que cero.",
        "solo_adultos": "Verdadero si toda su matrícula es de adultos.",
        "tasa_asistencia": "Días asistidos sobre días trabajados, 2025. "
                           "Calculada sobre todos los estudiantes, adultos incluidos.",
        "tasa_aprobacion": "Aprobados sobre aprobados + reprobados + retirados "
                           "(n_base_rendimiento), 2025. Adultos incluidos.",
        "tasa_reprobacion": "Reprobados sobre n_base_rendimiento, 2025.",
        "tasa_retiro": "Retirados (SIT_FIN_R = Y) sobre n_base_rendimiento, "
                       "2025. Los traslados no son retiros ni entran a la base.",
        "n_base_rendimiento": "Aprobados + reprobados + retirados: denominador "
                              "común de las tres tasas, que suman 100 %.",
        "n_matricula_rendimiento": "Registros de rendimiento 2025, traslados "
                                   "incluidos. Un alumno trasladado puede tener dos.",
        "desv_anio": "Año de la desvinculación (desvinculados de ese año que "
                     "no aparecen matriculados el siguiente).",
        "desv_global_tasa": "Tasa de incidencia global (%) de la COMUNA del "
                            "establecimiento, todas las dependencias. No es "
                            "un dato del establecimiento.",
        "desv_regular_tasa": "Tasa de incidencia del sistema regular (%) de la "
                             "COMUNA: cuenta también a quienes pasaron a "
                             "educación de adultos.",
    }

    dic = pd.DataFrame({
        "variable": d.columns,
        "definicion": [DEFINICIONES.get(c, "") for c in d.columns],
        "fuente": [fuente_de(c) for c in d.columns],
        "con_dato": [int(d[c].notna().sum()) for c in d.columns],
        "cobertura_de_72": [f"{d[c].notna().sum()/72:.0%}" for c in d.columns],
        "tipo": [str(d[c].dtype) for c in d.columns],
    })

    with pd.ExcelWriter(SALIDA / "base_consolidada.xlsx", engine="openpyxl") as w:
        d.to_excel(w, sheet_name="Establecimientos", index=False)
        dic.to_excel(w, sheet_name="Diccionario", index=False)
    d.to_csv(SALIDA / "base_consolidada.csv", index=False, encoding="utf-8")

    print(f"\nBase consolidada: {len(d)} filas × {len(d.columns)} columnas")
    print(f"  {SALIDA.relative_to(RAIZ)}/base_consolidada.xlsx")
    print("\nCobertura por bloque (sobre los 72 con RBD):")
    if "mat_adultos" in d:
        ad = d["mat_adultos"].fillna(0)
        print(f"\nEducación de adultos: {int(ad.sum())} estudiantes · "
              f"{int(ad.gt(0).sum())} establecimientos · "
              f"{int((d['solo_adultos'] == True).sum())} solo adultos")
        print(f"  Matrícula total {int(d['matricula'].fillna(0).sum()):,}".replace(",", ".")
              + f" · niños y jóvenes {int(d['mat_ninos_jovenes'].fillna(0).sum()):,}".replace(",", "."))
    for etq, col in [("Matrícula oficial", "matricula"), ("IVE", "ive"),
                     ("IVM 1º ciclo", "ivm_c1"), ("Asistencia", "tasa_asistencia"),
                     ("Aprobación", "tasa_aprobacion"), ("SIMCE 4º básico", "prom_lect_4b"),
                     ("SIMCE 8º básico", "prom_lect_8b"), ("SIMCE 2º medio", "prom_lect_2m")]:
        if col in d:
            n = int(d[col].notna().sum())
            print(f"  {etq:<18} {n:>3}/72  {'█'*round(n/72*28)}")
    return d


if __name__ == "__main__":
    main()
