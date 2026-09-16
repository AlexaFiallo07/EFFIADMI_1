from django.conf import settings
from django.contrib import messages
from django.shortcuts import render, redirect

from .models import MensajeContacto


MODULOS = [
    {
        "slug": "inventario",
        "nombre": "Inventario",
        "icono": "▣",
        "categoria": "Operación",
        "resumen": "Controla productos, existencias y movimientos con disponibilidad clara en tiempo real.",
        "descripcion": (
            "El módulo de Inventario centraliza el control de productos, categorías y existencias "
            "de tu empresa. Cada entrada y salida queda registrada, para que siempre sepas qué tienes "
            "disponible y en qué momento se movió."
        ),
        "caracteristicas": [
            "Registro de productos con categorías y precios.",
            "Control de existencias por sucursal.",
            "Movimientos de entrada y salida con trazabilidad.",
            "Aviso de stock bajo para anticipar compras.",
        ],
        "beneficios": [
            "Evita quedarte sin producto o comprar de más.",
            "Una sola fuente de verdad sobre tu mercancía.",
            "Mantiene el costo y el valor de inventario al día.",
        ],
    },
    {
        "slug": "ventas",
        "nombre": "Ventas",
        "icono": "🛒",
        "categoria": "Operación",
        "resumen": "Registra y administra las ventas del negocio con métricas claras del mes.",
        "descripcion": (
            "El módulo de Ventas te permite registrar cada operación y tener una visión mensual de tu "
            "facturación. Los indicadores del panel te muestran el comportamiento del negocio de forma "
            "inmediata."
        ),
        "caracteristicas": [
            "Registro de ventas con detalle de productos.",
            "Panel con la facturación del mes.",
            "Comparativo de desempeño entre períodos.",
            "Vínculo directo con inventario y facturación.",
        ],
        "beneficios": [
            "Sabes cuánto vendes y cómo cambia mes a mes.",
            "La información llega sin cálculos manuales.",
            "Facilita detectar productos y clientes clave.",
        ],
    },
    {
        "slug": "clientes",
        "nombre": "Clientes",
        "icono": "◉",
        "categoria": "Relación",
        "resumen": "Gestiona la información y el historial de tus clientes desde un solo lugar.",
        "descripcion": (
            "El módulo de Clientes centraliza tus datos de contacto y el historial de operaciones de cada "
            "cliente, para que la atención y el seguimiento sean más ágiles."
        ),
        "caracteristicas": [
            "Ficha completa de cada cliente.",
            "Historial de facturas y pedidos asociados.",
            "Estado activo o inactivo de la relación.",
            "Búsqueda rápida por nombre o documento.",
        ],
        "beneficios": [
            "Atiendas mejor a quien ya te compra.",
            "Agiliza la búsqueda de información en ventas.",
            "Ayuda a conocer la cartera de negocio.",
        ],
    },
    {
        "slug": "proveedores",
        "nombre": "Proveedores",
        "icono": "⛯",
        "categoria": "Relación",
        "resumen": "Administra tus proveedores y los productos que le surten a tu negocio.",
        "descripcion": (
            "El módulo de Proveedores organiza tus aliados comerciales y los productos que ofrecen, "
            "facilitando la gestión de compras y el abastecimiento del inventario."
        ),
        "caracteristicas": [
            "Registro de proveedores con datos de contacto.",
            "Relación de productos que surte cada proveedor.",
            "Consulta rápida de quién provee cada artículo.",
        ],
        "beneficios": [
            "Facilita decidir con quién reabastecer.",
            "Evita la dependencia de información dispersa.",
            "Apoya la negociación con datos claros.",
        ],
    },
    {
        "slug": "pedidos",
        "nombre": "Pedidos",
        "icono": "✓",
        "categoria": "Operación",
        "resumen": "Administra el ciclo de pedidos y facilita el seguimiento de cada operación.",
        "descripcion": (
            "El módulo de Pedidos acompaña cada operación desde su creación hasta su entrega, con estados "
            "claros que permiten saber en qué punto está cada pedido."
        ),
        "caracteristicas": [
            "Creación de pedidos con detalle de productos.",
            "Estados del ciclo: pendiente, en proceso, completado.",
            "Vínculo con clientes e inventario.",
            "Historial completo de cada pedido.",
        ],
        "beneficios": [
            "Ningún pedido queda sin seguimiento.",
            "El equipo sabe siempre qué sigue.",
            "Mejora la confianza con tus clientes.",
        ],
    },
    {
        "slug": "facturacion",
        "nombre": "Facturación",
        "icono": "☰",
        "categoria": "Finanzas",
        "resumen": "Organiza tus comprobantes de venta y la información de cada operación.",
        "descripcion": (
            "El módulo de Facturación registra y organiza los comprobantes de venta de tu empresa, "
            "vinculados con clientes, pedidos e inventario."
        ),
        "caracteristicas": [
            "Generación de facturas con detalle.",
            "Vista de comprobantes e impresión.",
            "Historial ordenado de cada operación.",
            "Integración con ventas y clientes.",
        ],
        "beneficios": [
            "Tienes un registro claro y ordenado.",
            "Menos errores en la documentación.",
            "Facilita la revisión y los reportes.",
        ],
    },
    {
        "slug": "usuarios",
        "nombre": "Usuarios y seguridad",
        "icono": "🔒",
        "categoria": "Control",
        "resumen": "Administra usuarios, roles y el acceso a la información del sistema.",
        "descripcion": (
            "El módulo de Usuarios te permite definir quién accede al sistema y qué rol cumple cada "
            "persona, manteniendo el control sobre la información de la empresa."
        ),
        "caracteristicas": [
            "Perfiles de usuario con rol y datos.",
            "Roles diferenciados (admin y empleado).",
            "Acceso controlado a cada módulo.",
            "Registro y actualización de contraseñas.",
        ],
        "beneficios": [
            "Proteges la información del negocio.",
            "Cada persona ve lo que le corresponde.",
            "Proceso de acceso claro y trazable.",
        ],
    },
    {
        "slug": "notificaciones",
        "nombre": "Notificaciones",
        "icono": "✦",
        "categoria": "Control",
        "resumen": "Recibe avisos automáticos sobre eventos importantes de tu operación.",
        "descripcion": (
            "El módulo de Notificaciones mantiene al equipo al tanto de los momentos importantes: stock "
            "bajo, pedidos nuevos, clientes por visitar y más."
        ),
        "caracteristicas": [
            "Avisos de stock bajo y movimientos críticos.",
            "Alertas de pedidos y facturación.",
            "Configuración de preferencias de aviso.",
        ],
        "beneficios": [
            "Actúas a tiempo frente a lo importante.",
            "Menos revisión manual constante.",
            "El sistema te acompaña en el día a día.",
        ],
    },
    {
        "slug": "reportes",
        "nombre": "Reportes y estadísticas",
        "icono": "⚙",
        "categoria": "Finanzas",
        "resumen": "Consulta reportes y recibe apoyo de un asistente con IA en tus decisiones.",
        "descripcion": (
            "El módulo de Reportes concentra la información de tu negocio en vistas claras y cuenta con un "
            "asistente inteligente que responde sobre tus datos y apoya la toma de decisiones."
        ),
        "caracteristicas": [
            "Indicadores del negocio en el panel.",
            "Reportes por período y área.",
            "Asistente con IA para consultas en lenguaje natural.",
            "Vistas parametrizables según el rol.",
        ],
        "beneficios": [
            "Decisiones con base en información real.",
            "Ahorro de tiempo al preguntar directamente.",
            "Visión integral del negocio en minutos.",
        ],
    },
    {
        "slug": "configuracion",
        "nombre": "Configuración",
        "icono": "◈",
        "categoria": "Control",
        "resumen": "Personaliza la plataforma y organiza tu estructura de sucursales.",
        "descripcion": (
            "El módulo de Configuración permite ajustar la plataforma a tu operación: sucursales, "
            "parámetros generales y preferencias de la empresa."
        ),
        "caracteristicas": [
            "Sucursales por cada punto de operación.",
            "Parámetros generales del sistema.",
            "Preferencias de notificación y presentación.",
        ],
        "beneficios": [
            "La plataforma se adapta a tu empresa.",
            "Estructura clara para crecer.",
            "Menos fricción al incorporar nuevos puntos.",
        ],
    },
]

