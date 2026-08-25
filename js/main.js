// main.js
// Lógica de manipulación de elementos HTML y objetos.
// Depende de que api.js se cargue ANTES que este archivo,
// ya que usa las constantes respuestaUsuarios y respuestaProductos.

const TIEMPO_SESION_MS = 180000; // sesión activa por 180 segundos
let temporizadorLogout = null;

// Recorre el arreglo de objetos "data" y crea filas <tr> en la tabla
function cargarProductos() {
    let tbody = document.getElementById("tbodyProductos");
    tbody.innerHTML = "";

    respuestaProductos.data.forEach((producto) => {
        let fila = document.createElement("tr");

        let celdaId = document.createElement("td");
        celdaId.innerText = producto.id;

        let celdaNombre = document.createElement("td");
        celdaNombre.innerText = producto.nombre;

        let celdaPrecio = document.createElement("td");
        celdaPrecio.innerText = "$" + producto.precio.toLocaleString("es-CL");

        fila.appendChild(celdaId);
        fila.appendChild(celdaNombre);
        fila.appendChild(celdaPrecio);
        tbody.appendChild(fila);
    });
}

// Muestra la sección de productos y carga los datos en la tabla
function mostrarProductos() {
    document.getElementById("seccionProductos").classList.remove("d-none");
    cargarProductos();
}

// Oculta la sección de productos y limpia la tabla
function ocultarProductos() {
    document.getElementById("seccionProductos").classList.add("d-none");
    document.getElementById("tbodyProductos").innerHTML = "";
}

// Valida el login contra el arreglo de usuarios simulado
function iniciarSesion(event) {
    event.preventDefault();

    let email = document.getElementById("email").value;
    let pswd = document.getElementById("pwd").value;
    let divError = document.getElementById("loginError");

    let usuario = respuestaUsuarios.data.find((u) => u.email === email && u.pswd === pswd);

    if (usuario) {
        divError.innerText = "";

        let modalEl = document.getElementById("myModal");
        let modal = bootstrap.Modal.getInstance(modalEl);
        modal.hide();

        mostrarSesionActiva(usuario.nombre);
        iniciarTemporizadorLogout();
        mostrarProductos();
    } else {
        divError.innerText = "Email o contraseña incorrectos";
    }
}

// Reemplaza el botón "Acceso" por el saludo + botón "Cerrar sesión"
function mostrarSesionActiva(nombre) {
    let contenedor = document.getElementById("contenedorAcceso");
    contenedor.innerHTML = "";

    let spanBienvenida = document.createElement("span");
    spanBienvenida.classList.add("text-light", "me-2");
    spanBienvenida.innerText = "Hola, " + nombre;

    let btnLogout = document.createElement("button");
    btnLogout.setAttribute("type", "button");
    btnLogout.classList.add("btn", "btn-outline-danger");
    btnLogout.innerText = "Cerrar sesion";
    btnLogout.onclick = cerrarSesion;

    contenedor.appendChild(spanBienvenida);
    contenedor.appendChild(btnLogout);
}

// Arranca (o reinicia) el temporizador de expiración de sesión
function iniciarTemporizadorLogout() {
    if (temporizadorLogout) clearTimeout(temporizadorLogout);
    temporizadorLogout = setTimeout(() => {
        alert("Su sesion ha expirado por tiempo de inactividad");
        cerrarSesion();
    }, TIEMPO_SESION_MS);
}

// Vuelve a mostrar el botón "Acceso" y limpia el temporizador
function cerrarSesion() {
    if (temporizadorLogout) clearTimeout(temporizadorLogout);
    temporizadorLogout = null;

    ocultarProductos();

    let contenedor = document.getElementById("contenedorAcceso");
    contenedor.innerHTML = "";

    let btnAcceso = document.createElement("button");
    btnAcceso.setAttribute("type", "button");
    btnAcceso.classList.add("btn", "btn-outline-info");
    btnAcceso.setAttribute("data-bs-toggle", "modal");
    btnAcceso.setAttribute("data-bs-target", "#myModal");
    btnAcceso.innerText = "Acceso";

    contenedor.appendChild(btnAcceso);
}
