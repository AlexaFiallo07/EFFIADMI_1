import ipaddress
import re

_RUTA_ADMIN_VALIDA = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def normalizar_ruta_admin(valor):
    ruta = (valor or "admin").strip().strip("/")
    if not _RUTA_ADMIN_VALIDA.fullmatch(ruta):
        raise RuntimeError(
            "ADMIN_URL invalida: usa solo letras, numeros, guion o guion bajo "
            "(ej. gestion-7f3a)."
        )
    return f"{ruta}/"


def parsear_redes_admin(valor):
    redes = []
    for entrada in (valor or "").split(","):
        entrada = entrada.strip()
        if not entrada:
            continue
        try:
            redes.append(ipaddress.ip_network(entrada, strict=False))
        except ValueError as exc:
            raise RuntimeError(
                f"ADMIN_ALLOWED_IPS contiene una IP/CIDR invalida: {entrada}"
            ) from exc
    return tuple(redes)


def ip_en_redes(ip, redes):
    try:
        direccion = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(direccion in red for red in redes)
