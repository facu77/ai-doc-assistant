"""Contenido del corpus ficticio de "Acme S.A." (RRHH y políticas internas).

Todo es inventado: la empresa, las personas, los legajos, los montos y los plazos. Los
correos usan el dominio reservado `acme.example` (RFC 2606) y no hay teléfonos ni números
de documento. Las cifras concretas están para que más adelante se pueda armar un set de
preguntas y respuestas (`add-rag-core`).
"""

from __future__ import annotations

from dataclasses import dataclass

from ingest.models import Category, PageKind


@dataclass(frozen=True)
class Heading:
    text: str


@dataclass(frozen=True)
class Para:
    text: str


@dataclass(frozen=True)
class Row:
    """Fila de tabla. Se dibuja en columnas y su referencia es texto plano (limitación)."""

    cells: tuple[str, ...]


Block = Heading | Para | Row


@dataclass(frozen=True)
class PageSpec:
    kind: PageKind
    blocks: tuple[Block, ...]
    stamp: str | None = None
    """Sello con capa de texto nativa sobre una página escaneada (caso borde de la spec)."""


@dataclass(frozen=True)
class DocSpec:
    filename: str
    category: Category
    title: str
    pages: tuple[PageSpec, ...]


def _native(*blocks: Block) -> PageSpec:
    return PageSpec(kind="native", blocks=blocks)


def _scan(*blocks: Block, stamp: str | None = None) -> PageSpec:
    return PageSpec(kind="scan", blocks=blocks, stamp=stamp)


H = Heading
P = Para


def R(*cells: str) -> Row:
    return Row(cells=cells)


