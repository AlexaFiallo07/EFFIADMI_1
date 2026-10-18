"""Prueba de carga de EFFIADMI con Locust.

Uso:
    pip install -r requirements-dev.txt
    locust -f locustfile.py --host http://127.0.0.1:8000

Abre http://localhost:8089 y define usuarios/hilos. Las credenciales de la API
se pasan por variables de entorno (no hardcodear contrasenas en el repo):

    $env:LOCUST_USER="admin@tudominio.com"; $env:LOCUST_PASSWORD="..."
    locust -f locustfile.py --host http://127.0.0.1:8000

Sin credenciales solo se prueba la landing (peticiones anonimas).
"""

import os

from locust import HttpUser, between, task


class EffiadmiUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.token = None
        usuario = os.getenv("LOCUST_USER")
        clave = os.getenv("LOCUST_PASSWORD")
        if usuario and clave:
            respuesta = self.client.post(
                "/api/token/",
                json={"username": usuario, "password": clave},
                name="POST /api/token/",
            )
            if respuesta.status_code == 200:
                self.token = respuesta.json().get("access")
        self.headers = (
            {"Authorization": f"Bearer {self.token}"} if self.token else {}
        )

    @task(3)
    def landing(self):
        self.client.get("/")

    @task(2)
    def catalogo(self):
        self.client.get("/api/catalogo-productos/", headers=self.headers)

    @task(1)
    def dashboard(self):
        self.client.get("/api/dashboard/estadisticas/", headers=self.headers)
