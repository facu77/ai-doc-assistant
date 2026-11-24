# Spec Delta

## Purpose

Permitir que cualquier persona levante el POC completo con un comando, en Compose o en un cluster local de Kubernetes, con imágenes endurecidas, configuración desde el entorno, ningún secreto en el repo y una prueba de humo que confirma que funciona.

## ADDED Requirements

### Requirement: Arranque local con un comando
`make up` SHALL levantar todos los servicios del stack desde un clon limpio, con Docker como único requisito y sin claves de proveedores, y MUST terminar con todos los servicios sanos o con un error que nombre el servicio que no arrancó. `make down` SHALL detenerlos y borrarlos.

#### Scenario: Clon limpio sin `.env`
- **WHEN** se corre `make up` en un clon limpio donde no existe `.env`
- **THEN** el comando termina con código 0, todos los servicios quedan sanos en 120 segundos o menos desde que las imágenes están construidas (propuesto) y el servicio de IA usa `LLM_PROVIDER=fake`

#### Scenario: Orden de arranque
- **WHEN** el stack arranca
- **THEN** el servicio de IA arranca recién cuando el vector store está sano, y el gateway recién cuando el servicio de IA está sano

#### Scenario: Servicio que no arranca
- **WHEN** un servicio no llega a estar sano dentro del tiempo de espera
- **THEN** `make up` termina con código distinto de 0 y su salida nombra ese servicio

#### Scenario: Bajar el stack
- **WHEN** se corre `make down` con el stack levantado
- **THEN** no queda ningún contenedor del proyecto corriendo

### Requirement: Imágenes endurecidas
Las imágenes de los servicios SHALL construirse en varias etapas, sin herramientas de build en la etapa final, y MUST correr con un usuario distinto de root, partir de una imagen base fijada por digest y declarar un healthcheck.

#### Scenario: Usuario no root
- **WHEN** se inspecciona cualquier imagen del proyecto o se ejecuta `id -u` dentro del contenedor
- **THEN** el UID es distinto de 0

#### Scenario: Base fijada
- **WHEN** se lee cualquier `Dockerfile` del proyecto
- **THEN** cada `FROM` referencia una imagen con digest `sha256`

#### Scenario: Tamaño acotado
- **WHEN** se construyen las imágenes
- **THEN** la del servicio de IA pesa 1,2 GB o menos y la del gateway 250 MB o menos (propuesto)

#### Scenario: Healthcheck en la imagen
- **WHEN** un contenedor arranca y su endpoint de salud responde
- **THEN** Docker lo reporta como sano sin configuración extra en Compose

### Requirement: Cluster local con kind
`make kind-up` SHALL crear un cluster local, cargar las imágenes del proyecto y desplegar todos los servicios, y MUST ser idempotente. `make kind-down` SHALL borrar el cluster.

#### Scenario: Despliegue desde cero
- **WHEN** se corre `make kind-up` sin un cluster previo
- **THEN** el comando termina con código 0 en 8 minutos o menos (propuesto), todos los pods quedan listos y el gateway responde en `localhost:8080`

#### Scenario: Segunda ejecución
- **WHEN** se corre `make kind-up` con el cluster ya creado
- **THEN** el comando actualiza el despliegue sin error y no crea un segundo cluster

#### Scenario: Teardown
- **WHEN** se corre `make kind-down`
- **THEN** el cluster del proyecto deja de existir

### Requirement: Probes, recursos y contexto de seguridad en Kubernetes
Cada contenedor desplegado en el cluster SHALL declarar readiness y liveness probes, requests y limits de CPU y memoria, y MUST correr sin root y sin escalada de privilegios. La readiness MUST reflejar la disponibilidad de las dependencias, y la liveness solo la del proceso.

#### Scenario: Manifiestos completos
- **WHEN** se renderizan los manifiestos del despliegue
- **THEN** cada contenedor tiene ambas probes, requests y limits, `runAsNonRoot: true` y `allowPrivilegeEscalation: false`, y un chequeo automático falla si falta alguno

#### Scenario: Cae una dependencia
- **WHEN** el vector store deja de responder en el cluster
- **THEN** el pod del servicio de IA deja de estar listo y sale del balanceo, pero no se reinicia por la liveness mientras el proceso responde

### Requirement: Configuración y secretos desde el entorno
La configuración del despliegue SHALL salir de variables de entorno o de valores no sensibles versionados, y el repo MUST NOT contener secretos ni manifiestos con valores secretos. Los secretos MUST cargarse en el cluster desde el entorno local al desplegar.

#### Scenario: Manifiestos sin secretos
- **WHEN** se renderizan los manifiestos con los valores por defecto
- **THEN** no hay ningún Secret con datos y los contenedores lo referencian solo por nombre

#### Scenario: Clave desde `.env`
- **WHEN** `.env` define `ANTHROPIC_API_KEY` y se corre `make kind-up`
- **THEN** el servicio de IA recibe la variable desde un Secret del cluster y el valor no aparece en la salida del comando

### Requirement: Prueba de humo
El proyecto SHALL ofrecer una prueba de humo única, parametrizada por la URL base, que valide un despliegue en Compose o en kind, y MUST salir con código distinto de 0 e indicar el paso que falló.

#### Scenario: Despliegue sano
- **WHEN** se corre la prueba de humo contra un stack recién levantado con `LLM_PROVIDER=fake`
- **THEN** el endpoint de salud responde 200 dentro de 60 segundos, se indexa un documento ficticio y una consulta devuelve una respuesta con al menos una cita, todo en 3 minutos o menos (propuesto)

#### Scenario: Despliegue roto
- **WHEN** se corre la prueba de humo con el servicio de IA detenido
- **THEN** sale con código distinto de 0 y su salida nombra el paso que falló
