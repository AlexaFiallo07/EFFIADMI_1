(function () {
    "use strict";

    var cabecera = document.getElementById("cabecera");
    var botonMenu = document.getElementById("botonMenu");
    var menuMovil = document.getElementById("menuMovil");
    var volverArriba = document.getElementById("volverArriba");

    // Navbar con sombra al hacer scroll
    function alDesplazar() {
        var scrolled = window.scrollY > 40;
        if (cabecera) cabecera.classList.toggle("al-desplazar", scrolled);

        if (volverArriba) {
            volverArriba.classList.toggle("visible", window.scrollY > 600);
        }
    }

    window.addEventListener("scroll", alDesplazar, { passive: true });
    alDesplazar();

    // Menú móvil
    function cerrarMenu() {
        if (!menuMovil) return;
        menuMovil.classList.remove("abierto");
        if (botonMenu) botonMenu.classList.remove("abierto");
        botonMenu.setAttribute("aria-expanded", "false");
    }

    if (botonMenu && menuMovil) {
        botonMenu.addEventListener("click", function () {
            var abierto = menuMovil.classList.toggle("abierto");
            botonMenu.classList.toggle("abierto", abierto);
            botonMenu.setAttribute("aria-expanded", abierto ? "true" : "false");
        });

        // Cerrar al hacer clic en un enlace
        menuMovil.querySelectorAll("a").forEach(function (enlace) {
            enlace.addEventListener("click", cerrarMenu);
        });
    }

    // Cerrar menú al redimensionar a escritorio
    window.addEventListener("resize", function () {
        if (window.innerWidth > 860) cerrarMenu();
    });

    // Volver arriba
    if (volverArriba) {
        volverArriba.addEventListener("click", function (e) {
            e.preventDefault();
            window.scrollTo({ top: 0, behavior: "smooth" });
        });
    }
})();
