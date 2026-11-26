# Spec Delta

## Purpose

Convertir PDFs e imágenes, nativos o escaneados, en documentos normalizados con texto por página, metadatos y una medida de calidad, listos para indexar.

## ADDED Requirements

### Requirement: Salida normalizada por documento
El pipeline SHALL producir, por cada documento de entrada, un registro con `doc_id` estable, nombre de origen, cantidad de páginas y, por página, el texto, el número de página y el método de extracción (`native` u `ocr`).

#### Scenario: PDF nativo
- **WHEN** se ingesta un PDF de 3 páginas con capa de texto
- **THEN** la salida tiene 3 páginas con método `native` y texto no vacío

#### Scenario: Archivo no soportado
- **WHEN** se ingesta un archivo `.docx`
- **THEN** el documento se reporta como error `unsupported_format` y el resto del lote se procesa igual

### Requirement: OCR selectivo
El pipeline SHALL aplicar OCR solo a las páginas sin texto extraíble útil, y MUST registrar qué páginas pasaron por OCR.

#### Scenario: PDF mixto
- **WHEN** se ingesta un PDF con las páginas 1 y 3 nativas y la página 2 escaneada
- **THEN** solo la página 2 tiene método `ocr`

#### Scenario: Imagen suelta
- **WHEN** se ingesta un PNG con texto
- **THEN** la salida tiene 1 página con método `ocr`

### Requirement: Calidad de OCR medida
El pipeline SHALL calcular el CER de cada documento que tenga texto de referencia y MUST incluirlo en el reporte.

#### Scenario: Escaneo limpio
- **WHEN** se ingestan los documentos del corpus marcados como escaneo limpio
- **THEN** el CER medio es menor o igual a 2%

#### Scenario: Escaneo ruidoso
- **WHEN** se ingestan los documentos del corpus marcados como escaneo ruidoso
- **THEN** el CER medio es menor o igual a 8%

#### Scenario: Texto de referencia ilegible
- **WHEN** el texto de referencia de un documento existe pero no se puede leer
- **THEN** el documento se ingiere igual, su CER queda vacío y el reporte registra el aviso `invalid_ground_truth` con su detalle

### Requirement: Reporte de ingesta
El pipeline SHALL generar un reporte en JSON y en Markdown con documentos procesados, páginas por método, CER por documento y promedio, tiempo total, tiempo por página y errores.

#### Scenario: Corpus completo
- **WHEN** se ingesta el corpus de 20 documentos
- **THEN** el reporte lista los 20 documentos con estado, método por página y CER, y los totales coinciden con la suma por documento

### Requirement: Idempotencia
Reingestar un documento sin cambios en el archivo ni en la configuración MUST NOT duplicar su salida ni volver a procesarlo. La salida SHALL registrar el motor de OCR y una huella de la configuración efectiva con la que se produjo.

#### Scenario: Reingesta
- **WHEN** se ingesta dos veces el mismo directorio sin cambios
- **THEN** la segunda corrida reporta 20 documentos omitidos y el `doc_id` de cada uno no cambia

#### Scenario: Cambio de configuración fuerza reprocesamiento
- **WHEN** se reingesta el mismo directorio sin cambios en los archivos pero con otra configuración de extracción (modo de segmentación, dpi, umbrales de detección, idiomas o motor de OCR)
- **THEN** los documentos se reprocesan, el `doc_id` no cambia, la salida no se duplica y registra el motor de OCR y la huella de la nueva configuración

### Requirement: Datos ficticios
El corpus versionado en el repo MUST ser ficticio y no contener PII real.

#### Scenario: Composición del corpus
- **WHEN** se genera el corpus
- **THEN** contiene 20 documentos: 8 nativos, 6 escaneos limpios, 4 escaneos ruidosos y 2 PDFs mixtos, cada uno con su texto de referencia por página

#### Scenario: Página escaneada con poco texto nativo
- **WHEN** un PDF mixto tiene una página escaneada que incluye un sello con capa de texto de menos de 50 caracteres
- **THEN** esa página se procesa con OCR y su texto reconocido incluye el contenido de la imagen

#### Scenario: Generación reproducible
- **WHEN** se corre el script de generación del corpus con la misma semilla
- **THEN** se obtienen los mismos 20 documentos y el mismo texto de referencia
