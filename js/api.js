// api.js
// Simula las respuestas que normalmente vendrían de un backend/API real.
// Al estar separado, el día de mañana basta con reemplazar estos datos
// por un fetch()/AJAX real sin tocar la lógica de main.js.

// --- Simulación de respuesta de API: usuarios válidos ---
const respuestaUsuarios = {
    "status": 200,
    "message": "Usuarios obtenidos correctamente",
    "data": [
        { "email": "admin@test.cl", "pswd": "1234", "nombre": "Administrador" },
        { "email": "juan@test.cl", "pswd": "abcd", "nombre": "Juan Perez" }
    ]
};

// --- Simulación de respuesta de API: productos ---
const respuestaProductos = {
    "status": 200,
    "message": "Productos obtenidos correctamente",
    "data": [
        { "id": 1, "nombre": "Teclado", "precio": 4590 },
        { "id": 2, "nombre": "Mouse", "precio": 6000 },
        { "id": 3, "nombre": "Monitor", "precio": 89990 },
        { "id": 4, "nombre": "Notebook", "precio": 459990 }
    ]
};
