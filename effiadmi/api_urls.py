from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import api_views

router = DefaultRouter()
router.register('productos', api_views.ProductoViewSet)
router.register('proveedores', api_views.ProveedorViewSet)
router.register('clientes', api_views.ClienteViewSet)
router.register('usuarios', api_views.UsuarioViewSet)
router.register('facturas', api_views.FacturaViewSet)
router.register('pedidos', api_views.PedidoViewSet)
router.register('notificaciones', api_views.NotificacionViewSet)
router.register('inventario', api_views.InventarioViewSet)
router.register('movimientos', api_views.MovimientoViewSet)
router.register('dashboard', api_views.DashboardViewSet, basename='dashboard')

urlpatterns = [
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('ia/consultar/', api_views.AsistenteIAView.as_view(), name='ia_consultar'),
]

urlpatterns += router.urls
