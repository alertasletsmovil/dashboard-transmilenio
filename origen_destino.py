"""
Matriz origen-destino a partir de las validaciones de cada tarjeta.

Cómo se arma (método de "encadenamiento de viajes", el usual en estudios de
transporte con datos de tarjeta):

  1. Se ordenan las validaciones de cada tarjeta en el día.
  2. Validaciones seguidas en el mismo punto con menos de 10 minutos de
     diferencia se cuentan como una sola (tarjeta prestada / pago de varias
     personas).
  3. Si entre una validación y la siguiente pasan MINUTOS_TRANSBORDO minutos o
     menos, se toma como un transbordo dentro del mismo viaje.
  4. El ORIGEN de cada viaje es el punto de la primera validación del viaje.
  5. El DESTINO de un viaje es el punto donde esa tarjeta empieza su siguiente
     viaje (se supone que la persona vuelve a subir cerca de donde se bajó).
     Para el último viaje del día, el destino es el origen del primer viaje
     (se supone que regresa a donde empezó el día).
  6. Las tarjetas con un solo viaje en el día no tienen destino y no entran.

Privacidad: nunca se publica el número de tarjeta ni viajes individuales. Solo
se publican conteos agregados, y las parejas origen-destino con menos de
MIN_VIAJES_PUBLICAR viajes se omiten.
"""

import json
import os
import time
from datetime import datetime, timedelta

import requests

# ============================ CONFIGURACIÓN ============================

MINUTOS_TRANSBORDO = 60           # tiempo máximo entre validaciones de un mismo viaje
MIN_VIAJES_PUBLICAR = 5           # parejas con menos viajes no se publican (privacidad)
MAX_VALIDACIONES_TARJETA = 12     # tarjetas con más validaciones al día se descartan (uso atípico)
DIAS_REFRESCAR_CATALOGO = 7       # cada cuántos días se vuelven a bajar las coordenadas

# Coordenadas oficiales (Datos Abiertos TRANSMILENIO S.A., ArcGIS Hub). Se prueban en orden.
CATALOGOS = {
    "Troncal": [  # Estaciones Troncales de TRANSMILENIO (campo numero_estacion, ej. 04100)
        "https://opendata.arcgis.com/api/v3/datasets/5365d814bbdd4062a59234eea7d70db7_1/downloads/data?format=geojson&spatialRefId=4326",
        "https://datosabiertos-transmilenio.hub.arcgis.com/api/download/v1/items/5365d814bbdd4062a59234eea7d70db7/geojson?layers=1",
        "https://opendata.arcgis.com/datasets/5365d814bbdd4062a59234eea7d70db7_1.geojson",
        "https://gis.transmilenio.gov.co/arcgis/rest/services/ConsultaSubgerenciaPlanificacionSITP/Consulta_Planificacion_SITP/FeatureServer/2/query?where=1%3D1&outFields=*&outSR=4326&f=geojson",
    ],
    "Zonal": [  # Paraderos Zonales del SITP (campo cenefa, ej. 178A02)
        "https://opendata.arcgis.com/api/v3/datasets/70b111e96b514bdfb36a7eb532d0eb4f_1/downloads/data?format=geojson&spatialRefId=4326",
        "https://datosabiertos-transmilenio.hub.arcgis.com/api/download/v1/items/70b111e96b514bdfb36a7eb532d0eb4f/geojson?layers=1",
        "https://opendata.arcgis.com/datasets/70b111e96b514bdfb36a7eb532d0eb4f_1.geojson",
    ],
}

PERIODOS = [
    (5, "Madrugada (0-5 h)"),
    (9, "Pico mañana (5-9 h)"),
    (16, "Valle (9-16 h)"),
    (20, "Pico tarde (16-20 h)"),
    (24, "Noche (20-24 h)"),
]
TODO_EL_DIA = "Todo el día"
SIN_UBICACION = "(sin ubicación)"
FUERA_BOGOTA = "Fuera de Bogotá"

# ======================================================================

AQUI = os.path.dirname(os.path.abspath(__file__))
RUTA_LOCALIDADES = os.path.join(AQUI, "sitio", "localidades.geojson")


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- catálogo

