"""
Procesador de la demanda diaria de TransMilenio (datos abiertos de TRANSMILENIO S.A.)

Qué hace, en palabras simples:
  1. Mira qué días ya están procesados.
  2. Descarga de los datos abiertos de TransMilenio los archivos diarios de
     validaciones (Troncal, Zonal y Dual) de los días que faltan.
  3. Los resume (cuenta las validaciones por empresa, línea, estación, perfil,
     tarifa, etc.) para que el dashboard cargue rápido.
  4. Guarda el resumen en la carpeta de salida y borra los días más viejos.

No necesitas modificar nada aquí. Si quieres cambiar algo, solo toca la
sección "CONFIGURACIÓN" de abajo.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
import zipfile
from datetime import date, datetime, timedelta, timezone

import duckdb
import requests

import origen_destino as od

# ============================ CONFIGURACIÓN ============================

# Archivos diarios que publica TransMilenio (uno por día y por componente).
# Página pública: https://storage.googleapis.com/validaciones_tmsa/validaciones_diarias.html
FUENTES = {
    "Troncal": "https://storage.googleapis.com/validaciones_tmsa/ValidacionTroncal/validacionTroncal{f}.zip",
    "Zonal":   "https://storage.googleapis.com/validaciones_tmsa/ValidacionZonal/validacionZonal{f}.zip",
    "Dual":    "https://storage.googleapis.com/validaciones_tmsa/ValidacionDual/validacionDual{f}.zip",
}

DIAS_PRIMERA_VEZ = 30    # la primera vez, cuántos días hacia atrás traer
DIAS_A_REVISAR = 10      # en cada corrida, cuántos días recientes revisar por si faltan
DIAS_A_CONSERVAR = 120   # cuántos días guardar en el dashboard (los más viejos se borran)

# Columnas de los archivos que NO se usan como filtro: son identificadores
# personales o de equipos, saldos, o fechas técnicas. Todas las demás columnas
# que traigan los archivos se vuelven filtros automáticamente.
COLUMNAS_EXCLUIDAS = {
    "Numero_Tarjeta", "Dispositivo", "ID_Vehiculo",
    "Saldo_Previo_a_Transaccion", "Saldo_Despues_Transaccion",
    "Valor", "Fecha_Clearing", "Fecha_Transaccion",
    "Hora_Pico_SN",   # en los archivos siempre trae el mismo valor
}

# Columnas que también se usan en el gráfico por hora (deben ser pocas).
COLUMNAS_POR_HORA = ["Operador", "Linea", "Estacion_Parada"]

# Nombres bonitos para mostrar en el dashboard.
NOMBRES = {
    "Componente": "Componente",
    "Operador": "Empresa operadora",
    "Linea": "Línea / zona",
    "Ruta": "Ruta",
    "Estacion_Parada": "Estación o parada",
    "Acceso_Estacion": "Acceso de la estación",
    "Nombre_Perfil": "Perfil del usuario",
    "Tipo_Tarifa": "Tipo de tarifa",
    "Tipo_Tarjeta": "Tipo de tarjeta",
    "Emisor": "Emisor de la tarjeta",
    "Fase": "Fase",
    "Tipo_Vehiculo": "Tipo de vehículo",
    "Day_Group_Type": "Tipo de día",
    "Sistema": "Sistema",
}

# ======================================================================

ZONA_BOGOTA = timezone(timedelta(hours=-5))


def log(msg):
    print(msg, flush=True)


def descargar(url, destino, intentos=3):
    """Descarga un archivo. Devuelve False si TransMilenio aún no lo ha publicado."""
    if url.startswith("file://"):  # modo prueba
        origen = url[len("file://"):]
        if not os.path.exists(origen):
            return False
        shutil.copy(origen, destino)
        return True
    for i in range(1, intentos + 1):
        try:
            with requests.get(url, stream=True, timeout=300) as r:
                if r.status_code in (403, 404):
                    return False
                r.raise_for_status()
                with open(destino, "wb") as f:
                    for bloque in r.iter_content(1 << 20):
                        f.write(bloque)
            if not zipfile.is_zipfile(destino):
                raise IOError("lo descargado no es un .zip válido")
            return True
        except Exception as e:  # noqa: BLE001
            log(f"    intento {i}/{intentos} falló: {e}")
            time.sleep(10 * i)
    raise RuntimeError(f"No se pudo descargar {url}")


def existe(url):
    """Pregunta si un archivo ya está publicado, sin descargarlo."""
    if url.startswith("file://"):
        return os.path.exists(url[len("file://"):])
    try:
        return requests.head(url, timeout=60, allow_redirects=True).status_code == 200
    except requests.RequestException:
        return False


def detectar_encoding(ruta):
    with open(ruta, "rb") as f:
        muestra = f.read(4_000_000)
    try:
        muestra.decode("utf-8", errors="strict")
        return "utf-8"
    except UnicodeDecodeError as e:
        # si el error es solo por un carácter cortado al final de la muestra, es UTF-8
        if e.start > len(muestra) - 4:
            return "utf-8"
        return "latin-1"


def limpiar(col):
    """Convierte '(018) GRAN AMERICAS USME' en 'GRAN AMERICAS USME', etc."""
    c = f'trim(CAST("{col}" AS VARCHAR))'
    if col == "Estacion_Parada":
        # '(53247) 005A12_TM|005A12_Estación Molinos' -> '005A12 Estación Molinos'
        c = (f"CASE WHEN strpos({c}, '|') > 0 "
             f"THEN regexp_replace(split_part({c}, '|', 2), '^([^_]+)_', '\\1 ') "
             f"ELSE regexp_replace({c}, '^\\(\\s*[^)]*\\)\\s*', '') END")
    else:
        c = f"regexp_replace({c}, '^\\(\\s*[^)]*\\)\\s*', '')"
    return f"coalesce(nullif(trim({c}), ''), '(sin dato)')"


def procesar_componente(con, componente, csvs, fecha):
    enc = detectar_encoding(csvs[0])
    lista = ", ".join(f"'{p}'" for p in csvs)
    con.execute(f"""
        CREATE OR REPLACE TEMP VIEW crudo AS
        SELECT * FROM read_csv([{lista}], all_varchar=true, header=true,
                               encoding='{enc}', ignore_errors=true,
                               null_padding=true, union_by_name=true)
    """)
    columnas = [r[0] for r in con.execute("DESCRIBE crudo").fetchall()]
    columnas = [c for c in columnas if not c.startswith("filename")]
    dims = [c for c in columnas if c not in COLUMNAS_EXCLUIDAS]
    hora_dims = [c for c in COLUMNAS_POR_HORA if c in columnas]

    sel_dims = ", ".join(f'{limpiar(c)} AS "{c}"' for c in dims)
    grp = ", ".join(str(i + 1) for i in range(len(dims) + 2))
    valor = "sum(try_cast(replace(\"Valor\", ',', '.') AS DOUBLE))" if "Valor" in columnas else "NULL::DOUBLE"

    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE dia_{componente} AS
        SELECT DATE '{fecha.isoformat()}' AS fecha, '{componente}' AS "Componente",
               {sel_dims},
               count(*)::BIGINT AS validaciones,
               coalesce({valor}, 0)::DOUBLE AS recaudo
        FROM crudo GROUP BY {grp}
    """)

    if "Fecha_Transaccion" in columnas:
        sel_h = ", ".join(f'{limpiar(c)} AS "{c}"' for c in hora_dims)
        sel_h = (sel_h + ",") if sel_h else ""
        grp_h = ", ".join(str(i + 1) for i in range(len(hora_dims) + 3))
        con.execute(f"""
            CREATE OR REPLACE TEMP TABLE hora_{componente} AS
            SELECT DATE '{fecha.isoformat()}' AS fecha, '{componente}' AS "Componente",
                   {sel_h}
                   coalesce(hour(try_cast("Fecha_Transaccion" AS TIMESTAMP)), -1)::TINYINT AS hora,
                   count(*)::BIGINT AS validaciones
            FROM crudo GROUP BY {grp_h}
        """)
    od.guardar_etapas(con, componente, columnas)
    total = con.execute(f"SELECT sum(validaciones) FROM dia_{componente}").fetchone()[0] or 0
    return dims, int(total)