DOCUMENTS: tuple[DocSpec, ...] = (
    # ------------------------------------------------------------------ nativos (8)
    DocSpec(
        filename="01-politica-licencias.pdf",
        category="native",
        title="Política de licencias",
        pages=(
            _native(
                H("Acme S.A. - Política de licencias"),
                P(
                    "Versión 3.2. Vigente desde el 1 de marzo de 2026. Responsable: Gerencia de "
                    "Recursos Humanos. Alcance: todo el personal en relación de dependencia de "
                    "Acme S.A., en todas sus sedes."
                ),
                H("1. Vacaciones anuales"),
                P(
                    "Las vacaciones se calculan según la antigüedad al 31 de diciembre de cada "
                    "año. Con menos de 5 años de antigüedad corresponden 14 días corridos. Entre "
                    "5 y 10 años corresponden 21 días corridos. Entre 10 y 20 años corresponden "
                    "28 días corridos. Con más de 20 años corresponden 35 días corridos."
                ),
                P(
                    "Las vacaciones se solicitan con al menos 30 días de anticipación mediante el "
                    "formulario RH-07. Se pueden fraccionar en hasta 3 períodos, siempre que uno "
                    "de ellos sea de 7 días corridos o más."
                ),
                P(
                    "Los días no gozados no se acumulan de un año al siguiente, salvo autorización "
                    "escrita de la Gerencia de Recursos Humanos, que puede extender el plazo hasta "
                    "el 31 de marzo del año siguiente."
                ),
                H("2. Licencia por enfermedad"),
                P(
                    "La persona debe avisar a su responsable y a Recursos Humanos antes de las 2 "
                    "horas del inicio de su jornada. El certificado médico se presenta dentro de "
                    "las 48 horas por el portal de autogestión."
                ),
            ),
            _native(
                H("3. Licencias especiales"),
                P(
                    "Matrimonio o unión convivencial registrada: 10 días corridos, que pueden "
                    "unirse a las vacaciones anuales."
                ),
                P(
                    "Nacimiento o adopción, persona no gestante: 15 días corridos, a tomar dentro "
                    "de los 30 días posteriores al nacimiento o a la guarda con fines de adopción."
                ),
                P(
                    "Nacimiento, persona gestante: 90 días corridos, según la legislación vigente, "
                    "más 15 días adicionales pagos que otorga Acme S.A. como beneficio propio."
                ),
                P(
                    "Fallecimiento de cónyuge, hijos o padres: 3 días corridos. Fallecimiento de "
                    "hermanos: 1 día."
                ),
                P(
                    "Exámenes de estudios secundarios, terciarios o universitarios: 2 días por "
                    "examen, con un máximo de 10 días por año calendario. Se presenta la constancia "
                    "de examen dentro de los 5 días hábiles."
                ),
                P("Mudanza: 1 día por año calendario."),
                P("Donación de sangre: el día de la donación, con constancia del centro de salud."),
                H("4. Licencia sin goce de haberes"),
                P(
                    "Con al menos 2 años de antigüedad se puede pedir una licencia sin goce de "
                    "haberes de hasta 6 meses. La solicitud se presenta con 45 días de anticipación "
                    "y requiere la aprobación de la Gerencia del área y de Recursos Humanos."
                ),
            ),
            _native(
                H("5. Procedimiento y registro"),
                P(
                    "Toda licencia se registra en el portal de autogestión. El responsable directo "
                    "aprueba o rechaza la solicitud dentro de los 3 días hábiles. Si no responde en "
                    "ese plazo, la solicitud pasa automáticamente a Recursos Humanos."
                ),
                P(
                    "Recursos Humanos controla los saldos de vacaciones dos veces por año, en junio "
                    "y en diciembre, e informa a cada persona su saldo disponible."
                ),
                H("6. Consultas"),
                P(
                    "Las consultas sobre esta política se envían a licencias@acme.example o se "
                    "hacen por el canal interno de Recursos Humanos, interno 4410."
                ),
                P("Esta política reemplaza a la versión 3.1 del 15 de enero de 2025."),
            ),
        ),
    ),
    DocSpec(
        filename="02-politica-viaticos.pdf",
        category="native",
        title="Política de viáticos y gastos de viaje",
        pages=(
            _native(
                H("Acme S.A. - Política de viáticos y gastos de viaje"),
                P(
                    "Versión 2.0. Vigente desde el 1 de julio de 2026. Aplica a todo viaje por "
                    "trabajo que requiera pernoctar fuera del domicilio habitual."
                ),
                H("1. Montos diarios de viático"),
                P("El viático diario cubre comidas y traslados urbanos. Los montos vigentes son:"),
                R("Destino", "Monto diario"),
                R("CABA y Gran Buenos Aires", "$ 38.000"),
                R("Interior del país", "$ 45.000"),
                R("Países limítrofes", "USD 90"),
                R("Resto del mundo", "USD 140"),
                P(
                    "El alojamiento no está incluido en el viático y se reserva por la agencia de "
                    "viajes contratada por Acme S.A."
                ),
                H("2. Anticipos"),
                P(
                    "Se puede solicitar un anticipo de hasta el 70% del viático estimado, con al "
                    "menos 5 días hábiles de anticipación al viaje."
                ),
                H("3. Uso de vehículo propio"),
                P(
                    "El uso de vehículo propio se reintegra a $ 210 por kilómetro recorrido, más "
                    "peajes y estacionamiento con comprobante."
                ),
            ),
            _native(
                H("4. Rendición de gastos"),
                P(
                    "La rendición se presenta dentro de los 10 días hábiles posteriores al regreso, "
                    "con el formulario RH-12 y los comprobantes originales o digitalizados."
                ),
                P(
                    "Los gastos sin comprobante se aceptan hasta un máximo de $ 15.000 por viaje y "
                    "deben justificarse por escrito."
                ),
                P("No se reintegran bebidas alcohólicas, multas de tránsito ni gastos personales."),
                H("5. Aprobaciones"),
                P(
                    "Los viajes nacionales los aprueba el responsable directo. Los viajes al "
                    "exterior requieren además la aprobación de la Gerencia General."
                ),
                P("Las consultas se envían a viajes@acme.example."),
            ),
        ),
    ),
    DocSpec(
        filename="03-beneficios.pdf",
        category="native",
        title="Beneficios para el personal",
        pages=(
            _native(
                H("Acme S.A. - Beneficios para el personal 2026"),
                P(
                    "Este documento resume los beneficios vigentes desde el 1 de enero de 2026 "
                    "para todo el personal en relación de dependencia."
                ),
                H("1. Cobertura médica"),
                P(
                    "Acme S.A. cubre el plan 310 de la empresa de medicina prepaga contratada para "
                    "la persona y su grupo familiar primario, sin costo adicional."
                ),
                H("2. Almuerzo"),
                P(
                    "Se acredita una tarjeta de almuerzo de $ 9.500 por día trabajado, incluidos "
                    "los días de trabajo remoto."
                ),
                H("3. Actividad física"),
                P(
                    "Se reintegra el 50% de la cuota de un gimnasio o club, con un tope de $ 25.000 "
                    "por mes, contra la presentación del comprobante."
                ),
                H("4. Guardería"),
                P(
                    "Para hijos e hijas menores de 4 años se reintegra la cuota de guardería o jardín "
                    "maternal hasta $ 120.000 por mes por cada hijo o hija."
                ),
            ),
            _native(
                H("5. Día de cumpleaños"),
                P(
                    "Cada persona tiene libre el día de su cumpleaños. Si cae en fin de semana o "
                    "feriado, se toma el día hábil siguiente."
                ),
                H("6. Bono anual por desempeño"),
                P(
                    "El bono anual se paga en marzo y va de 0 a 2 sueldos según la calificación de "
                    "la evaluación de desempeño y el resultado de la compañía."
                ),
                H("7. Kit de bienvenida"),
                P(
                    "Al ingresar, cada persona recibe una notebook, auriculares y un kit de "
                    "bienvenida. La notebook se renueva cada 3 años."
                ),
                P("Las consultas se envían a beneficios@acme.example."),
            ),
        ),
    ),
    DocSpec(
        filename="04-codigo-de-conducta.pdf",
        category="native",
        title="Código de conducta",
        pages=(
            _native(
                H("Acme S.A. - Código de conducta"),
                P(
                    "Versión 4.0, aprobada por el Directorio el 10 de febrero de 2026. Este código "
                    "aplica a directores, empleados, pasantes y proveedores que trabajan en nombre "
                    "de Acme S.A."
                ),
                H("1. Principios"),
                P(
                    "Actuamos con integridad, respeto y transparencia. No toleramos la "
                    "discriminación, el acoso ni la violencia en ninguna de sus formas."
                ),
                H("2. Conflictos de interés"),
                P(
                    "Toda situación en la que un interés personal pueda influir en una decisión de "
                    "trabajo se declara por escrito al Comité de Ética dentro de los 15 días de "
                    "conocida. Esto incluye participaciones en proveedores o clientes y relaciones "
                    "familiares con personas a cargo."
                ),
                H("3. Regalos e invitaciones"),
                P(
                    "Se pueden aceptar regalos de cortesía de hasta USD 50 de valor. Los regalos de "
                    "mayor valor se rechazan o se entregan al Comité de Ética. Nunca se aceptan "
                    "regalos en dinero."
                ),
            ),
            _native(
                H("4. Confidencialidad"),
                P(
                    "La información de clientes, empleados y de la compañía se usa solo para fines "
                    "laborales. La obligación de confidencialidad sigue vigente durante 2 años "
                    "después de la desvinculación."
                ),
                H("5. Uso de los recursos"),
                P(
                    "Los equipos, cuentas y sistemas de Acme S.A. se usan para el trabajo. Se "
                    "permite un uso personal razonable que no afecte la seguridad ni la "
                    "productividad."
                ),
                H("6. Línea ética"),
                P(
                    "Cualquier persona puede informar una posible violación de este código, de "
                    "forma anónima, en el sitio etica.acme.example o al correo etica@acme.example. "
                    "El Comité de Ética responde dentro de los 10 días hábiles."
                ),
                P("Acme S.A. prohíbe cualquier represalia contra quien informe de buena fe."),
            ),
            _native(
                H("7. Sanciones"),
                P(
                    "El incumplimiento de este código puede dar lugar a un apercibimiento, una "
                    "suspensión de hasta 30 días o el despido con justa causa, según la gravedad del "
                    "caso y la legislación vigente."
                ),
                H("8. Capacitación y aceptación"),
                P(
                    "Todo el personal completa el curso de ética dentro de los 30 días de su "
                    "ingreso y lo renueva cada 2 años. Al terminar el curso, cada persona firma la "
                    "aceptación de este código en el portal de autogestión."
                ),
            ),
        ),
    ),
    DocSpec(
        filename="05-home-office.pdf",
        category="native",
        title="Política de trabajo remoto",
        pages=(
            _native(
                H("Acme S.A. - Política de trabajo remoto"),
                P(
                    "Vigente desde el 1 de abril de 2026. Aplica a los puestos que la Gerencia del "
                    "área declare compatibles con el trabajo remoto."
                ),
                H("1. Modalidad"),
                P(
                    "Se puede trabajar en forma remota hasta 3 días por semana. Los martes y jueves "
                    "son días de presencia para todos los equipos de oficina central."
                ),
                P(
                    "La modalidad se solicita con al menos 5 días hábiles de anticipación y la "
                    "aprueba el responsable directo."
                ),
                H("2. Horario de disponibilidad"),
                P(
                    "En los días remotos la persona está disponible de 10 a 16 horas para reuniones "
                    "y consultas, dentro de su jornada habitual de 8 horas."
                ),
                H("3. Compensación de gastos"),
                P(
                    "Se paga una compensación mensual de $ 18.000 por conectividad y servicios. "
                    "Además, se reintegra una única vez hasta $ 150.000 para la compra de una silla "
                    "ergonómica."
                ),
            ),
            _native(
                H("4. Seguridad"),
                P(
                    "El trabajo remoto se hace siempre con la VPN corporativa y en redes de "
                    "confianza. No se usan redes públicas abiertas para acceder a sistemas "
                    "internos."
                ),
                H("5. Desconexión digital"),
                P(
                    "Fuera del horario de trabajo nadie está obligado a responder mensajes ni "
                    "correos, salvo guardias acordadas por escrito."
                ),
                P("Las consultas se envían a personas@acme.example."),
            ),
        ),
    ),
    DocSpec(
        filename="06-onboarding.pdf",
        category="native",
        title="Guía de incorporación",
        pages=(
            _native(
                H("Acme S.A. - Guía de incorporación"),
                P(
                    "Bienvenida o bienvenido a Acme S.A. Esta guía resume lo que pasa en tus "
                    "primeras semanas."
                ),
                H("1. Primer día"),
                P(
                    "Tu primer día empieza a las 9 horas en la recepción de la sede central. "
                    "Recursos Humanos te entrega la notebook, la credencial y los accesos."
                ),
                H("2. Período de prueba"),
                P(
                    "El período de prueba es de 6 meses. A los 3 meses tenés una reunión de "
                    "seguimiento con tu responsable y con Recursos Humanos."
                ),
                H("3. Mentor"),
                P(
                    "Cada persona nueva tiene un mentor asignado durante los primeros 90 días. El "
                    "mentor es de otra área y te ayuda a entender cómo trabaja la compañía."
                ),
            ),
            _native(
                H("4. Capacitaciones obligatorias"),
                P(
                    "Dentro de los primeros 30 días completás tres cursos en la plataforma de "
                    "aprendizaje: código de conducta, seguridad de la información y prevención de "
                    "riesgos laborales."
                ),
                H("5. Contactos útiles"),
                P(
                    "Soporte técnico: soporte@acme.example. Recursos Humanos: personas@acme.example. "
                    "Seguridad e higiene: interno 4425."
                ),
            ),
        ),
    ),
    DocSpec(
        filename="07-capacitacion.pdf",
        category="native",
        title="Política de capacitación",
        pages=(
            _native(
                H("Acme S.A. - Política de capacitación y desarrollo"),
                P("Vigente desde el 1 de enero de 2026."),
                H("1. Presupuesto"),
                P(
                    "Cada persona tiene un presupuesto anual de capacitación de $ 600.000, que se "
                    "puede usar en cursos, congresos y certificaciones relacionados con su puesto."
                ),
                H("2. Posgrados"),
                P(
                    "Acme S.A. reintegra el 80% del costo de un posgrado, con un tope anual de "
                    "$ 3.000.000. Quien recibe este beneficio se compromete a permanecer en la "
                    "compañía 12 meses después de terminar el posgrado; si no, devuelve la parte "
                    "proporcional."
                ),
                H("3. Idiomas"),
                P(
                    "Las clases de inglés y portugués se dictan en la oficina dos veces por semana, "
                    "sin costo, para todos los niveles."
                ),
                H("4. Horas de estudio"),
                P(
                    "Se pueden usar hasta 4 horas por semana del horario laboral para capacitación, "
                    "acordadas con el responsable directo."
                ),
            ),
        ),
    ),
    DocSpec(
        filename="08-seguridad-informacion.pdf",
        category="native",
        title="Política de seguridad de la información",
        pages=(
            _native(
                H("Acme S.A. - Política de seguridad de la información"),
                P(
                    "Versión 1.4. Vigente desde el 1 de mayo de 2026. Responsable: Gerencia de "
                    "Tecnología."
                ),
                H("1. Contraseñas"),
                P(
                    "Las contraseñas tienen al menos 12 caracteres y no se reutilizan entre "
                    "sistemas. Se cambian de inmediato si hay sospecha de que fueron expuestas."
                ),
                H("2. Autenticación de dos factores"),
                P(
                    "El segundo factor de autenticación es obligatorio para el correo, la VPN y "
                    "todos los sistemas con datos de clientes o de personal."
                ),
                H("3. Clasificación de la información"),
                P(
                    "La información se clasifica como pública, interna, confidencial o restringida. "
                    "Los datos de legajos y sueldos son siempre restringidos."
                ),
            ),
            _native(
                H("4. Incidentes"),
                P(
                    "Todo incidente de seguridad, como la pérdida de una notebook o un correo de "
                    "phishing, se informa dentro de las 24 horas a seguridad@acme.example."
                ),
                H("5. Dispositivos"),
                P(
                    "Los dispositivos de la compañía tienen el disco cifrado y se bloquean después "
                    "de 5 minutos sin uso."
                ),
                H("6. Revisión"),
                P("Esta política se revisa una vez por año o después de un incidente grave."),
            ),
        ),
    ),
    # ------------------------------------------------------------ escaneos limpios (6)
    DocSpec(
        filename="09-formulario-solicitud-vacaciones.pdf",
        category="clean_scan",
        title="Formulario RH-07 de solicitud de vacaciones",
        pages=(
            _scan(
                H("Acme S.A. - Formulario RH-07"),
                H("Solicitud de vacaciones"),
                P("Empleada: Lucía Fernández"),
                P("Legajo: 4821"),
                P("Área: Finanzas"),
                P("Antigüedad: 6 años"),
                P("Período solicitado: del 11 de enero de 2027 al 31 de enero de 2027"),
                P("Cantidad de días corridos: 21"),
                P("Saldo disponible antes de la solicitud: 21 días"),
                P("Reemplazo durante la ausencia: Martín Gómez, legajo 3954"),
                P("Fecha de la solicitud: 2 de noviembre de 2026"),
                P("Aprobado por: Martín Gómez, Jefe de Tesorería"),
                P("Estado: aprobado el 4 de noviembre de 2026"),
            ),
        ),
    ),
    DocSpec(
        filename="10-memo-aguinaldo.pdf",
        category="clean_scan",
        title="Memo sobre el pago del aguinaldo",
        pages=(
            _scan(
                H("Acme S.A. - Memo interno RH-2026-041"),
                P("Para: todo el personal"),
                P("De: Gerencia de Recursos Humanos"),
                P("Fecha: 20 de noviembre de 2026"),
                H("Pago de la segunda cuota del aguinaldo"),
                P(
                    "La segunda cuota del sueldo anual complementario se acredita el 18 de "
                    "diciembre de 2026, junto con el bono de fin de año de $ 85.000 para todo el "
                    "personal con más de 3 meses de antigüedad."
                ),
                P(
                    "Los recibos de sueldo estarán disponibles en el portal de autogestión desde "
                    "el 17 de diciembre de 2026."
                ),
                P("Las consultas se envían a sueldos@acme.example hasta el 23 de diciembre."),
            ),
        ),
    ),
    DocSpec(
        filename="11-circular-horario-verano.pdf",
        category="clean_scan",
        title="Circular de horario de verano",
        pages=(
            _scan(
                H("Acme S.A. - Circular 2026-12"),
                H("Horario de verano"),
                P(
                    "Desde el 1 de diciembre de 2026 y hasta el 28 de febrero de 2027 rige el "
                    "horario de verano en las oficinas centrales."
                ),
                P(
                    "De lunes a jueves se trabaja de 8 a 17 horas. Los viernes la jornada termina "
                    "a las 14 horas, sin descuento de haberes."
                ),
                P(
                    "Las áreas con atención al cliente organizan turnos para cubrir el horario "
                    "habitual de 9 a 18 horas."
                ),
                P(
                    "El horario de verano no aplica al personal de planta, que mantiene sus turnos "
                    "rotativos."
                ),
                P("Firmado: Gerencia de Recursos Humanos"),
            ),
        ),
    ),
    DocSpec(
        filename="12-reglamento-comedor.pdf",
        category="clean_scan",
        title="Reglamento de comedor y espacios comunes",
        pages=(
            _scan(
                H("Acme S.A. - Reglamento de comedor y espacios comunes"),
                P("Vigente desde el 1 de septiembre de 2026."),
                H("1. Horarios"),
                P(
                    "El comedor funciona de 12 a 15 horas. Cada persona dispone de 45 minutos para "
                    "almorzar, en el turno que acuerde con su equipo."
                ),
                H("2. Reservas"),
                P(
                    "Las salas de reuniones se reservan desde el calendario corporativo con un "
                    "máximo de 2 horas por reunión."
                ),
                H("3. Limpieza"),
                P(
                    "Cada persona lava y guarda la vajilla que usa. Las heladeras se vacían todos "
                    "los viernes a las 16 horas."
                ),
            ),
            _scan(
                H("4. Espacios de descanso"),
                P(
                    "El espacio de descanso del tercer piso es de uso libre. Se pide no hacer "
                    "llamadas de trabajo en ese lugar."
                ),
                H("5. Lactario"),
                P(
                    "El lactario del segundo piso está disponible de 8 a 19 horas y se reserva por "
                    "el calendario corporativo."
                ),
                H("6. Incumplimientos"),
                P("Los incumplimientos reiterados se informan a Recursos Humanos."),
            ),
        ),
    ),
    DocSpec(
        filename="13-formulario-rendicion-gastos.jpg",
        category="clean_scan",
        title="Formulario RH-12 de rendición de gastos",
        pages=(
            _scan(
                H("Acme S.A. - Formulario RH-12"),
                H("Rendición de gastos de viaje"),
                P("Empleado: Diego Ramírez"),
                P("Legajo: 3307"),
                P("Área: Ventas"),
                P("Viaje: Córdoba, del 6 al 8 de octubre de 2026"),
                R("Concepto", "Importe"),
                R("Viático 3 días", "$ 135.000"),
                R("Taxi aeropuerto", "$ 12.400"),
                R("Estacionamiento", "$ 6.800"),
                R("Total rendido", "$ 154.200"),
                P("Anticipo recibido: $ 94.500"),
                P("Saldo a favor del empleado: $ 59.700"),
                P("Fecha de presentación: 14 de octubre de 2026"),
            ),
        ),
    ),
    DocSpec(
        filename="14-procedimiento-licencia-medica.pdf",
        category="clean_scan",
        title="Procedimiento de licencia médica",
        pages=(
            _scan(
                H("Acme S.A. - Procedimiento PR-RH-03"),
                H("Licencia por enfermedad o accidente"),
                P(
                    "1. Avisar al responsable directo y a Recursos Humanos antes de las 2 horas "
                    "del inicio de la jornada."
                ),
                P(
                    "2. Indicar el domicilio donde se encuentra, por si corresponde un control "
                    "médico."
                ),
                P(
                    "3. Cargar el certificado médico en el portal de autogestión dentro de las 48 "
                    "horas."
                ),
                P(
                    "4. El certificado indica el diagnóstico o la causa, los días de reposo y la "
                    "firma y matrícula del profesional."
                ),
            ),
            _scan(
                P(
                    "5. Si el reposo supera los 3 días, el servicio médico de la compañía puede "
                    "hacer un control domiciliario."
                ),
                P(
                    "6. Para volver al trabajo después de más de 10 días de licencia se presenta el "
                    "alta médica."
                ),
                P(
                    "7. Los accidentes de trabajo se informan en el mismo día a seguridad e "
                    "higiene, interno 4425."
                ),
                P("Revisión: octubre de 2026."),
            ),
        ),
    ),
    # ------------------------------------------------------------ escaneos ruidosos (4)
    DocSpec(
        filename="15-acta-comite-seguridad-higiene.pdf",
        category="noisy_scan",
        title="Acta del comité de seguridad e higiene",
        pages=(
            _scan(
                H("Acme S.A. - Acta 2026-09 del Comité de Seguridad e Higiene"),
                P("Fecha: 17 de septiembre de 2026. Lugar: planta de Pilar."),
                P("Presentes: Carla Méndez, Jorge Paz y Valeria Ortiz."),
                H("Temas tratados"),
                P(
                    "1. Se registraron 2 incidentes leves en el tercer trimestre, sin días "
                    "perdidos."
                ),
                P(
                    "2. Se aprueba la compra de 40 pares de calzado de seguridad para el turno "
                    "noche."
                ),
                P(
                    "3. El simulacro de evacuación se hará el 12 de noviembre de 2026 a las 10 "
                    "horas."
                ),
                P(
                    "4. Se recuerda que el uso de protección auditiva es obligatorio en el sector "
                    "de prensas."
                ),
                P("Próxima reunión: 15 de octubre de 2026."),
            ),
        ),
    ),
    DocSpec(
        filename="16-formulario-alta-beneficiario.pdf",
        category="noisy_scan",
        title="Formulario de alta de beneficiario del seguro de vida",
        pages=(
            _scan(
                H("Acme S.A. - Formulario RH-21"),
                H("Designación de beneficiarios del seguro de vida"),
                P("Empleada: Sofía Benítez"),
                P("Legajo: 5190"),
                P("Área: Logística"),
                P("Beneficiario 1: Tomás Benítez, hijo, 50%"),
                P("Beneficiario 2: Ana Ruiz, madre, 50%"),
                P("Capital asegurado: 24 sueldos brutos"),
                P("Fecha: 3 de agosto de 2026"),
                P("Recibido por: Recursos Humanos, sede Pilar"),
            ),
        ),
    ),
    DocSpec(
        filename="17-aviso-cambio-turnos.jpg",
        category="noisy_scan",
        title="Aviso de cambio de turnos en planta",
        pages=(
            _scan(
                H("Acme S.A. - Aviso a todo el personal de planta"),
                H("Cambio de turnos desde el 4 de enero de 2027"),
                P("Turno mañana: de 6 a 14 horas."),
                P("Turno tarde: de 14 a 22 horas."),
                P("Turno noche: de 22 a 6 horas, con un adicional del 15% sobre el básico."),
                P("La rotación de turnos pasa a ser cada 2 semanas."),
                P(
                    "Las solicitudes de cambio de turno se presentan al supervisor con 7 días de "
                    "anticipación."
                ),
                P("Gerencia de Operaciones, planta de Pilar."),
            ),
        ),
    ),
    DocSpec(
        filename="18-politica-prestamos-personales.pdf",
        category="noisy_scan",
        title="Política de préstamos al personal",
        pages=(
            _scan(
                H("Acme S.A. - Política de préstamos al personal"),
                P("Vigente desde el 1 de junio de 2026."),
                H("1. Monto"),
                P(
                    "Se puede pedir un préstamo de hasta 2 sueldos brutos, sin interés, con al "
                    "menos 1 año de antigüedad."
                ),
                H("2. Devolución"),
                P(
                    "El préstamo se devuelve en hasta 12 cuotas mensuales, que se descuentan del "
                    "recibo de sueldo."
                ),
            ),
            _scan(
                H("3. Condiciones"),
                P(
                    "Solo se puede tener un préstamo vigente por vez. Un nuevo préstamo se pide 3 "
                    "meses después de cancelar el anterior."
                ),
                P("Si la relación laboral termina, el saldo se descuenta de la liquidación final."),
                P("Las solicitudes se presentan a prestamos@acme.example."),
            ),
        ),
    ),
    # ------------------------------------------------------------------- mixtos (2)
    DocSpec(
        filename="19-manual-evaluacion-desempeno.pdf",
        category="mixed",
        title="Manual de evaluación de desempeño",
        pages=(
            _native(
                H("Acme S.A. - Manual de evaluación de desempeño"),
                P(
                    "La evaluación de desempeño se hace una vez por año, en noviembre, y tiene una "
                    "revisión de mitad de año en mayo."
                ),
                H("1. Etapas"),
                P(
                    "Primero, cada persona completa su autoevaluación en el portal. Después, el "
                    "responsable directo completa su evaluación. Por último, ambos tienen una "
                    "reunión de devolución de al menos 30 minutos."
                ),
                P("La escala de calificación está en el anexo escaneado de la página siguiente."),
            ),
            _scan(
                H("Anexo A - Escala de calificación"),
                P("1 - No cumple las expectativas del puesto."),
                P("2 - Cumple parcialmente las expectativas."),
                P("3 - Cumple las expectativas."),
                P("4 - Supera las expectativas."),
                P("5 - Desempeño excepcional y referente para el equipo."),
                P("Con calificación 1 se arma un plan de mejora de 90 días."),
            ),
            _native(
                H("2. Calibración"),
                P(
                    "Las calificaciones de cada área se calibran en un comité con la Gerencia y "
                    "Recursos Humanos antes de comunicarlas. La calificación final se usa para el "
                    "bono anual por desempeño."
                ),
                P("Las consultas se envían a desempeno@acme.example."),
            ),
        ),
    ),
    DocSpec(
        filename="20-constancia-capacitacion.pdf",
        category="mixed",
        title="Constancia de capacitación con sello de recepción",
        pages=(
            _native(
                H("Acme S.A. - Registro de capacitaciones obligatorias"),
                P(
                    "Este documento reúne la constancia de capacitación entregada por la persona y "
                    "su registro en el legajo. La constancia escaneada está en la página 2."
                ),
                P(
                    "Recursos Humanos sella la constancia al recibirla y la carga en el portal "
                    "dentro de los 5 días hábiles."
                ),
            ),
            _scan(
                H("Constancia de capacitación"),
                P(
                    "Se deja constancia de que Pablo Sosa, legajo 6012, completó el curso de "
                    "prevención de riesgos laborales."
                ),
                P("Duración del curso: 8 horas."),
                P("Fecha de aprobación: 28 de octubre de 2026."),
                P("Calificación obtenida: 9 sobre 10."),
                P("Instructora: Valeria Ortiz, Seguridad e Higiene."),
                stamp="RECIBIDO RRHH 02/11/2026",
            ),
        ),
    ),
)
