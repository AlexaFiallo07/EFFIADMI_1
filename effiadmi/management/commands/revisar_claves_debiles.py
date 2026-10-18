"""Detecta y rota cuentas que siguen con una contrasena por defecto.

Las claves tipo 'admin123' quedaron publicadas en el repositorio, asi que
cualquiera que las conozca puede entrar a esas cuentas. Este comando las
localiza y, con --aplicar, las cambia por una aleatoria que se imprime una
sola vez.

Uso:
    python manage.py revisar_claves_debiles            # solo lista
    python manage.py revisar_claves_debiles --aplicar   # rota y muestra
"""

import secrets
import string

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

# Contrasenas conocidas/publicadas o demasiado obvias.
CLAVES_DEBILES = (
    "admin123",
    "admin",
    "administrador",
    "123456",
    "12345678",
    "123456789",
    "password",
    "contrasena",
    "contraseña",
    "qwerty",
    "effiadmi",
)


def clave_aleatoria(longitud=18):
    abecedario = string.ascii_letters + string.digits + "!@#$%*-_"
    return "".join(secrets.choice(abecedario) for _ in range(longitud))


class Command(BaseCommand):
    help = "Lista y (con --aplicar) rota las cuentas con contrasena por defecto."

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Rota las contrasenas debiles; sin esta opcion solo las lista.",
        )

    def handle(self, *args, **options):
        aplicar = options["aplicar"]
        afectados = []

        for usuario in User.objects.all():
            for debil in CLAVES_DEBILES:
                if usuario.check_password(debil):
                    afectados.append((usuario, debil))
                    break

        if not afectados:
            self.stdout.write(self.style.SUCCESS("No se encontraron contrasenas debiles."))
            return

        for usuario, debil in afectados:
            if not aplicar:
                self.stdout.write(
                    self.style.WARNING(
                        f"DEBIL: '{usuario.username}' usa una contrasena por defecto "
                        f"(coincide con una de la lista). Reactiva con --aplicar."
                    )
                )
                continue

            nueva = clave_aleatoria()
            usuario.set_password(nueva)
            usuario.save(update_fields=["password"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"'{usuario.username}' rotada. Nueva contrasena: {nueva} "
                    "(guardala ahora: solo se imprime una vez)."
                )
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Cuentas afectadas: {len(afectados)}."
                if aplicar
                else f"Cuentas a rotar: {len(afectados)}. Ejecuta con --aplicar para cambiar."
            )
        )
