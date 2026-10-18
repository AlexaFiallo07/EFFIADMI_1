"""Carga un respaldo JSON (dumpdata) y reinicia las secuencias de autoincremento.

Al migrar de SQLite a Supabase/Postgres los IDs se cargan explicitos. En
Postgres el contador interno (secuencia) NO se actualiza solo, asi que el
primer INSERT nuevo intentaria reusar una PK ya existente y fallaria. Este
comando carga el respaldo y luego ejecuta el SQL de sqlsequencereset para
dejar los contadores a tono.

Uso:
    # 1) En el entorno actual (SQLite):
    python manage.py dumpdata --natural-foreign --indent 2 \
        -e contenttypes -e auth.permission -e auth.group -e admin -e sessions \
        -o respaldo.json

    # 2) Tras configurar DB_ENGINE=postgres en el .env:
    python manage.py migrate
    python manage.py restaurar_respaldo respaldo.json
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Carga un respaldo JSON y reinicia las secuencias de autoincremento."

    def add_arguments(self, parser):
        parser.add_argument("ruta", help="Archivo JSON generado con 'manage.py dumpdata'.")

    def handle(self, *args, **options):
        ruta = options["ruta"]

        self.stdout.write(f"Cargando respaldo desde: {ruta}")
        call_command("loaddata", ruta, verbosity=1)

        sql = call_command(
            "sqlsequencereset", "auth", "effiadmi", "landing", verbosity=0
        )
        sentencias = [s.strip() for s in sql.split(";") if s.strip()]

        if not sentencias:
            self.stdout.write(self.style.WARNING("No hay secuencias que reiniciar."))
            return

        with connection.cursor() as cursor:
            for sentencia in sentencias:
                cursor.execute(sentencia)

        self.stdout.write(
            self.style.SUCCESS(f"Secuencias reiniciadas correctamente: {len(sentencias)}.")
        )
