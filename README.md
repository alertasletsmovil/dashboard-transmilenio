# Dashboard de TransMilenio: demanda diaria y origen-destino

Guía paso a paso, de principio a fin, para dejar funcionando el dashboard en GitHub.

**Qué vas a tener al final:** una página web con dos pestañas, que se actualiza sola dos veces al día con los datos abiertos de TRANSMILENIO S.A.

- **Demanda diaria:** validaciones por día, por hora y por empresa operadora, con un filtro por cada columna de los archivos (componente, línea, ruta, estación o parada, perfil, tarifa, tarjeta, etc.).
- **Origen-destino:** los viajes de cada tarjeta reconstruidos en el día y mostrados en un mapa de Bogotá por localidades. Incluye la matriz origen-destino y las parejas estación/paradero más frecuentes, con filtros por día y franja horaria.

**Cuánto cuesta:** nada (datos abiertos de TransMilenio, GitHub Actions y GitHub Pages).
**Tiempo:** unos 20 minutos de tu parte, más una espera de 30 a 60 minutos la primera vez.

---

# EL FLUJO COMPLETO (11 pasos)

## Paso 1. Descomprimir el archivo

1. Descarga `dashboard-transmilenio.zip` y descomprímelo en tu computador (clic derecho → *Extraer todo* en Windows, o doble clic en Mac).
2. Abre la carpeta. Debes ver: `sitio`, `procesar.py`, `origen_destino.py`, `requirements.txt`, `README.md` y una carpeta oculta `.github` (puede que no la veas; está bien, se revisa en el Paso 4).

## Paso 2. Crear el repositorio en GitHub

1. Entra a https://github.com con tu cuenta (la misma del buscador de licitaciones sirve).
2. Clic en el **+** (arriba a la derecha) → **New repository**.
3. *Repository name:* `dashboard-transmilenio`
4. Marca **Public**.
   > GitHub Pages, que es lo que convierte el repositorio en página web, es gratis solo en repositorios públicos. No hay nada privado en él: son datos abiertos y la página solo muestra totales, nunca tarjetas individuales.
5. Clic en **Create repository**.

> **¿Ya habías creado el repositorio con la versión anterior?** No crees otro. Entra al que tienes y sigue con el Paso 3: al subir los archivos nuevos, GitHub reemplaza los viejos.

## Paso 3. Subir los archivos

1. En la página del repositorio, clic en **uploading an existing file** (o **Add file → Upload files**).
2. Selecciona **todo** lo que hay dentro de la carpeta descomprimida (no la carpeta misma, sino su contenido) y arrástralo a la ventana.
3. Espera a que termine de cargar y haz clic en **Commit changes**.

## Paso 4. Revisar que esté la carpeta `.github`

1. En la página principal del repositorio, revisa que aparezcan: `.github`, `sitio`, `origen_destino.py`, `procesar.py`, `requirements.txt` y `README.md`.
2. **Si falta `.github`** (pasa a menudo porque el computador la oculta), créala a mano:
   1. **Add file → Create new file**.
   2. En el nombre escribe exactamente: `.github/workflows/actualizar.yml` (cada `/` crea una carpeta).
   3. En tu computador, abre el archivo `actualizar.yml` del zip con el Bloc de notas (Windows) o TextEdit (Mac). Está en la carpeta `.github/workflows`; si no la ves, activa "mostrar archivos ocultos" o ábrelo desde el propio zip.
   4. Copia todo el texto, pégalo en GitHub y haz clic en **Commit changes**.

## Paso 5. Dar permiso de escritura

1. En el repositorio, ve a **Settings** (arriba).
2. Menú izquierdo: **Actions → General**.
3. Baja hasta **Workflow permissions**, marca **Read and write permissions** y haz clic en **Save**.

## Paso 6. Ejecutar la primera carga de datos