def procesar_dia(fecha, carpeta_datos, trabajo, catalogo):
    """Descarga y resume un día. Devuelve info del día o None si no hay archivos aún."""
    con = duckdb.connect()
    con.execute("SET memory_limit='5GB'")
    con.execute(f"SET temp_directory='{trabajo}/duck_tmp'")
    con.execute("SET preserve_insertion_order=false")
    od.crear_tabla_etapas(con)
    cargados, totales, todas_dims = [], {}, []
    for componente, plantilla in FUENTES.items():
        url = plantilla.format(f=fecha.strftime("%Y%m%d"))
        zpath = os.path.join(trabajo, f"{componente}.zip")
        t0 = time.time()
        if not descargar(url, zpath):
            log(f"  {componente}: todavía no publicado")
            continue
        carpeta_csv = os.path.join(trabajo, componente)
        shutil.rmtree(carpeta_csv, ignore_errors=True)
        with zipfile.ZipFile(zpath) as zf:
            nombres = [n for n in zf.namelist() if n.lower().endswith((".csv", ".txt"))]
            zf.extractall(carpeta_csv, members=nombres)
        os.remove(zpath)
        csvs = [os.path.join(carpeta_csv, n) for n in nombres]
        if not csvs:
            log(f"  {componente}: el zip no trae CSV, se omite")
            continue
        dims, total = procesar_componente(con, componente, csvs, fecha)
        shutil.rmtree(carpeta_csv, ignore_errors=True)
        cargados.append(componente)
        totales[componente] = total
        todas_dims += [d for d in dims if d not in todas_dims]
        log(f"  {componente}: {total:,} validaciones ({time.time() - t0:.0f} s)")

    if not cargados:
        con.close()
        return None

    sufijo = fecha.strftime("%Y%m%d")
    union = " UNION ALL BY NAME ".join(f"SELECT * FROM dia_{c}" for c in cargados)
    cols = ['"Componente"'] + [f'coalesce("{d}", \'(no aplica)\') AS "{d}"' for d in todas_dims]
    con.execute(f"""
        COPY (SELECT fecha, {", ".join(cols)}, validaciones, recaudo FROM ({union})
              ORDER BY ALL)
        TO '{carpeta_datos}/dia_{sufijo}.parquet' (FORMAT parquet, COMPRESSION zstd)
    """)
    tablas_hora = [c for c in cargados
                   if con.execute(f"SELECT count(*) FROM duckdb_tables() WHERE table_name='hora_{c}'").fetchone()[0]]
    if tablas_hora:
        union_h = " UNION ALL BY NAME ".join(f"SELECT * FROM hora_{c}" for c in tablas_hora)
        hdims = [d for d in COLUMNAS_POR_HORA if d in todas_dims]
        cols_h = ['"Componente"'] + [f'coalesce("{d}", \'(no aplica)\') AS "{d}"' for d in hdims]
        con.execute(f"""
            COPY (SELECT fecha, {", ".join(cols_h)}, hora, validaciones FROM ({union_h})
                  ORDER BY ALL)
            TO '{carpeta_datos}/hora_{sufijo}.parquet' (FORMAT parquet, COMPRESSION zstd)
        """)
    resumen_od = None
    try:
        res = od.calcular(con, fecha, carpeta_datos, catalogo)
        if res:
            resumen_od, nombres = res
            od.guardar_puntos(carpeta_datos, catalogo, nombres)
    except Exception as e:  # noqa: BLE001
        log(f"  AVISO: no se pudo calcular el origen-destino: {e}")
    con.close()
    return {"fecha": fecha.isoformat(), "componentes": cargados, "totales": totales,
            "validaciones": sum(totales.values()), "dimensiones": todas_dims, "od": resumen_od}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--salida", default="publicado", help="carpeta del sitio publicado")
    ap.add_argument("--dias", type=int, default=0, help="forzar revisar N días hacia atrás")
    ap.add_argument("--fuentes-locales", default="", help="(pruebas) carpeta con zips locales")
    ap.add_argument("--catalogo-local", default="", help="(pruebas) carpeta con Troncal/Zonal.geojson")
    args = ap.parse_args()

    if args.fuentes_locales:  # modo prueba: lee zips de una carpeta local
        for k in FUENTES:
            FUENTES[k] = "file://" + os.path.abspath(args.fuentes_locales) + f"/validacion{k}{{f}}.zip"

    carpeta_datos = os.path.join(args.salida, "datos")
    os.makedirs(carpeta_datos, exist_ok=True)
    ruta_indice = os.path.join(carpeta_datos, "indice.json")
    indice = {"dias": []}
    if os.path.exists(ruta_indice):
        with open(ruta_indice, encoding="utf-8") as f:
            indice = json.load(f)
    por_fecha = {d["fecha"]: d for d in indice.get("dias", [])}

    hoy = datetime.now(ZONA_BOGOTA).date()
    n = args.dias or (DIAS_A_REVISAR if por_fecha else DIAS_PRIMERA_VEZ)
    candidatos = [hoy - timedelta(days=i) for i in range(1, n + 1)]
    # días ya guardados que se procesaron antes de existir el origen-destino
    candidatos += [date.fromisoformat(f) for f, info in por_fecha.items()
                   if "od" not in info and date.fromisoformat(f) not in candidatos]
    pendientes = []
    for d in candidatos:
        info = por_fecha.get(d.isoformat())
        if not info or "od" not in info:   # nuevo, o procesado antes de existir el origen-destino
            pendientes.append(d)
            continue
        faltan = [c for c in FUENTES if c not in info["componentes"]]
        # si a un día reciente le faltaba un componente, revisar si ya lo publicaron
        if faltan and (hoy - d).days <= 5 and any(existe(FUENTES[c].format(f=d.strftime("%Y%m%d"))) for c in faltan):
            pendientes.append(d)

    log(f"Días por revisar: {len(pendientes)}")
    catalogo = od.preparar_catalogo(carpeta_datos, args.catalogo_local) if pendientes else {}
    with tempfile.TemporaryDirectory() as trabajo:
        os.makedirs(f"{trabajo}/duck_tmp", exist_ok=True)
        for d in sorted(pendientes):
            log(f"{d}:")
            try:
                info = procesar_dia(d, carpeta_datos, trabajo, catalogo)
            except Exception as e:  # noqa: BLE001
                log(f"  ERROR procesando {d}: {e}")
                continue
            if info:
                anterior = por_fecha.get(d.isoformat())
                if anterior and len(anterior["componentes"]) > len(info["componentes"]):
                    log("  se conserva la versión anterior (tenía más componentes)")
                    continue
                por_fecha[d.isoformat()] = info

    # borrar días viejos
    limite = hoy - timedelta(days=DIAS_A_CONSERVAR)
    for f in list(por_fecha):
        if date.fromisoformat(f) < limite:
            del por_fecha[f]
    validos = {f"{p}_{f.replace('-', '')}.parquet" for f in por_fecha for p in ("dia", "hora", "od_loc", "od_pun")}
    for archivo in os.listdir(carpeta_datos):
        if archivo.endswith(".parquet") and archivo not in validos:
            os.remove(os.path.join(carpeta_datos, archivo))

    dims = []
    for info in por_fecha.values():
        dims += [d for d in info.get("dimensiones", []) if d not in dims]
    orden = list(NOMBRES)  # primero las del diccionario NOMBRES (empresa, línea, estación…), luego las nuevas
    dims.sort(key=lambda d: (orden.index(d) if d in orden else len(orden), d))
    indice = {
        "actualizado": datetime.now(ZONA_BOGOTA).strftime("%Y-%m-%d %H:%M"),
        "fuente": "Datos abiertos TRANSMILENIO S.A. - validaciones diarias",
        "dias": [por_fecha[k] for k in sorted(por_fecha)],
        "dimensiones": [{"columna": "Componente", "nombre": NOMBRES["Componente"]}]
                       + [{"columna": d, "nombre": NOMBRES.get(d, d.replace("_", " "))} for d in dims],
        "columnas_por_hora": ["Componente"] + COLUMNAS_POR_HORA,
        "origen_destino": {
            "periodos": [p for _, p in od.PERIODOS],
            "todo_el_dia": od.TODO_EL_DIA,
            "minutos_transbordo": od.MINUTOS_TRANSBORDO,
            "min_viajes_publicar": od.MIN_VIAJES_PUBLICAR,
        },
    }
    with open(ruta_indice, "w", encoding="utf-8") as f:
        json.dump(indice, f, ensure_ascii=False, indent=1)
    log(f"Listo. Días en el dashboard: {len(por_fecha)}")
    if not por_fecha:
        log("Aviso: no se encontró ningún archivo. Revisa que TransMilenio siga publicando los datos.")
        sys.exit(1)


if __name__ == "__main__":
    main()
