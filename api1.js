const API_BASE_URL = "http://localhost:8000/api";

const apiService = {
    async obtenerProductos() {
        const response = await fetch(`${API_BASE_URL}/products`);
        if (!response.ok) {
            throw new Error(`Error en el Gateway: ${response.status}`);
        }
        return await response.json();
    },

    async login(email, password) {
        // Validación local de prueba para acceder al panel
        if ((email === "mail@dulcetentacion.com" || email === "mail@gmail.com") && password === "1234") {
            return { ok: true, usuario: { nombre: "Administrador Dulce Tentación" } };
        }
        if (email === "cliente@dulcetentacion.com" && password === "1234") {
            return { ok: true, usuario: { nombre: "Cliente Frecuente" } };
        }
        return { ok: false, mensaje: "Correo o contraseña incorrectos" };
    }
};