1. Ve a la pestaña **Actions**.
2. Si aparece un botón verde para habilitar los workflows (*I understand my workflows, go ahead and enable them*), haz clic en él.
3. A la izquierda, clic en **Actualizar dashboard TransMilenio**.
4. A la derecha, **Run workflow** → **Run workflow** (deja vacío el cuadro de días).
5. Aparece una ejecución con un círculo amarillo girando. La primera vez trae los **últimos 30 días** y tarda entre **30 y 60 minutos**. Puedes cerrar la página: sigue corriendo sola.
6. Cuando termine debe quedar un ✅ verde. Si queda una ❌ roja, ve a *Problemas frecuentes* al final.

> Si ya habías hecho una primera carga con la versión anterior, esta corrida vuelve a procesar esos días para calcular también el origen-destino. Es normal que tarde lo mismo que la primera vez.

## Paso 7. Revisar que todo se haya calculado bien

1. En **Actions**, abre la ejecución con ✅ → clic en **actualizar** → abre el paso **Descargar y procesar datos de TransMilenio**.
2. Debes ver líneas como estas:
   - `Coordenadas Troncal: 1xx puntos` y `Coordenadas Zonal: 7.xxx puntos`: el mapa tiene las estaciones y paraderos.
   - Por cada día: `Troncal: …`, `Zonal: … validaciones` y `Origen-destino: … tarjetas, … viajes, … con ambos puntos ubicados en el mapa`.
   - Al final: `Listo. Días en el dashboard: 30`.
3. Si ves `AVISO: sin coordenadas para Troncal` o `para Zonal`, el dashboard funciona, pero los viajes de ese componente salen "(sin ubicación)" en el mapa. Copia ese mensaje y avísame.
4. Es normal ver `Dual: todavía no publicado` en algunos días: TransMilenio a veces lo publica tarde o no lo publica.

## Paso 8. Activar la página web (GitHub Pages)

1. **Settings** → menú izquierdo **Pages**.
2. En *Source* elige **Deploy from a branch**.
3. En *Branch* elige **gh-pages** y **/ (root)** → **Save**.
   > Si `gh-pages` no aparece en la lista, es porque el Paso 6 no ha terminado con ✅. Espera y vuelve.
4. Espera 1 o 2 minutos y recarga la página. Arriba aparece: *Your site is live at* `https://TU-USUARIO.github.io/dashboard-transmilenio/`

## Paso 9. Abrir el dashboard y guardarlo

1. Abre el enlace del paso anterior y guárdalo en favoritos.
2. Arriba hay dos pestañas: **Demanda diaria** y **Origen-destino**. La segunda también se abre directo con el enlace terminado en `od.html`.
3. La primera vez tarda unos segundos en cargar (descarga los datos al navegador).

## Paso 10. Usar el dashboard

**Pestaña Demanda diaria**
1. **📅 Fechas:** último día, 7, 30 o 90 días, todo lo disponible, o un rango personalizado.
2. **Filtros (botones de arriba):** uno por cada columna de los archivos. Clic, marca uno o varios valores (hay buscador) y **Aplicar**. El número azul indica cuántos valores elegiste. **Limpiar filtros** los quita todos.
3. **Validaciones por día:** barras por componente (Troncal, Zonal, Dual). Pasa el mouse para ver los números.
4. **Promedio por hora:** curva típica del día. Solo responde a los filtros de componente, empresa, línea y estación; si usas otro filtro, el gráfico lo avisa.
5. **Ranking:** en *Ver por* eliges la columna (empresa, estación, perfil…). **Clic en una barra para filtrar por ella.**
6. **Tabla y Descargar CSV:** el ranking completo, para abrir en Excel.

**Pestaña Origen-destino**
1. **Día:** un día puntual, o el *promedio de los últimos 7 días* o de *días hábiles*.
2. **Franja horaria:** todo el día, madrugada, pico mañana, valle, pico tarde o noche (según la hora en que empieza el viaje).
3. **Componente donde empieza el viaje:** Troncal, Zonal o Dual.
4. **Colorear el mapa por Orígenes / Destinos:** muestra dónde empiezan o dónde terminan los viajes.
5. **Clic en una localidad del mapa** (o en el nombre de una fila de la matriz): aparecen líneas naranjas hacia sus destinos, más gruesas donde hay más viajes, y a la derecha la lista de destinos. Clic de nuevo, o en *Ver todas*, para volver.
6. **Estaciones y paraderos:** muestra los puntos (rojo = estación troncal, azul = paradero zonal; más grande = más viajes). Clic en uno para ver a dónde van sus viajes.
7. **Matriz origen-destino:** filas = localidad donde empieza el viaje; columnas = donde termina. **Descargar matriz (CSV)** para Excel.
8. **Parejas más frecuentes:** de estación/paradero a estación/paradero, también descargables.

