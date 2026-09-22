const TIEMPO_SESION_MS = 180000;
let temporizadorLogout = null;


async function cargarProductos() {
    const tbody = document.getElementById("tbodyProductos");
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">Consultando API Gateway...</td></tr>`;

    try {
        const data = await apiService.obtenerProductos();
        const productos = data.products || data;

        tbody.innerHTML = "";
        productos.forEach((p) => {
            const fila = document.createElement("tr");
            const precio = p.price !== undefined ? p.price : p.precio;
            fila.innerHTML = `
                <td><strong>${p.id}</strong></td>
                <td>${p.name}</td>
                <td>$${Number(precio).toLocaleString("es-CL")}</td>
            `;
            tbody.appendChild(fila);
        });
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="3" class="text-danger text-center">Error al conectar con API Gateway (${error.message})</td></tr>`;
    }
}

function mostrarProductos() {
    const sec = document.getElementById("seccionProductos");
    if (sec) sec.classList.remove("d-none");
    cargarProductos();
}

function ocultarProductos() {
    const sec = document.getElementById("seccionProductos");
    if (sec) sec.classList.add("d-none");
    const tbody = document.getElementById("tbodyProductos");
    if (tbody) tbody.innerHTML = "";
}

async function iniciarSesion(event) {
    event.preventDefault();
    const email = document.getElementById("email").value;
    const pswd = document.getElementById("pwd").value;
    const divError = document.getElementById("loginError");

    const res = await apiService.login(email, pswd);
    if (res.ok) {
        divError.innerText = "";
        const modalEl = document.getElementById("myModal");
        const modal = bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();

        mostrarSesionActiva(res.usuario.nombre);
        iniciarTemporizadorLogout();
        mostrarProductos();
    } else {
        divError.innerText = res.mensaje;
    }
}

function mostrarSesionActiva(nombre) {
    const contenedor = document.getElementById("contenedorAcceso");
    if (!contenedor) return;
    contenedor.innerHTML = `
        <span class="text-light me-2 small">Hola, ${nombre}</span>
        <button type="button" class="btn btn-outline-danger btn-sm" onclick="cerrarSesion()">Cerrar sesión</button>
    `;
}

function iniciarTemporizadorLogout() {
    if (temporizadorLogout) clearTimeout(temporizadorLogout);
    temporizadorLogout = setTimeout(() => {
        alert("Su sesión ha expirado");
        cerrarSesion();
    }, TIEMPO_SESION_MS);
}

function cerrarSesion() {
    if (temporizadorLogout) clearTimeout(temporizadorLogout);
    temporizadorLogout = null;
    ocultarProductos();
    const contenedor = document.getElementById("contenedorAcceso");
    if (contenedor) {
        contenedor.innerHTML = `
            <button type="button" class="btn btn-outline-light" data-bs-toggle="modal" data-bs-target="#myModal">
                <i class="bi bi-person-fill"></i> Acceso
            </button>
        `;
    }
}
