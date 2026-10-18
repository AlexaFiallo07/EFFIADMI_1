import secrets
import string

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from effiadmi.models import UserProfile, Branch


def password_aleatoria(longitud=18):
    abecedario = string.ascii_letters + string.digits
    # Sin simbolos: el password viaja impreso en consola y los copiamos/pegamos.
    return "".join(secrets.choice(abecedario) for _ in range(longitud))


class Command(BaseCommand):
    help = "Crea el usuario administrador (password aleatoria) y la sucursal principal si no existen."

    def handle(self, *args, **options):
        email = "admin@example.com"

        user, created_user = User.objects.get_or_create(
            username=email,
            defaults={
                "email": email,
                "first_name": "Admin",
                "last_name": "Prueba",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        if created_user:
            password = password_aleatoria()
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Usuario '{email}' creado exitosamente."))
            self.stdout.write(self.style.WARNING(f"Password generada: {password}"))
            self.stdout.write("Guardala ahora: solo se imprime una vez.")
        elif user.check_password("admin123"):
            # Rotacion: la password por defecto estaba publicada en el repo.
            password = password_aleatoria()
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.WARNING(
                f"'{email}' tenia la password por defecto 'admin123'; fue rotada."
            ))
            self.stdout.write(self.style.WARNING(f"Password nueva: {password}"))
        else:
            self.stdout.write(f"Usuario '{email}' ya existe, omitiendo.")

        UserProfile.objects.get_or_create(
            user=user,
            defaults={"cargo": "admin"},
        )

        Branch.objects.get_or_create(
            nombre="Sucursal Principal",
            defaults={"direccion": "Direccion Principal", "es_principal": True},
        )

        self.stdout.write(self.style.SUCCESS("Datos iniciales listos."))
