# Despliegue GRATIS en PythonAnywhere

Guía paso a paso para poner EFFIADMI en línea con la cuenta gratuita de
[PythonAnywhere](https://www.pythonanywhere.com). El proyecto ya esta listo
para produccion: solo hay que seguir esta lista en orden.

## Por que esta plataforma

- Disco **persistente**: los archivos que suban los usuarios (`media/`) SI se
  quedan guardados. No hace falta integrar Supabase Storage.
- Gmail SMTP en su lista blanca: los correos del sistema salen de verdad.
- Un solo proceso: la cache `locmem` (candado de login, throttling) funciona
  tal cual. No se necesita Redis.
- Siempre encendido, sin arranques en frio, HTTPS incluido en
  `TUUSUARIO.pythonanywhere.com`.

Limitaciones del plan gratis: 512 MB de disco y ~100 segundos de CPU/dia
(sobra para una demo o un equipo pequeño). Las funciones de IA pueden fallar
si su endpoint no esta en la lista blanca; todo el resto de la app no depende
de eso.

## Paso 0 — Antes de empezar

Ten a mano el `.env` local del proyecto (para copiar `EMAIL_HOST_PASSWORD` y
`GEMINI_API_KEY`).

Genera una SECRET_KEY nueva para produccion (distinta a la local):

```
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Guarda ese texto larguito, se usa en el paso 4.

## Paso 1 — Crear la cuenta y descargar el codigo

1. Crea una cuenta gratis en pythonanywhere.com (cualquier nombre de usuario:
   sera el subdominio, ej. `effiadmi.pythonanywhere.com`).
2. Abre la pestana **Consoles → Bash** y clona el repo:

```
git clone https://github.com/AlexaFiallo07/EFFIADMI_1.git ~/EFFIADMI_1
```

## Paso 2 — Entorno virtual

En la misma consola Bash:

```
mkvirtualenv effiadmi --python=$(which python3.13) || mkvirtualenv effiadmi --python=$(which python3.12)
pip install -r ~/EFFIADMI_1/requirements.txt
```

Importante: Django 6 exige Python 3.12+; usa la version mas alta que ofrezca
el selector del Paso 6.

## Paso 3 — Migraciones y superusuario

```
cd ~/EFFIADMI_1
python manage.py migrate
python manage.py createsuperuser
```

Si `mkvirtualenv` no activo automaticamente: `workon effiadmi` antes.

## Paso 4 — Archivo .env en el servidor

En **Files**, crea `~/EFFIADMI_1/.env` con este contenido (cambia TUUSUARIO y
pega los dos valores copiados del .env local):

```
DEBUG=0
SECRET_KEY=<la clave de 50+ caracteres generada en el Paso 0>
ALLOWED_HOSTS=TUUSUARIO.pythonanywhere.com
GEMINI_API_KEY=<copiala del .env local>

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=effiadmi042@gmail.com
EMAIL_HOST_PASSWORD=<copiala del .env local>
DEFAULT_FROM_EMAIL=effiadmi042@gmail.com
```

OJO: NO pongas `DB_ENGINE=postgres` — sin esa variable la app usa SQLite en
el disco persistente, que es lo que queremos aquí. Nunca subas este archivo
a GitHub (ya esta en `.gitignore`).

## Paso 5 — Archivos estaticos y de usuarios

En la consola Bash (solo la primera vez o cuando cambien estilos):

```
cd ~/EFFIADMI_1 && python manage.py collectstatic --noinput
```

## Paso 6 — Crear la app web

1. **Web → Add a new web app → Manual configuration** (NO el wizard de
   Django; usa la version que ponga de Python).
2. Elije la version de Python mas alta disponible (3.12+).
3. En la seccion **Code**:
   - **Source code**: `/home/TUUSUARIO/EFFIADMI_1`
   - **Working directory**: `/home/TUUSUARIO/EFFIADMI_1`
   - **Virtualenv**: `/home/TUUSUARIO/.virtualenvs/effiadmi`
4. Baja a **Static files** y agrega:

| URL        | Directory                       |
|------------|---------------------------------|
| `/static/` | `/home/TUUSUARIO/EFFIADMI_1/staticfiles` |
| `/media/`  | `/home/TUUSUARIO/EFFIADMI_1/media`       |

5. En **WSGI configuration file** (seccion Code), abre el enlace
   `..._pythonanywhere_com_wsgi.py`, borra TODO y pega:

```python
import os
import sys

sys.path.insert(0, "/home/TUUSUARIO/EFFIADMI_1")

os.environ["DJANGO_SETTINGS_MODULE"] = "base.settings"

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
```

6. Boton verde **Reload** arriba.

Abre `https://TUUSUARIO.pythonanywhere.com` — deberia aparecer la landing y
el login del sistema en `/login/`.

## Ultimos ajustes ( opcionales pero recomendados )

- **Admin Django**: no confundir con el panel auto (el login del sistema es
  `TUUSUARIO.pythonanywhere.com/login/`).
- **Dominio propio**: solo con plan de pago; el subdominio gratuito funciona
  bien para demo/entrega.
- Los correos llegan a `effiadmi042@gmail.com` exactamente igual que en
  local; revisa spam la primera vez y marca "no es spam".

## Actualizar el codigo despues de cambios

```
cd ~/EFFIADMI_1
git pull
pip install -r requirements.txt          # solo si cambio requirements.txt
python manage.py migrate                 # solo si hay migraciones nuevas
python manage.py collectstatic --noinput # solo si cambio CSS/JS/img
```

y **Web → Reload**.
