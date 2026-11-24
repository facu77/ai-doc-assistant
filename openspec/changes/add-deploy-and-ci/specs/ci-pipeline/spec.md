# Spec Delta

## Purpose

Verificar automáticamente cada PR y cada push a `main` con lint, tipos, tests, build de imágenes, un gate de evaluación determinista contra la línea base y una prueba de humo en un cluster local, de forma rápida, reproducible y con permisos mínimos.

## ADDED Requirements

### Requirement: Jobs separados de verificación
El pipeline SHALL correr en cada PR y en cada push a `main` jobs independientes de lint y tipos, de tests, de build de imágenes, de evaluación y de prueba de humo, y MUST marcar el PR en rojo si alguno falla.

#### Scenario: PR correcto
- **WHEN** se abre un PR que no rompe nada
- **THEN** todos los jobs terminan en verde en 15 minutos o menos con la caché caliente (propuesto)

#### Scenario: Error de tipos
- **WHEN** un PR introduce un error de mypy o de `tsc`
- **THEN** el job de lint y tipos falla, nombra el archivo y el PR queda en rojo

#### Scenario: Mismos comandos que en local
- **WHEN** se comparan los pasos del pipeline con `scripts/verify.sh`
- **THEN** cada comando de verificación local tiene su equivalente en la CI, y un chequeo automático falla si alguno falta

### Requirement: Gate de evaluación determinista
El job de evaluación SHALL correr la evaluación con un perfil de CI que no llame a proveedores pagos ni requiera claves, y MUST producir las mismas métricas gateadas en dos corridas sobre el mismo commit.

#### Scenario: Sin claves
- **WHEN** el job de evaluación corre en un PR sin acceso a secretos
- **THEN** termina usando `LLM_PROVIDER=fake` y sin ninguna llamada de red a un proveedor de LLM

#### Scenario: Reproducibilidad
- **WHEN** se corre el job de evaluación dos veces sobre el mismo commit
- **THEN** recall@5 y MRR difieren en menos de 0,001 entre corridas (propuesto)

#### Scenario: Falta el evaluador o la línea base
- **WHEN** el job corre en modo estricto y no existe el script de evaluación o la línea base
- **THEN** el job falla con un mensaje que nombra el archivo faltante, en vez de pasar en verde

### Requirement: Falla por regresión de calidad
El gate SHALL comparar cada métrica gateada contra la línea base y MUST fallar si alguna queda por debajo de `línea base − tolerancia`, con una tolerancia de 0,02 absoluta (propuesto). El gate MUST NOT actualizar la línea base de forma automática.

#### Scenario: Métrica dentro de la tolerancia
- **WHEN** recall@5 de la línea base es 0,80 y la corrida da 0,79
- **THEN** el gate pasa

#### Scenario: Regresión
- **WHEN** recall@5 de la línea base es 0,80 y la corrida da 0,77
- **THEN** el gate falla y su salida muestra, por métrica, la línea base, el valor obtenido y la diferencia

#### Scenario: Mejora
- **WHEN** todas las métricas superan la línea base
- **THEN** el gate pasa y la línea base versionada queda sin cambios

#### Scenario: Demostración con regresión intencional
- **WHEN** se abre el PR de la rama de demostración que degrada la recuperación a propósito
- **THEN** el job de evaluación falla por regresión mientras los demás jobs pasan, y el README enlaza ese PR y uno en verde

### Requirement: Prueba de humo en cluster dentro de la CI
El pipeline SHALL desplegar las imágenes construidas en el mismo pipeline en un cluster local efímero y correr la prueba de humo, y MUST fallar si el despliegue no queda listo o la prueba de humo falla.

#### Scenario: Despliegue correcto
- **WHEN** las imágenes del PR se construyen bien
- **THEN** el job despliega esas imágenes, sin reconstruirlas, y la prueba de humo pasa

#### Scenario: Pod que no queda listo
- **WHEN** un cambio hace que un pod no pase su readiness
- **THEN** el job falla en 10 minutos o menos (propuesto) y publica los eventos y logs de los pods como artefacto

### Requirement: Caché y versiones fijadas
El pipeline SHALL cachear las dependencias de Python y Node, las capas de las imágenes y el modelo de embeddings de evaluación, y MUST referenciar cada acción de terceros por un SHA de commit completo y cada herramienta (kind, kubectl, Helm) por una versión exacta.

#### Scenario: Acciones fijadas
- **WHEN** se leen los workflows del repo
- **THEN** cada `uses:` de terceros referencia un SHA de 40 caracteres, y un chequeo automático falla si encuentra un tag o una rama

#### Scenario: Segunda corrida con caché
- **WHEN** se vuelve a correr el pipeline sin cambios en los lockfiles
- **THEN** las dependencias y el modelo se restauran de la caché sin descargarse otra vez

### Requirement: Permisos mínimos y publicación condicionada
El pipeline SHALL declarar permisos de solo lectura por defecto y dar permisos de escritura solo al job que los necesita. La publicación de imágenes MUST ocurrir solo en un push a `main` con todos los jobs en verde y con la publicación habilitada por configuración del repo, y MUST NOT ocurrir en un PR.

#### Scenario: PR
- **WHEN** corre el pipeline de un PR, incluso desde un fork
- **THEN** ningún job tiene permisos de escritura ni acceso a secretos, y no se publica ninguna imagen

#### Scenario: Push a `main` habilitado
- **WHEN** se hace un push a `main`, todos los jobs pasan y la publicación está habilitada
- **THEN** se publican las imágenes en el registro con un tag por SHA corto y el tag `main`

#### Scenario: Publicación deshabilitada
- **WHEN** se hace un push a `main` con la publicación deshabilitada
- **THEN** el job de publicación se omite y el pipeline queda en verde
