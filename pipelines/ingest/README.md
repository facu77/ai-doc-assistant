# pipelines/ingest

El pipeline convierte PDFs e imágenes, nativos o escaneados, en un JSONL por documento. El JSONL tiene el texto por página, el método de extracción (`native` u `ocr`) y metadatos. Además, el pipeline mide la calidad del OCR (CER) contra un texto de referencia. Se implementó en la change `add-ingest-pipeline` (ver `openspec/changes/add-ingest-pipeline`).

## Requisitos

- Python 3.12 y `uv`. Las dependencias de Python están fijadas en `uv.lock`.
- Para el OCR real, Tesseract 5 con el idioma español:

  ```bash
  sudo apt-get install -y tesseract-ocr tesseract-ocr-spa   # Debian/Ubuntu
  tesseract --list-langs                                    # tiene que listar spa y eng
  ```

  La suite rápida de tests no necesita Tesseract, porque usa un motor de OCR falso.

## Uso

Desde `pipelines/ingest`:

```bash
uv sync

# Generar el corpus ficticio (ya está versionado: regenerarlo da los mismos bytes)
uv run make-corpus --out ../../data/corpus            # semilla por defecto: 20261124

# Ingestar un directorio
uv run ingest ../../data/corpus --out ../../data/processed/ingest
```

La salida queda así:

- `<out>/documents/<doc_id>.jsonl`: una línea por documento, con el modelo `IngestedDocument`. Si concatenás todos los archivos, obtenés el JSONL del corpus completo.
- `<out>/ingest_report.json` y `<out>/ingest_report.md`: los documentos con su estado, el método por página, el CER por documento y por categoría, los tiempos y los errores.

La CLI devuelve `0` si todo se procesó u omitió, `1` si algún documento terminó con error (el resto del lote se procesa igual) y `2` si los argumentos son inválidos.

### Cómo funciona

1. **Formato.** El pipeline acepta `.pdf`, `.png`, `.jpg`/`.jpeg` y `.tif`/`.tiff`. Cualquier otro formato queda como error `unsupported_format`.
2. **`doc_id`.** Es el `sha256` del archivo. Si ya existe `documents/<doc_id>.jsonl` con la misma `PIPELINE_VERSION`, el documento se omite (`skipped`).
3. **Detección por página.** Una página es nativa si su capa de texto tiene al menos 50 caracteres no blancos y al menos el 90 % de ellos son imprimibles. Si no cumple, la página completa se rasteriza a 300 dpi y pasa por OCR. Una página escaneada con un sello de texto corto va a OCR, y el OCR lee el sello junto con la imagen.
4. **Normalización.** El texto se pasa a NFC y se colapsan los espacios dentro de cada línea, pero se conservan los saltos de línea. El CER se calcula sobre el texto con todos los blancos colapsados.
5. **Errores.** Los errores (`unsupported_format`, `unreadable_file`, `ocr_failed`) se registran por documento y no cortan el lote.

### Configuración

Cada valor se toma de una variable de entorno con prefijo `INGEST_` (se lee con `pydantic-settings`) y se puede pisar con un flag de la CLI.

| Variable | Flag | Por defecto | Qué hace |
| --- | --- | --- | --- |
| `INGEST_MIN_NATIVE_CHARS` | `--min-native-chars` | 50 | Mínimo de caracteres no blancos para que la página sea nativa |
| `INGEST_MIN_PRINTABLE_RATIO` | `--min-printable-ratio` | 0.9 | Proporción mínima de caracteres imprimibles para que la página sea nativa |
| `INGEST_OCR_DPI` | `--dpi` | 300 | Resolución a la que se rasteriza la página para el OCR |
| `INGEST_OCR_LANG` | `--lang` | `spa+eng` | Idiomas de Tesseract |
| `INGEST_OCR_PSM` | `--psm` | 3 | Modo de segmentación de página de Tesseract |
| `INGEST_OCR_TIMEOUT_S` | (sin flag) | 120 | Timeout por página de OCR, en segundos |

Cambiar estos valores **no** invalida el salteo: para reingestar con otra configuración, usá otro `--out` o subí `PIPELINE_VERSION`.

