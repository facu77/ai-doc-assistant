# Spec Delta

## Purpose

Convertir textos en vectores que representen su significado, con un modelo identificado y de dimensión fija, para indexar documentos y buscar por similitud de forma reproducible.

## ADDED Requirements

### Requirement: Modelo identificado y de dimensión fija
El sistema SHALL seleccionar el modelo de embeddings por `EMBEDDINGS_PROVIDER` y `EMBEDDINGS_MODEL`, y MUST exponer el identificador del modelo y la dimensión de sus vectores.

#### Scenario: Modelo por defecto
- **WHEN** el servicio arranca con `EMBEDDINGS_PROVIDER=local` y sin `EMBEDDINGS_MODEL`
- **THEN** usa `intfloat/multilingual-e5-small` e informa la dimensión 384

#### Scenario: Proveedor desconocido
- **WHEN** el servicio arranca con `EMBEDDINGS_PROVIDER=desconocido`
- **THEN** el arranque falla con un error de configuración que lista los proveedores válidos

### Requirement: Rol del texto: consulta o pasaje
El sistema SHALL distinguir entre embeddings de consultas y de pasajes (documentos), y MUST aplicar a cada uno el formato que exige el modelo.

#### Scenario: Consulta y pasaje con el mismo texto
- **WHEN** se generan el embedding de consulta y el de pasaje para el texto "licencia anual"
- **THEN** los dos vectores tienen la dimensión del modelo y no son idénticos

#### Scenario: Modelo fuera de la familia e5
- **WHEN** `EMBEDDINGS_MODEL` es un modelo que no es de la familia e5 (por ejemplo, `sentence-transformers/all-MiniLM-L6-v2`)
- **THEN** los textos se embeben sin los prefijos `"query: "` y `"passage: "`

#### Scenario: Modelo e5 instruct
- **WHEN** `EMBEDDINGS_MODEL` es una variante e5 `-instruct` (por ejemplo, `intfloat/multilingual-e5-large-instruct`), cuyo formato de prompt no está implementado
- **THEN** el arranque falla con un error de configuración que lo explica, antes de cargar el modelo

### Requirement: Determinismo
Para el mismo modelo y el mismo texto, el sistema MUST producir el mismo vector en corridas sucesivas, dentro de una tolerancia numérica.

#### Scenario: Dos corridas
- **WHEN** se genera dos veces el embedding de los mismos 10 textos en CPU
- **THEN** la similitud coseno entre cada par de vectores correspondientes es mayor o igual a 0,9999

### Requirement: Procesamiento en lotes
El sistema SHALL procesar las listas de textos en lotes de `EMBEDDINGS_BATCH_SIZE` y devolver un vector por texto, en el mismo orden de la entrada.

#### Scenario: Lote grande
- **WHEN** se piden embeddings para 250 textos con un tamaño de lote de 100
- **THEN** se devuelven 250 vectores en el mismo orden, todos de dimensión 384, en 3 lotes

### Requirement: Similitud semántica
Con el modelo por defecto, los textos de significado parecido SHALL quedar más cerca que los textos no relacionados.

#### Scenario: Paráfrasis frente a texto no relacionado
- **WHEN** se compara la consulta "¿cómo pido vacaciones?" con el pasaje "Procedimiento para solicitar la licencia anual" y con el pasaje "Receta de pan casero"
- **THEN** la similitud coseno con el pasaje de la licencia es mayor que con la receta
