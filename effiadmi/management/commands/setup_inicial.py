from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from effiadmi.models import UserProfile, Branch


class Command(BaseCommand):
    help = "Crea el usuario administrador de prueba y la sucursal principal si no existen."

    def handle(self, *args, **options):
        email = "admin@example.com"
        password = "admin123"

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
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Usuario '{email}' creado exitosamente."))
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