## Paso 11. Comprobar que se actualiza sola

1. Desde ahora corre sola todos los días a las **7:17 a. m. y 6:17 p. m.** (hora Colombia). No tienes que hacer nada.
2. Para comprobarlo, en el dashboard mira la línea de arriba: **"Actualizado: fecha y hora"**. También puedes ver las ejecuciones en la pestaña **Actions**.
3. Ten en cuenta que TransMilenio publica los datos de un día al día siguiente, así que el dashboard llega hasta ayer (o anteayer si se demoran).

**¡Listo!** 🎉

---

# Información de apoyo

## Cómo se calcula el origen-destino

TransMilenio solo registra la **entrada** (la validación), no la salida. El destino se estima con el método de *encadenamiento de viajes*, el usual en estudios con datos de tarjeta:

1. Se ordenan las validaciones de cada tarjeta en el día.
2. Si entre dos validaciones pasan **60 minutos o menos**, es un **transbordo** del mismo viaje (por ejemplo, alimentador → troncal).
3. **Origen** = donde empieza el viaje. **Destino** = donde esa tarjeta empieza su siguiente viaje (se supone que vuelve a subir cerca de donde se bajó). Para el último viaje del día, el destino es el origen del primero (el regreso a casa).
4. No se cuentan: las tarjetas con un solo viaje en el día (no tienen destino) ni las de más de 12 validaciones al día (uso atípico). Las validaciones repetidas en el mismo punto en menos de 10 minutos cuentan como una sola (tarjeta compartida).

Es una estimación: el destino real queda "cerca de" el punto de la siguiente subida. Por eso es más confiable a nivel de localidad que de paradero exacto.

**Privacidad.** El número de tarjeta ya viene cifrado en los datos de TransMilenio. Aun así, la página **no publica tarjetas ni viajes individuales**: solo cantidades agregadas, y las parejas origen-destino con menos de 5 viajes se omiten. El recorrido diario de una sola tarjeta podría revelar dónde vive y trabaja una persona, y la página es pública.

**Ubicaciones.** Las coordenadas de estaciones troncales y paraderos zonales se descargan cada semana de los datos abiertos de TransMilenio (ArcGIS Hub). Se cruzan con el código que trae cada validación: `04100` en troncal y la *cenefa* (por ejemplo `178A02`) en zonal. Los viajes en buses **duales** no traen paradero y aparecen como "(sin ubicación)", igual que algún paradero nuevo que todavía no esté en el mapa oficial. El indicador *Viajes ubicados en el mapa* dice qué porcentaje sí se ubicó.

**Mapa.** Localidades oficiales de Bogotá (IDECA, Acuerdo 117 de 2003) sobre un mapa base de OpenStreetMap/CARTO.

## De dónde salen los datos

- **Validaciones diarias:** https://storage.googleapis.com/validaciones_tmsa/validaciones_diarias.html. Es un .zip por día y por componente (Troncal, Zonal, Dual), con una fila por cada vez que alguien pasa la tarjeta.
- **Estaciones troncales y paraderos zonales:** https://datosabiertos-transmilenio.hub.arcgis.com
- No es una "API" de consultas sino descargas diarias. Por eso el programa baja los archivos, los resume y guarda solo el resumen, que es lo que lee el dashboard.

Qué significa cada indicador:
- **Validación:** una entrada registrada con tarjeta (troncal: torniquete; zonal: validador del bus). No cuenta a quienes se colaron.
- **Recaudo nominal:** suma del valor cobrado en cada validación. Transbordos y algunos beneficios aparecen con valor 0.

