# pipelines/ingest

El pipeline convierte PDFs e imágenes, nativos o escaneados, en un JSONL por documento. El JSONL tiene el texto por página, el método de extracción (`native` u `ocr`) y metadatos. Además, el pipeline mide la calidad del OCR (CER) contra un texto de referencia. Se implementó en la change `add-ingest-pipeline` (ver `openspec/changes/add-ingest-pipeline`).

## Requisitos

- Python 3.12 y `uv`. Las dependencias de Python están fijadas en `uv.lock`.
- Para el OCR real, Tesseract 5 con el idioma español:

  ```bash
  sudo apt-get install -y tesseract-ocr tesseract-ocr-spa   # Debian/Ubuntu
  tesseract --list-langs                                    # tiene que listar spa y eng
  ```

  La suite rápida de tests no necesita Tesseract, porque usa motores de OCR falsos.

## Uso

Desde `pipelines/ingest`:

```bash
uv sync

# Generar los corpus ficticios (están versionados: regenerarlos da los mismos bytes)
uv run make-corpus --out ../../data/corpus                                # prueba, semilla 20261124
uv run make-corpus --set validation --out ../../data/corpus-validation    # validación, semilla 20261126

# Ingestar un directorio
uv run ingest ../../data/corpus --out ../../data/processed/ingest

# Aplicar la regla preregistrada de selección del psm a tres reportes del set de validación
uv run python scripts/choose_psm.py --psm3 a.json --psm4 b.json --psm6 c.json
```

La salida queda así:

- `<out>/documents/<doc_id>.jsonl`: una línea por documento, con el modelo `IngestedDocument`. Si concatenás todos los archivos, obtenés el JSONL del corpus completo.
- `<out>/ingest_report.json` y `<out>/ingest_report.md`: los documentos con su estado, el método por página, el CER por documento y por categoría, los tiempos y los errores.

La CLI devuelve `0` si todo se procesó u omitió, `1` si algún documento terminó con error (el resto del lote se procesa igual) y `2` si los argumentos son inválidos.

### Cómo funciona

1. **Formato.** El pipeline acepta `.pdf`, `.png`, `.jpg`/`.jpeg` y `.tif`/`.tiff`. Cualquier otro formato queda como error `unsupported_format`.
2. **Clave de idempotencia.** El `doc_id` es el `sha256` del archivo. La salida guarda además el motor de OCR (`ocr_engine`) y `config_hash`: el sha256 de la configuración efectiva (`PIPELINE_VERSION`, umbrales de detección, dpi, idiomas, psm y motor). Si ya existe `documents/<doc_id>.jsonl` con el mismo `config_hash`, el documento se omite (`skipped`). Si cambia cualquiera de esos valores, se reprocesa y se sobrescribe la salida. El timeout no entra en la huella.
3. **Detección por página.** Una página es nativa si su capa de texto tiene al menos 50 caracteres no blancos y al menos el 90 % de ellos son imprimibles. Si no cumple, la página completa se rasteriza y pasa por OCR. Una página escaneada con un sello de texto corto va a OCR, y el OCR lee el sello junto con la imagen.
4. **Resolución.** El OCR recibe cada página a 300 dpi:
   - Las páginas de PDF se rasterizan a esa resolución.
   - Las imágenes se reescalan según el dpi que declaran, solo si está entre 100 y 600 (72 suele ser el valor por defecto de la aplicación, no el del escáner). Si no declaran un dpi plausible, se asume que ya están a 300. Se aceptan los dpi racionales de TIFF.
   - Ninguna página supera 40 Mpx (`MAX_OCR_PIXELS`). Si haría falta más, se baja la resolución y se le informa al motor el dpi efectivo.
