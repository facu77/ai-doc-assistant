"""Set de validación de "Acme S.A.": 6 escaneos para elegir el psm (decisión 5).

Composición fijada antes de medir: 2 documentos a dos columnas, 2 formularios con tabla y
2 textos corridos, mitad escaneo limpio y mitad ruidoso, una página cada uno. Son otros
documentos que los del corpus de prueba. Todo es inventado (ver `content.py`).
"""

from __future__ import annotations

from ingest.corpus.content import Columns, DocSpec, Heading, PageSpec, Para, Row

H = Heading
P = Para


def _scan(*blocks: Heading | Para | Row | Columns) -> PageSpec:
    return PageSpec(kind="scan", blocks=blocks)


VALIDATION_DOCUMENTS: tuple[DocSpec, ...] = (
    DocSpec(
        filename="v01-boletin-interno.pdf",
        category="clean_scan",
        title="Boletín interno de noviembre",
        pages=(
            _scan(
                H("Acme S.A. - Boletín interno, noviembre de 2026"),
                Columns(
                    left=(
                        H("Novedades de Recursos Humanos"),
                        P(
                            "Desde el 1 de diciembre el portal de autogestión permite descargar "
                            "el certificado de trabajo sin pedirlo por correo."
                        ),
                        P(
                            "La encuesta de clima laboral cierra el 5 de diciembre. Respondieron "
                            "412 personas, el 68% de la dotación."
                        ),
                        P(
                            "El programa de referidos paga $ 250.000 por cada ingreso que supere "
                            "el período de prueba."
                        ),
                    ),
                    right=(
                        H("Agenda del mes"),
                        P(
                            "Martes 3: charla de educación financiera en el auditorio, de 13 a 14 "
                            "horas."
                        ),
                        P(
                            "Jueves 12: colecta de juguetes para un comedor del barrio, en la "
                            "recepción de cada sede."
                        ),
                        P(
                            "Viernes 20: brindis de fin de año en la terraza de la sede central, "
                            "a partir de las 18 horas."
                        ),
                    ),
                ),
                P(
                    "Para sumar una novedad al próximo boletín, escribí a comunicacion@acme.example."
                ),
            ),
        ),
    ),
    DocSpec(
        filename="v02-planilla-horas-extra.pdf",
        category="clean_scan",
        title="Planilla de horas extra de octubre",
        pages=(
            _scan(
                H("Acme S.A. - Formulario RH-15"),
                H("Planilla de horas extra"),
                P("Empleado: Hernán Vega"),
                P("Legajo: 2864"),
                P("Área: Depósito central"),
                Row(cells=("Fecha", "Horas", "Motivo")),
                Row(cells=("07/10/2026", "2,5", "Inventario")),
                Row(cells=("14/10/2026", "3", "Recepción de mercadería")),
                Row(cells=("21/10/2026", "1,5", "Despacho urgente")),
                Row(cells=("28/10/2026", "4", "Cierre de mes")),
                P("Total de horas extra: 11"),
                P("Autorizó: Marina Sosa, jefa de Depósito"),
            ),
        ),
    ),
    DocSpec(
        filename="v03-memo-feriados.pdf",
        category="clean_scan",
        title="Memo de feriados y días no laborables 2027",
        pages=(
            _scan(
                H("Acme S.A. - Memo interno RH-2026-047"),
                P("Para: todo el personal"),
                P("Asunto: feriados y días no laborables de 2027"),
                P(
                    "Los días no laborables que fije el calendario oficial de 2027 se otorgan a "
                    "todo el personal de oficinas. El personal de planta mantiene los turnos que "
                    "organice cada supervisor y cobra el adicional correspondiente."
                ),
                P(
                    "El 24 y el 31 de diciembre de 2026 la jornada termina a las 13 horas en "
                    "todas las sedes."
                ),
                P("Las consultas se envían a personas@acme.example."),
            ),
        ),
    ),
    DocSpec(
        filename="v04-solicitud-reintegro-guarderia.jpg",
        category="noisy_scan",
        title="Solicitud de reintegro de guardería",
        pages=(
            _scan(
                H("Acme S.A. - Formulario RH-18"),
                H("Solicitud de reintegro de guardería"),
                P("Empleada: Rocío Aguirre"),
                P("Legajo: 7215"),
                P("Hijo: Bruno Aguirre, 2 años"),
                Row(cells=("Mes", "Importe pagado")),
                Row(cells=("Agosto 2026", "$ 98.000")),
                Row(cells=("Septiembre 2026", "$ 98.000")),
                Row(cells=("Octubre 2026", "$ 104.500")),
                P("Total solicitado: $ 300.500"),
                P("Tope mensual vigente: $ 120.000 por hijo"),
            ),
        ),
    ),
    DocSpec(
        filename="v05-guia-rapida-beneficios.pdf",
        category="noisy_scan",
        title="Guía rápida de beneficios para nuevos ingresos",
        pages=(
            _scan(
                H("Acme S.A. - Guía rápida de beneficios"),
                Columns(
                    left=(
                        H("Salud y bienestar"),
                        P("Prepaga plan 310 para vos y tu grupo familiar primario, sin costo."),
                        P("Reintegro del 50% del gimnasio, con un tope de $ 25.000 por mes."),
                        P("Día libre en tu cumpleaños."),
                    ),
                    right=(
                        H("Desarrollo"),
                        P("Presupuesto anual de capacitación de $ 600.000 por persona."),
                        P("Clases de inglés y portugués en la oficina, sin costo."),
                        P("Hasta 4 horas por semana para estudiar en horario laboral."),
                    ),
                ),
            ),
        ),
    ),
    DocSpec(
        filename="v06-aviso-mantenimiento-edificio.pdf",
        category="noisy_scan",
        title="Aviso de mantenimiento del edificio",
        pages=(
            _scan(
                H("Acme S.A. - Aviso de Servicios Generales"),
                H("Corte programado de energía"),
                P(
                    "El sábado 12 de diciembre de 2026, de 8 a 16 horas, se hará el mantenimiento "
                    "anual del tablero eléctrico de la sede central."
                ),
                P(
                    "Durante ese horario no habrá energía ni acceso al edificio. Los servidores "
                    "del centro de datos funcionan con el generador de respaldo."
                ),
                P(
                    "Si necesitás retirar algo antes, avisá a servicios@acme.example hasta el "
                    "jueves 10 de diciembre."
                ),
            ),
        ),
    ),
)