## Ajustes opcionales (sin programar)

Abre el archivo en GitHub, clic en el lápiz ✏️, cambia el número y clic en **Commit changes**.

En `procesar.py` (sección CONFIGURACIÓN):

| Ajuste | Qué hace | Valor inicial |
|---|---|---|
| `DIAS_PRIMERA_VEZ` | Días que trae la primera vez | 30 |
| `DIAS_A_CONSERVAR` | Días que se guardan en el dashboard | 120 |
| `COLUMNAS_EXCLUIDAS` | Columnas que no se vuelven filtro | tarjeta, dispositivo, vehículo, saldos, fechas técnicas |
| `NOMBRES` | Cómo se llama cada filtro en pantalla | |

En `origen_destino.py` (sección CONFIGURACIÓN):

| Ajuste | Qué hace | Valor inicial |
|---|---|---|
| `MINUTOS_TRANSBORDO` | Tiempo máximo entre validaciones de un mismo viaje | 60 |
| `MIN_VIAJES_PUBLICAR` | Parejas con menos viajes no se publican (privacidad) | 5 |
| `MAX_VALIDACIONES_TARJETA` | Tarjetas con más validaciones al día se descartan | 12 |

- **Traer más días hacia atrás (una sola vez):** Actions → Actualizar dashboard TransMilenio → Run workflow, y en el cuadro escribe los días (por ejemplo `90`).
- **Cambiar la hora de actualización:** en `.github/workflows/actualizar.yml`, las líneas `cron:` (la hora va en UTC, que es la hora Colombia + 5).

## Problemas frecuentes

| Qué pasa | Qué hacer |
|---|---|
| ❌ en Actions con "permission denied" o "403" al publicar | Falta el Paso 5. Hazlo y vuelve a correr el Paso 6. |
| ❌ con "no se encontró ningún archivo" | TransMilenio no publicó o cambió la dirección de los archivos. Mándame el mensaje. |
| ❌ con error de descarga | El portal estaba caído. La siguiente corrida automática lo reintenta; también puedes darle *Run workflow*. |
| No aparece la rama `gh-pages` en el Paso 8 | La primera carga (Paso 6) no ha terminado con ✅. |
| La página dice "No se pudo cargar" | Si es la primera vez, espera el ✅ del Paso 6. El dashboard necesita acceso a `cdn.jsdelivr.net`, `unpkg.com` y `extensions.duckdb.org`; algunas redes de empresa los bloquean, así que prueba desde el celular u otra red. |
| Origen-destino dice "Todavía no hay días con origen-destino" | Espera a que termine una corrida de Actions con la versión nueva (Paso 6). |
| Muchos viajes "(sin ubicación)" en el mapa | Revisa el Paso 7. Si sale "AVISO: sin coordenadas", mándame el mensaje. |
| GitHub avisa que pausó la tarea programada | Pasa en repos públicos tras 60 días sin cambios (el programa intenta evitarlo solo). Ve a Actions y vuelve a habilitarla. |

**¿Cuánto pesa?** Cada día queda resumido en pocos MB. Abrir 7 días descarga unos 10 a 30 MB al navegador; 90 días puede tardar más de un minuto.

## Cómo funciona por dentro (por si alguien pregunta)

- `procesar.py` (Python + DuckDB): descarga los .zip diarios, resume las validaciones por fecha y por todas las columnas útiles (y por hora para empresa, línea y estación), y guarda un archivo Parquet por día.
- `origen_destino.py`: arma los viajes de cada tarjeta, calcula las matrices origen-destino (por localidad y por estación/paradero) y descarga las coordenadas oficiales.
- `sitio/index.html`: la pestaña Demanda diaria. `sitio/od.html` y `sitio/localidades.geojson`: la pestaña Origen-destino y el mapa de localidades. Leen los datos con DuckDB-WASM en el navegador; el mapa usa Leaflet.
- `.github/workflows/actualizar.yml`: corre todo dos veces al día y publica el resultado en la rama `gh-pages`, que GitHub Pages muestra como página web. Esa rama se reescribe en cada corrida para que el repositorio no crezca.
