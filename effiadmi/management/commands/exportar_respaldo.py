"""Exporta los datos de la BD activa a un respaldo JSON en UTF-8.

`manage.py dumpdata --output` abre el archivo sin codificacion explicita, asi
que en Windows escribe en la codificacion del sistema (cp1252). Al restaurar
ese archivo con `loaddata` (que lee UTF-8) sale un `UnicodeDecodeError`. Este
comando serializa en memoria y escribe con UTF-8 forzado, asi que el respaldo
funciona igual entre SQLite y Postgres/Supabase.

Se excluyen contenttypes, permisos, grupos, admin y sesiones: los regenera
`manage.py migrate`, y cargarlos produciria conflictos de clave primaria.

Uso:
    python manage.py exportar_respaldo respaldo.json

Para restaurar en otra BD:
    python manage.py migrate
    python manage.py restaurar_respaldo respaldo.json
"""

import io

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

EXCLUIDOS = (
    "contenttypes",
    "auth.permission",
    "auth.group",
    "admin",
    "sessions",
)


class Command(BaseCommand):
    help = "Exporta la BD activa a un respaldo JSON en UTF-8."

    def add_arguments(self, parser):
        parser.add_argument("ruta", help="Archivo de salida (por ejemplo: respaldo.json).")

    def handle(self, *args, **options):
        ruta = options["ruta"]
        buffer = io.StringIO()

        call_command(
            "dumpdata",
            "--natural-foreign",
            "--indent",
            "2",
            *sum((["-e", e] for e in EXCLUIDOS), []),
            stdout=buffer,
            stderr=io.StringIO(),
        )

        try:
            with open(ruta, "w", encoding="utf-8", newline="") as archivo:
                archivo.write(buffer.getvalue())
        except OSError as error:
            raise CommandError(f"No se pudo escribir el respaldo: {error}")

        self.stdout.write(
            self.style.SUCCESS(f"Respaldo exportado en UTF-8: {ruta}")
        )
