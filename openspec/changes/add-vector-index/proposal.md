# Proposal

## Why

Hay que elegir el almacén vectorial con datos, no por moda. Un benchmark reproducible entre FAISS (en proceso) y Qdrant (servicio) sobre el mismo corpus y los mismos embeddings le da al POC una decisión defendible y una métrica de recuperación de base.

## What Changes

- Chunking inicial de los documentos ingestados, con tamaño y solapamiento fijos (línea base). Las variantes de chunking se prueban en `add-rag-core`.
- El índice registra qué modelo de embeddings y qué dimensión usa, y el sistema rechaza consultas o indexaciones hechas con un modelo distinto, para que no se mezclen vectores incomparables.
- Interfaz `VectorStore` (upsert, búsqueda por similitud con filtros de metadatos y borrado por `doc_id`) con adaptadores para Qdrant y FAISS.
- Un script de benchmark que mide recall@10 contra la búsqueda exacta (fuerza bruta), latencia p50 y p95, tiempo de indexación y memoria.
- Qdrant agregado a `deploy/compose.yaml`.

## Capabilities

### New Capabilities
- `vector-index`: indexación de chunks con metadatos y búsqueda por similitud con filtros, intercambiable entre backends, con benchmark de calidad y latencia.

### Modified Capabilities

## Impact

- Código nuevo: `services/ai/src/ai_doc_assistant/index/` y `evals/bench_vector.py`.
- Dependencias: `qdrant-client` y `faiss-cpu`.
- Infraestructura: servicio `qdrant` en compose, con volumen.
- Depende de `add-ingest-pipeline` (formato `IngestedDocument`) y de los embeddings de `add-llm-client`.

## Preguntas abiertas

1. ~~¿Qué modelo de embeddings usamos?~~ **Resuelta** en `add-llm-client`: `intfloat/multilingual-e5-small`, 384 dimensiones.
2. ¿Con qué tamaño de corpus hacemos el benchmark? Con 20 documentos no se distinguen los índices aproximados. Propuesta: agregar un corpus sintético ampliado (por ejemplo, 50 mil chunks) solo para la latencia.
3. ¿Qué umbrales de aceptación usamos? Propuesta: recall@10 de 0,95 o más frente a la búsqueda exacta y p95 de 50 ms o menos en local para 50 mil vectores.
