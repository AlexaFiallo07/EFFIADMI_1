from django.contrib import admin
from django.shortcuts import redirect
from django.contrib import messages


class AdminProtegido(admin.AdminSite):
    """AdminSite personalizado que requiere autenticación con el sistema personalizado"""
    site_header = "Panel de Administración EFFIADMI"
    site_title = "EFFIADMI Admin"
    index_title = "Bienvenido al panel de administración"
    
    def has_permission(self, request):
        """Verifica que el usuario esté autenticado y sea Admin"""
        # Verificar si el usuario está logueado en la sesión personalizada
        usuario_sesion = request.session.get("logueado")
        if not usuario_sesion:
            return False
        
        # Verificar si el usuario es Admin
        rol = usuario_sesion.get("rol")
        return rol == "Admin"
    
    def login(self, request, extra_context=None):
        """Redirige al login personalizado si no está autenticado"""
        if not request.session.get("logueado"):
            messages.error(request, "Debes estar logueado como Administrador para acceder.")
            return redirect("effiadmi:login")
        
        # Si llegó aquí, está logueado pero no es Admin
        messages.error(request, "Solo los administradores pueden acceder al panel de admin.")
        return redirect("effiadmi:inicio")


# Instancia global del AdminSite personalizado
admin_site = AdminProtegido()