def _punto_en_poligono(x, y, anillo):
    dentro = False
    j = len(anillo) - 1
    for i in range(len(anillo)):
        xi, yi = anillo[i][0], anillo[i][1]
        xj, yj = anillo[j][0], anillo[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


class Localizador:
    def __init__(self, ruta=RUTA_LOCALIDADES):
        with open(ruta, encoding="utf-8") as f:
            g = json.load(f)
        self.zonas = []
        for feat in g["features"]:
            geom = feat["geometry"]
            polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
            xs = [p[0] for poly in polys for p in poly[0]]
            ys = [p[1] for poly in polys for p in poly[0]]
            self.zonas.append((feat["properties"]["localidad"], polys, (min(xs), min(ys), max(xs), max(ys))))

    def localidad(self, lon, lat):
        for nombre, polys, (x0, y0, x1, y1) in self.zonas:
            if not (x0 <= lon <= x1 and y0 <= lat <= y1):
                continue
            for poly in polys:
                if _punto_en_poligono(lon, lat, poly[0]) and not any(_punto_en_poligono(lon, lat, h) for h in poly[1:]):
                    return nombre
        return FUERA_BOGOTA


def _bajar_geojson(url):
    if url.startswith("file://"):
        with open(url[7:], encoding="utf-8") as f:
            return json.load(f)["features"]
    feats, offset = [], 0
    while True:
        u = url + (f"&resultOffset={offset}&resultRecordCount=2000" if "/query?" in url else "")
        r = requests.get(u, timeout=180)
        r.raise_for_status()
        data = r.json()
        if "features" not in data:
            raise ValueError(f"respuesta sin 'features': {str(data)[:200]}")
        feats += data["features"]
        if "/query?" not in url or not data["features"] or not data.get("exceededTransferLimit", len(data["features"]) >= 2000):
            break
        offset += len(data["features"])
    return feats


def _clave(props, exactas, contiene):
    low = {k.lower(): k for k in props}
    for e in exactas:
        if e in low:
            return low[e]
    for k_low, k in low.items():
        if all(c in k_low for c in contiene):
            return k
    return None


def _normalizar(componente, feats, localizador):
    puntos = {}
    if not feats:
        return puntos
    p0 = feats[0].get("properties") or {}
    if componente == "Troncal":
        k_cod = _clave(p0, ["numero_estacion", "num_est", "numero_est", "cod_est", "codigo_estacion"], ["num", "est"])
        k_nom = _clave(p0, ["nombre_estacion", "nom_est", "nombre"], ["nom"])
    else:
        k_cod = _clave(p0, ["cenefa", "cenefa_paradero"], ["cenefa"])
        k_nom = _clave(p0, ["nombre", "nombre_paradero"], ["nombre"])
    k_lat = _clave(p0, ["latitud", "latitud_estacion", "latitud_paradero", "lat"], ["lat"])
    k_lon = _clave(p0, ["longitud", "longitud_estacion", "longitud_paradero", "lon"], ["lon"])
    if not k_cod:
        raise ValueError(f"no encontré el campo de código en {list(p0)}")
    for f in feats:
        p = f.get("properties") or {}
        cod = str(p.get(k_cod) or "").strip()
        if not cod:
            continue
        if componente == "Troncal" and cod.replace(".0", "").isdigit():
            cod = cod.replace(".0", "").zfill(5)
        lon = lat = None
        g = f.get("geometry") or {}
        if g.get("type") == "Point":
            lon, lat = g["coordinates"][:2]
        elif k_lat and k_lon:
            try:
                lon, lat = float(str(p[k_lon]).replace(",", ".")), float(str(p[k_lat]).replace(",", "."))
            except (TypeError, ValueError):
                pass
        if lon is None or not (-74.5 < lon < -73.8 and 4.2 < lat < 5.0):
            continue
        nombre = str(p.get(k_nom) or cod).strip() if k_nom else cod
        pid = f"{'T' if componente == 'Troncal' else 'Z'}:{cod}"
        puntos[pid] = [nombre, round(lat, 6), round(lon, 6), localizador.localidad(lon, lat), componente]
    return puntos


def preparar_catalogo(carpeta_datos, local_dir=""):
    """Devuelve {id: [nombre, lat, lon, localidad, componente]} y lo guarda en caché."""
    ruta = os.path.join(carpeta_datos, "catalogo_puntos.json")
    previo = {}
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            previo = json.load(f)
        edad = datetime.now() - datetime.fromisoformat(previo.get("actualizado", "2000-01-01T00:00:00"))
        if edad < timedelta(days=DIAS_REFRESCAR_CATALOGO) and not local_dir:
            log(f"Coordenadas: uso las guardadas ({len(previo['puntos']):,} puntos)")
            return previo["puntos"]

    localizador = Localizador()
    puntos = {}
    for componente, urls in CATALOGOS.items():
        if local_dir:
            urls = [f"file://{os.path.abspath(local_dir)}/{componente}.geojson"]
        for url in urls:
            try:
                t0 = time.time()
                nuevos = _normalizar(componente, _bajar_geojson(url), localizador)
                if not nuevos:
                    raise ValueError("no se obtuvo ningún punto con coordenadas")
                puntos.update(nuevos)
                log(f"Coordenadas {componente}: {len(nuevos):,} puntos ({time.time() - t0:.0f} s)")
                break
            except Exception as e:  # noqa: BLE001
                log(f"  no se pudo con {url[:90]}…: {e}")
        else:
            viejos = {k: v for k, v in previo.get("puntos", {}).items() if v[4] == componente}
            log(f"Coordenadas {componente}: uso las guardadas ({len(viejos):,})" if viejos
                else f"AVISO: sin coordenadas para {componente}; sus viajes saldrán '{SIN_UBICACION}'")
            puntos.update(viejos)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump({"actualizado": datetime.now().isoformat(timespec="seconds"), "puntos": puntos}, f, ensure_ascii=False)
    return puntos


# ---------------------------------------------------------------- viajes

def crear_tabla_etapas(con):
    con.execute("""CREATE OR REPLACE TEMP TABLE etapas (
        tarjeta VARCHAR, ts TIMESTAMP, punto VARCHAR, punto_nombre VARCHAR, componente VARCHAR)""")


def guardar_etapas(con, componente, columnas):
    """Guarda (tarjeta, hora, punto) de cada validación del componente."""
    if not {"Numero_Tarjeta", "Fecha_Transaccion", "Estacion_Parada"} <= set(columnas):
        return
    e = 'trim("Estacion_Parada")'
    prefijo = {"Troncal": "T", "Zonal": "Z"}.get(componente, componente)  # Dual: sin coordenadas
    codigo = (f"CASE WHEN strpos({e}, '|') > 0 THEN split_part(split_part({e}, '|', 2), '_', 1) "
              f"ELSE coalesce(nullif(regexp_extract({e}, '^\\(\\s*([^)]*?)\\s*\\)', 1), ''), {e}) END")
    nombre = (f"CASE WHEN strpos({e}, '|') > 0 THEN regexp_replace(split_part({e}, '|', 2), '^[^_]*_', '') "
              f"ELSE regexp_replace({e}, '^\\(\\s*[^)]*\\)\\s*', '') END")
    con.execute(f"""
        INSERT INTO etapas
        SELECT "Numero_Tarjeta", try_cast("Fecha_Transaccion" AS TIMESTAMP),
               '{prefijo}:' || {codigo}, {nombre}, '{componente}'
        FROM crudo
        WHERE "Numero_Tarjeta" IS NOT NULL AND trim("Numero_Tarjeta") <> ''
    """)


def calcular(con, fecha, carpeta_datos, catalogo):
    """Calcula y guarda las matrices origen-destino del día. Devuelve un resumen."""
    n = con.execute("SELECT count(*) FROM etapas").fetchone()[0]
    if not n:
        return None
    t0 = time.time()
    con.execute("CREATE OR REPLACE TEMP TABLE puntos (id VARCHAR, nombre VARCHAR, lat DOUBLE, lon DOUBLE, localidad VARCHAR)")
    if catalogo:
        con.executemany("INSERT INTO puntos VALUES (?, ?, ?, ?, ?)",
                        [(k, v[0], v[1], v[2], v[3]) for k, v in catalogo.items()])
    periodo = "CASE " + " ".join(f"WHEN hour(inicio) < {h} THEN '{p}'" for h, p in PERIODOS) + " END"
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE viajes AS
        WITH validas AS (
            SELECT e.* FROM etapas e
            JOIN (SELECT tarjeta FROM etapas WHERE ts IS NOT NULL GROUP BY 1
                  HAVING count(*) <= {MAX_VALIDACIONES_TARJETA}) t USING (tarjeta)
            WHERE ts IS NOT NULL
        ),
        con_anterior AS (
            SELECT *, lag(ts) OVER w AS ts_ant, lag(punto) OVER w AS punto_ant
            FROM validas WINDOW w AS (PARTITION BY tarjeta ORDER BY ts)
        ),
        sin_repetidas AS (
            SELECT tarjeta, ts, punto, componente FROM con_anterior
            WHERE NOT coalesce(punto = punto_ant AND ts - ts_ant < INTERVAL 10 MINUTE, false)
        ),
        marcadas AS (
            SELECT *, CASE WHEN lag(ts) OVER w IS NULL
                            OR ts - lag(ts) OVER w > INTERVAL {MINUTOS_TRANSBORDO} MINUTE THEN 1 ELSE 0 END AS nuevo
            FROM sin_repetidas WINDOW w AS (PARTITION BY tarjeta ORDER BY ts)
        ),
        numeradas AS (
            SELECT *, sum(nuevo) OVER (PARTITION BY tarjeta ORDER BY ts ROWS UNBOUNDED PRECEDING) AS nv
            FROM marcadas
        ),
        por_viaje AS (
            SELECT tarjeta, nv, arg_min(punto, ts) AS origen, arg_min(componente, ts) AS comp_origen,
                   min(ts) AS inicio, count(*) AS etapas
            FROM numeradas GROUP BY 1, 2
        )
        SELECT origen, comp_origen, inicio, etapas, {periodo} AS periodo,
               CASE WHEN nv = count(*) OVER t THEN first_value(origen) OVER t ELSE lead(origen) OVER t END AS destino,
               count(*) OVER t AS viajes_tarjeta
        FROM por_viaje
        WINDOW t AS (PARTITION BY tarjeta ORDER BY nv ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
    """)
    # nombres de puntos que no estén en el catálogo (se toman de las validaciones)
    con.execute("""
        INSERT INTO puntos
        SELECT punto, arg_max(punto_nombre, ts), NULL, NULL, NULL FROM etapas
        WHERE punto NOT IN (SELECT id FROM puntos) GROUP BY punto
    """)

    sufijo = fecha.strftime("%Y%m%d")
    base = f"""
        SELECT v.*, coalesce(po.localidad, '{SIN_UBICACION}') AS loc_origen,
               coalesce(pd.localidad, '{SIN_UBICACION}') AS loc_destino
        FROM viajes v
        LEFT JOIN puntos po ON po.id = v.origen
        LEFT JOIN puntos pd ON pd.id = v.destino
        WHERE v.viajes_tarjeta >= 2
    """
    con.execute(f"CREATE OR REPLACE TEMP TABLE od_base AS {base}")
    con.execute(f"""
        COPY (
            SELECT DATE '{fecha.isoformat()}' AS fecha, periodo, comp_origen, loc_origen, loc_destino,
                   count(*)::INTEGER AS viajes, count(*) FILTER (WHERE etapas > 1)::INTEGER AS con_transbordo
            FROM od_base GROUP BY ALL HAVING count(*) >= {MIN_VIAJES_PUBLICAR} ORDER BY ALL
        ) TO '{carpeta_datos}/od_loc_{sufijo}.parquet' (FORMAT parquet, COMPRESSION zstd)
    """)
    con.execute(f"""
        COPY (
            SELECT * FROM (
                SELECT DATE '{fecha.isoformat()}' AS fecha, '{TODO_EL_DIA}' AS periodo, origen, destino,
                       count(*)::INTEGER AS viajes
                FROM od_base GROUP BY ALL HAVING count(*) >= {MIN_VIAJES_PUBLICAR}
                UNION ALL
                SELECT DATE '{fecha.isoformat()}', periodo, origen, destino, count(*)::INTEGER
                FROM od_base GROUP BY ALL HAVING count(*) >= {MIN_VIAJES_PUBLICAR}
            ) ORDER BY ALL
        ) TO '{carpeta_datos}/od_pun_{sufijo}.parquet' (FORMAT parquet, COMPRESSION zstd)
    """)
    r = con.execute(f"""
        SELECT (SELECT count(DISTINCT tarjeta) FROM etapas),
               (SELECT count(*) FROM viajes),
               (SELECT count(*) FROM od_base),
               (SELECT count(*) FROM od_base WHERE loc_origen <> '{SIN_UBICACION}' AND loc_destino <> '{SIN_UBICACION}')
    """).fetchone()
    nombres = {k: v for k, v in con.execute(
        "SELECT id, nombre FROM puntos WHERE id IN (SELECT origen FROM od_base UNION SELECT destino FROM od_base)"
    ).fetchall()}
    resumen = {"tarjetas": r[0], "viajes": r[1], "viajes_con_destino": r[2], "viajes_ubicados": r[3]}
    log(f"  Origen-destino: {r[0]:,} tarjetas, {r[1]:,} viajes, {r[2]:,} con destino, "
        f"{r[3]:,} con ambos puntos ubicados en el mapa ({time.time() - t0:.0f} s)")
    return resumen, nombres


def guardar_puntos(carpeta_datos, catalogo, nombres_vistos):
    """puntos.json: lo que el mapa necesita de cada punto que aparece en los datos."""
    ruta = os.path.join(carpeta_datos, "puntos.json")
    puntos = {}
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            puntos = json.load(f)
    for pid, nombre in nombres_vistos.items():
        if pid in catalogo:
            c = catalogo[pid]
            puntos[pid] = {"n": c[0], "lat": c[1], "lon": c[2], "loc": c[3], "c": c[4]}
        elif pid not in puntos:
            puntos[pid] = {"n": nombre or pid, "lat": None, "lon": None, "loc": SIN_UBICACION,
                           "c": {"T": "Troncal", "Z": "Zonal"}.get(pid[:1], pid.split(":")[0])}
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(puntos, f, ensure_ascii=False, separators=(",", ":"))
