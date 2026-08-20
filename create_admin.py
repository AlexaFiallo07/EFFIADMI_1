from effiadmi.models import Usuario

# Verificar si ya existe un usuario Admin
admin_users = Usuario.objects.filter(cargo="Admin")
print(f"Usuarios Admin existentes: {admin_users.count()}")

if admin_users.count() == 0:
    # Crear un usuario Admin
    usuario = Usuario.objects.create(
        nombre_usuario="admin",
        apellido_usuario="sistema",
        email="admin@effiadmi.com",
        contraseña="admin123",
        cargo="Admin"
    )
    print(f"✓ Usuario Admin creado: {usuario}")
else:
    print(f"✓ Usuarios Admin encontrados:")
    for u in admin_users:
        print(f"  - {u.nombre_usuario} ({u.email})")