5. **Normalización.** El texto se pasa a NFC y se colapsan los espacios dentro de cada línea, pero se conservan los saltos de línea. El CER se calcula sobre el texto con todos los blancos colapsados.
6. **Errores.** Los errores se registran por documento y no cortan el lote:
   - `unsupported_format`: formato no soportado.
   - `unreadable_file`: PDF corrupto o cifrado, imagen ilegible o demasiado grande para Pillow, o fallo de pymupdf o Pillow.
   - `ocr_failed`: el OCR falló.
   - `invalid_ground_truth`: el texto de referencia existe pero no se puede leer.

   Los errores de programación no se atrapan, para que se vean.

### Archivos renombrados y duplicados

- **Archivo renombrado sin cambios**: tiene el mismo `doc_id`, así que se omite. En el reporte aparece con el nombre nuevo, pero el JSONL conserva el nombre con el que se ingestó (`source`).
- **Dos archivos idénticos en el mismo lote**: comparten el `doc_id`. El primero, en orden alfabético, se procesa; el segundo se omite. Queda un solo JSONL.
- **Archivo editado**: cambia el `doc_id` y genera una salida nueva. La salida del contenido anterior no se borra.

Los tres casos están fijados por tests en `tests/test_idempotency.py`.

### Configuración

Cada valor se toma de una variable de entorno con prefijo `INGEST_` (se lee con `pydantic-settings`) y se puede pisar con un flag de la CLI.

| Variable | Flag | Por defecto | Qué hace |
| --- | --- | --- | --- |
| `INGEST_MIN_NATIVE_CHARS` | `--min-native-chars` | 50 | Mínimo de caracteres no blancos para que la página sea nativa |
| `INGEST_MIN_PRINTABLE_RATIO` | `--min-printable-ratio` | 0.9 | Proporción mínima de caracteres imprimibles para que la página sea nativa |
| `INGEST_OCR_DPI` | `--dpi` | 300 | Resolución a la que se rasteriza la página para el OCR |
| `INGEST_OCR_LANG` | `--lang` | `spa+eng` | Idiomas de Tesseract |
| `INGEST_OCR_PSM` | `--psm` | 3 | Modo de segmentación de página de Tesseract, elegido con la regla preregistrada (ver abajo) |
| `INGEST_OCR_TIMEOUT_S` | (sin flag) | 120 | Timeout por página de OCR, en segundos |

Todas, salvo el timeout, forman parte de `config_hash`.

## Tests