MODULOS_POR_SLUG = {m["slug"]: m for m in MODULOS}


def _contexto_base(seccion):
    return {
        "seccion": seccion,
        "sistema_login_url": getattr(settings, "SISTEMA_LOGIN_URL", "#"),
    }


def landing(request):
    contexto = _contexto_base("inicio")
    contexto["modulos_destacados"] = MODULOS[:6]
    return render(request, "landing/inicio.html", contexto)


def solucion(request):
    return render(request, "landing/solucion.html", _contexto_base("solucion"))


def modulos(request):
    contexto = _contexto_base("modulos")
    contexto["modulos"] = MODULOS
    return render(request, "landing/modulos.html", contexto)


def modulo(request, slug):
    modulo = MODULOS_POR_SLUG.get(slug)
    if not modulo:
        return redirect("modulos")

    pos = next(i for i, m in enumerate(MODULOS) if m["slug"] == slug)
    contexto = _contexto_base("modulos")
    contexto["modulo"] = modulo
    contexto["modulo_anterior"] = MODULOS[(pos - 1) % len(MODULOS)]
    contexto["modulo_siguiente"] = MODULOS[(pos + 1) % len(MODULOS)]
    contexto["otros_modulos"] = [m for m in MODULOS if m["slug"] != slug][:4]
    return render(request, "landing/modulo.html", contexto)


def proceso(request):
    return render(request, "landing/proceso.html", _contexto_base("proceso"))


def tecnologia(request):
    return render(request, "landing/tecnologia.html", _contexto_base("tecnologia"))


def contacto(request):
    if request.method == "POST":
        nombre = request.POST.get("nombre", "").strip()
        correo = request.POST.get("correo", "").strip()
        asunto = request.POST.get("asunto", "").strip()
        mensaje = request.POST.get("mensaje", "").strip()

        if not all([nombre, correo, mensaje]):
            messages.error(
                request,
                "Por favor completa los campos obligatorios (nombre, correo y mensaje).",
            )
        elif "@" not in correo or "." not in correo:
            messages.error(request, "Ingresa un correo electrónico válido.")
        else:
            MensajeContacto.objects.create(
                nombre=nombre,
                correo=correo,
                asunto=asunto,
                mensaje=mensaje,
            )
            messages.success(
                request,
                "¡Gracias por escribirnos! Hemos recibido tu mensaje y te responderemos pronto.",
            )

        return redirect("contacto")

    return render(request, "landing/contacto.html", _contexto_base("contacto"))