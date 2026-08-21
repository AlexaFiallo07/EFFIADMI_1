from django.shortcuts import redirect
from django.contrib import messages


def autorizacion(roles=[]):
    def verificar_autenticacion(func):
        def envoltorio_func(request, *args, **kwargs):
            # captura de variable de sesion
            validar = request.session.get("logueado", False)
            if validar:
                if roles != [] and validar["rol"] not in roles:
                    messages.warning(request, "No tienes permisos para acceder a esta seccion.")
                    return redirect("effiadmi:inicio")
                return func(request, *args, **kwargs)
            else:
                return redirect("effiadmi:login")

        return envoltorio_func
    return verificar_autenticacion