## Tests

```bash
uv run pytest                  # suite rápida, con OCR falso (corre en CI)
uv run pytest -m integration   # Tesseract real sobre el corpus: umbrales de CER y página con sello
uv run ruff check . && uv run ruff format --check . && uv run mypy
```

Hay al menos un test por cada escenario de la spec. Los tests marcados `integration` quedan excluidos por defecto (`addopts = -m 'not integration'`).

## Corpus ficticio

`data/corpus/` tiene 20 documentos de RRHH y políticas internas de "Acme S.A.", una empresa ficticia:

| Categoría | Cantidad | Cómo se genera |
| --- | --- | --- |
| Nativo | 8 | PDF con capa de texto (reportlab) |
| Escaneo limpio | 6 | Página rasterizada a 300 dpi, rotación ≤ 0,5°, ruido gaussiano sigma 10, bajada a 200 dpi, JPEG calidad 85 |
| Escaneo ruidoso | 4 | Igual, con rotación de 1 a 2°, sigma 35 y JPEG calidad 60 |
| Mixto | 2 | Páginas nativas y escaneadas; una página escaneada lleva un sello con capa de texto de 24 caracteres |

Dos de los escaneos son `.jpg` sueltos y el resto son PDFs. El texto de referencia por página está en `data/corpus/ground_truth/<archivo>.json`, y la semilla, los perfiles y los hashes, en `ground_truth/manifest.json`. Todo el contenido es inventado: las personas, los legajos y los montos. Los correos usan el dominio reservado `acme.example`, y no hay números de documento ni teléfonos. El corpus ocupa 9,3 MB.

## Resultados medidos

Corrida registrada en [`REPORT.md`](REPORT.md): commit `da01914`, Tesseract 5.3.4 con `spa+eng` y psm 3, en un contenedor de 4 vCPU.

| Categoría | Documentos | CER medio | CER máximo | Umbral de la spec | Resultado |
| --- | --- | --- | --- | --- | --- |
| Nativo | 8 | 0,00 % | 0,00 % | (sin umbral) | |
| Escaneo limpio | 6 | 4,04 % | 23,81 % | ≤ 2 % | **No cumple** |
| Escaneo ruidoso | 4 | 0,04 % | 0,18 % | ≤ 8 % | Cumple |
| Mixto | 2 | 0,00 % | 0,00 % | (sin umbral) | |

- 35 páginas (20 nativas y 15 con OCR) en 29,6 s, o sea 0,85 s por página en promedio. Casi todo el tiempo es de OCR: unos 2 s por página escaneada, contra milisegundos por página nativa.
- La reingesta sin cambios omite los 20 documentos en 0,03 s.
- **Hallazgo**: el escaneo limpio no cumple por un solo documento con tabla. Tesseract (psm 3) lee la columna "Importe" después del resto de la página: los caracteres están bien, pero el orden no. Con `--psm 4` o `--psm 6` el CER limpio baja a 0,07 %. No se adoptó ese valor porque se eligió mirando el mismo corpus que mide el resultado. La decisión está en las "Preguntas abiertas" de la propuesta y el test de integración del umbral limpio queda en rojo.

## Limitaciones

- **El corpus sintético es más fácil que los escaneos reales.** La única degradación que simula es ruido gaussiano, rotación y JPEG. No hay desenfoque, manchas, sombras, papel con textura, sellos manuscritos ni fotos de celular. El perfil ruidoso dio casi el mismo CER que el limpio (0,04 %), así que el umbral de 8 % todavía no se puso a prueba con un caso difícil.
- **Las tablas salen como texto plano.** No se reconstruyen filas ni columnas. En los escaneos, el orden de lectura de una tabla depende del modo de segmentación de Tesseract (ver el hallazgo).
- **No hay detección de títulos ni de estructura.** La salida conserva los saltos de línea para que `add-rag-core` pueda detectar títulos.
- **Las imágenes sin metadato de dpi se tratan como si estuvieran a 300 dpi.**
- **El OCR en la nube y los formatos Office, HTML o correo** quedan fuera de alcance (ver `design.md`).
