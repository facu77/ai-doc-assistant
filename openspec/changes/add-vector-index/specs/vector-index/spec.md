# Spec Delta

## Purpose

Indexar chunks de documentos con sus metadatos y recuperar los más similares a una consulta, con filtros, de forma intercambiable entre backends y con calidad y latencia medidas.

## ADDED Requirements

### Requirement: Chunking con trazabilidad
El sistema SHALL dividir cada documento ingestado en chunks que conserven `doc_id`, número de página y un `chunk_id` estable.

#### Scenario: Chunk con origen
- **WHEN** se trocea un documento de 5 páginas
- **THEN** cada chunk tiene `doc_id`, `page` y `chunk_id`, y ningún chunk mezcla texto de dos documentos

### Requirement: Backend intercambiable
El sistema SHALL ofrecer las mismas operaciones de indexación, búsqueda y borrado sobre Qdrant y FAISS, seleccionables por `VECTOR_BACKEND`.

#### Scenario: Mismo resultado en ambos backends con búsqueda exacta
- **WHEN** se indexan los mismos chunks en ambos backends y se consulta con búsqueda exacta
- **THEN** ambos devuelven el mismo top-10

### Requirement: Filtros por metadatos
La búsqueda SHALL aceptar filtros por `doc_id` y por grupos de acceso, y MUST NOT devolver chunks que no cumplan el filtro.

#### Scenario: Filtro por documento
- **WHEN** se busca con un filtro `doc_id = X`
- **THEN** todos los resultados pertenecen a X

### Requirement: Reindexado idempotente
Reindexar un documento MUST reemplazar sus chunks anteriores sin duplicarlos.

#### Scenario: Reindexado
- **WHEN** se indexa dos veces el mismo documento
- **THEN** la cantidad de chunks del documento en el índice no cambia

### Requirement: Benchmark reproducible
El repositorio SHALL incluir un benchmark que reporte recall@10 contra la búsqueda exacta, latencia p50 y p95, tiempo de indexación y memoria para cada backend, y MUST guardar el resultado en un archivo versionable.

#### Scenario: Corrida del benchmark
- **WHEN** se corre el benchmark con una semilla fija
- **THEN** se genera un JSON y una tabla Markdown con las métricas por backend, y dos corridas con la misma semilla dan el mismo recall@10

#### Scenario: Umbrales de aceptación
- **WHEN** se corre el benchmark sobre el corpus ampliado acordado
- **THEN** el backend elegido cumple recall@10 de 0,95 o más y el p95 acordado (propuesto: 50 ms o menos para 50 mil vectores en local)