```bash
uv run pytest                  # suite rápida, con OCR falso (corre en CI)
uv run pytest -m integration   # Tesseract real sobre el corpus: umbrales de CER, sello e imagen suelta
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

Hay al menos un test por cada escenario de la spec. Los tests marcados `integration` quedan excluidos por defecto (`addopts = -m 'not integration'`). Los motores falsos están en `tests/fakes.py`:

- `FakeOCREngine` registra el tamaño y el dpi de cada imagen.
- `FailingOCREngine` falla siempre.
- `DirtyTextOCREngine` devuelve texto con la suciedad típica de Tesseract.
- `PixelMeanOCREngine` responde según el contenido de la imagen, para detectar si el pipeline rasteriza la página equivocada o manda una imagen en blanco.

## Corpus ficticios

Todo el contenido es inventado: las personas, los legajos y los montos. Los correos usan el dominio reservado `acme.example`. No hay números de documento, CUIT/CUIL, CBU ni teléfonos, y un test lo verifica con regex (`tests/test_fictitious_data.py`).

### Corpus de prueba (`data/corpus/`, 9,3 MB)

20 documentos de RRHH y políticas internas de "Acme S.A.", una empresa ficticia:

| Categoría | Cantidad | Cómo se genera |
| --- | --- | --- |
| Nativo | 8 | PDF con capa de texto (reportlab) |
| Escaneo limpio | 6 | Página rasterizada a 300 dpi, rotación ≤ 0,5°, ruido gaussiano sigma 10, bajada a 200 dpi, JPEG calidad 85 |
| Escaneo ruidoso | 4 | Igual, con rotación de 1 a 2°, sigma 35 y JPEG calidad 60 |
| Mixto | 2 | Páginas nativas y escaneadas; una página escaneada lleva el sello "RECIBIDO RRHH 02/11/2026" con capa de texto (24 caracteres, 22 no blancos) |

Dos de los escaneos son `.jpg` sueltos y el resto son PDFs. El texto de referencia por página está en `ground_truth/<archivo>.json`, y la semilla, los perfiles y los hashes, en `ground_truth/manifest.json`.

### Set de validación (`data/corpus-validation/`, 3,9 MB)

Son 6 escaneos de una página cada uno, generados con otra semilla y con documentos distintos de los del corpus de prueba:

- 2 documentos a dos columnas;
- 2 formularios con tabla;
- 2 textos corridos.

Tres son escaneos limpios y tres ruidosos. Este set se usa solo para elegir el psm, y el corpus de prueba no interviene en esa decisión. En las páginas a dos columnas, la referencia es la columna izquierda completa y después la derecha.

## Resultados medidos

Todas las corridas están versionadas en [`evals/runs/ingest/`](../../evals/runs/ingest/), y [`REPORT.md`](REPORT.md) tiene el detalle. Se usó Tesseract 5.3.4 con `spa+eng`, en un contenedor de 4 vCPU.

**1. Selección del psm sobre el set de validación** (regla preregistrada en `design.md`; corridas `validation_37a4454_psm*.json`):

| psm | CER medio por página escaneada |
| --- | --- |
| 3 | **0,13 %** (elegido) |
| 4 | 11,17 % |
| 6 | 18,40 % |

psm 4 y 6 mezclan las líneas de los documentos a dos columnas (el boletín pasa de 0,13 % a cerca de 61 %).

**2. Corpus de prueba, corrida única con psm 3** (`corpus_76145f8_psm3.json`):

| Categoría | Documentos | CER medio | CER máximo | Umbral de la spec | Resultado |
| --- | --- | --- | --- | --- | --- |
| Nativo | 8 | 0,00 % | 0,00 % | (sin umbral) | |
| Escaneo limpio | 6 | 4,04 % | 23,81 % | ≤ 2 % | **No cumple** |
| Escaneo ruidoso | 4 | 0,04 % | 0,18 % | ≤ 8 % | Cumple |
| Mixto | 2 | 0,00 % | 0,00 % | (sin umbral) | |

- 35 páginas (20 nativas y 15 con OCR) en 33,3 s, o sea 0,95 s por página, medido en una corrida solo de tiempos (`corpus_76145f8_psm3_tiempos.json`). La corrida registrada tardó 76,5 s porque la máquina estaba cargada, con el mismo CER.
- La reingesta sin cambios omite los 20 documentos en 0,02 s.
- **El escaneo limpio no cumple, por un solo documento con tabla** (`13-formulario-rendicion-gastos.jpg`). psm 3 lee la columna "Importe" después del resto de la página: los caracteres están bien, pero el orden no.
  - psm 4 o 6 lo arreglarían en este corpus (0,07 %, según las corridas reproducidas `corpus_da01914_psm4.json` y `corpus_da01914_psm6.json`), pero el set de validación muestra que rompen los documentos a dos columnas.
  - Siguiendo la decisión 5, el test de integración del umbral limpio queda en rojo y no se ajusta nada más.

## Limitaciones

- **El corpus sintético es más fácil que los escaneos reales.** La única degradación que simula es ruido gaussiano, rotación y JPEG. No hay desenfoque, manchas, sombras, papel con textura, sellos manuscritos ni fotos de celular. El perfil ruidoso dio casi el mismo CER que el limpio (0,04 %). Un perfil más difícil va a una change posterior (decisión 6).
- **Las tablas salen como texto plano.** No se reconstruyen filas ni columnas. En los escaneos, el orden de lectura de una tabla depende del modo de segmentación de Tesseract, y ningún psm único sirve para todos los diseños (ver los resultados).
- **No hay detección de títulos ni de estructura.** La salida conserva los saltos de línea para que `add-rag-core` pueda detectar títulos.
- **El OCR en la nube y los formatos Office, HTML o correo** quedan fuera de alcance (ver `design.md`).
