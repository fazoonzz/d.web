<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Pastelería Dulce Tentación - Inicio</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css" rel="stylesheet">
    <style>
        :root {
            --cafe-pasteleria: #6F4E37;
            --fondo-pagina: #F8F9FA;
            --texto-principal: #2B2B2B;
        }
        body {
            background-color: var(--fondo-pagina);
            color: var(--texto-principal);
            font-family: system-ui, -apple-system, sans-serif;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        .navbar-custom {
            background-color: var(--cafe-pasteleria);
        }
        .btn-cafe {
            background-color: var(--cafe-pasteleria);
            color: #fff;
        }
        .btn-cafe:hover {
            background-color: #563c2a;
            color: #fff;
        }
        .carousel-item img {
            height: 380px;
            object-fit: cover;
            border-radius: 10px;
        }
        .ad-box {
            border: 2px dashed #bbb;
            background-color: #eee;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            color: #777;
            letter-spacing: 2px;
            border-radius: 8px;
        }
        .comments-box {
            max-height: 260px;
            overflow-y: auto;
            border: 1px solid #dee2e6;
            background: #fff;
            border-radius: 8px;
        }
        .footer-custom {
            background-color: #212529;
            color: #ccc;
            margin-top: auto;
        }
    </style>
</head>
<body>

    <!-- Navbar -->
    <nav class="navbar navbar-expand-lg navbar-dark navbar-custom py-2 shadow-sm">
        <div class="container">
            <a class="navbar-brand fw-bold fs-4" href="index1.0.php">Dulce Tentación</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navMenu">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navMenu">
                <ul class="navbar-nav me-auto mb-2 mb-lg-0">
                    <li class="nav-item"><a class="nav-link active" href="index1.0.php">Inicio</a></li>
                    <li class="nav-item"><a class="nav-link" href="Pagina_Secundaria1.0.php">Catálogo</a></li>
                    <li class="nav-item"><a class="nav-link" href="carousel1.0.php">Destacados</a></li>
                    <li class="nav-item"><a class="nav-link" href="Contacto1.0.php">Contacto</a></li>
                </ul>
                <div id="contenedorAcceso">
                    <button type="button" class="btn btn-outline-light" data-bs-toggle="modal" data-bs-target="#myModal">
                        <i class="bi bi-person-fill"></i> Acceso
                    </button>
                </div>
            </div>
        </div>
    </nav>

    <!-- Contenedor Principal -->
    <main class="container my-4">
        
        <!-- Carrusel de Ofertas -->
        <div class="card p-3 border-0 shadow-sm mb-4 bg-white">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <h4 class="m-0 fw-bold">Ofertas de la Semana</h4>
            </div>

            <div id="carouselOfertas" class="carousel slide" data-bs-ride="carousel">
                <div class="carousel-indicators">
                    <button type="button" data-bs-target="#carouselOfertas" data-bs-slide-to="0" class="active"></button>
                    <button type="button" data-bs-target="#carouselOfertas" data-bs-slide-to="1"></button>
                    <button type="button" data-bs-target="#carouselOfertas" data-bs-slide-to="2"></button>
                </div>
                <div class="carousel-inner">
                    <div class="carousel-item active">
                        <img src="img/Torta1.jpg" class="d-block w-100" alt="Torta Chocolate">
                        <div class="carousel-caption d-none d-md-block bg-dark bg-opacity-50 p-2 rounded">
                            <h5>Torta Suprema de Chocolate</h5>
                        </div>
                    </div>
                    <div class="carousel-item">
                        <img src="img/Torta2.JPG" class="d-block w-100" alt="Deliciosa Torta de Piña">
                        <div class="carousel-caption d-none d-md-block bg-dark bg-opacity-50 p-2 rounded">
                            <h5>Deliciosa Torta de Piña</h5>
                        </div>
                    </div>
                    <div class="carousel-item">
                        <img src="https://images.unsplash.com/photo-1588195538326-c5b1e9f80a1b?w=1200&auto=format&fit=crop&q=80" class="d-block w-100" alt="Pastel Cumpleaños">
                        <div class="carousel-caption d-none d-md-block bg-dark bg-opacity-50 p-2 rounded">
                            <h5>Tortas Personalizadas para Eventos</h5>
                        </div>
                    </div>
                </div>
                <button class="carousel-control-prev" type="button" data-bs-target="#carouselOfertas" data-bs-slide="prev">
                    <span class="carousel-control-prev-icon"></span>
                </button>
                <button class="carousel-control-next" type="button" data-bs-target="#carouselOfertas" data-bs-slide="next">
                    <span class="carousel-control-next-icon"></span>
                </button>
            </div>
            
            <div class="d-flex justify-content-between align-items-center mt-3 text-muted small px-1">
                <span><i class="bi bi-info-circle"></i> Envío gratis a domicilio dentro de 3 km a la redonda (Maipú).</span>
            </div>
        </div>

        <!-- Fila de Comentarios -->
        <div class="row g-4 mb-4">
            <div class="col-lg-8">
                <div class="card p-3 border-0 shadow-sm bg-white h-100">
                    <h5 class="fw-bold mb-3"><i class="bi bi-chat-square-text"></i> Comentarios de Clientes</h5>
                    <div class="comments-box p-3">
                        <div class="border-bottom pb-2 mb-2">
                            <div class="d-flex justify-content-between">
                                <strong><i class="bi bi-person-circle"></i> Marcela Soto</strong>
                                <span class="text-warning">4.5/5 ★</span>
                            </div>
                            <p class="m-0 small text-secondary">"La torta cuatro leches estaba perfecta, muy fresca y llegó a la hora acordada a mi casa."</p>
                            <span class="badge bg-light text-dark border mt-1">Compró: Torta Cuatro Leches</span>
                        </div>
                        <div class="border-bottom pb-2 mb-2">
                            <div class="d-flex justify-content-between">
                                <strong><i class="bi bi-person-circle"></i> Ignacio Vega</strong>
                                <span class="text-warning">4.8/5 ★</span>
                            </div>
                            <p class="m-0 small text-secondary">"Excelente calidad el cheesecake."</p>
                            <span class="badge bg-light text-dark border mt-1">Compró: Cheesecake Frambuesa</span>
                        </div>
                        <div>
                            <div class="d-flex justify-content-between">
                                <strong><i class="bi bi-person-circle"></i> Camila Durán</strong>
                                <span class="text-warning">4.5/5 ★</span>
                            </div>
                            <p class="m-0 small text-secondary">"El pie de limón tiene el punto justo de acidez y merengue firme. Volveré a pedir."</p>
                            <span class="badge bg-light text-dark border mt-1">Compró: Pie de Limón</span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- AD Lateral -->
            <div class="col-lg-4">
                <div class="ad-box h-100 p-4 text-center">
                    <div>
                        <div class="fs-1 text-secondary mb-2"><i class="bi bi-megaphone"></i></div>
                        <h5>ESPACIO PUBLICITARIO</h5>
                        <p class="small text-muted m-0">Promoción del mes: 15% dcto en tortas temáticas con reserva previa.</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Sección de Catálogo dinámico vía API Gateway -->
        <div id="seccionProductos" class="card border-0 shadow-sm p-4 bg-white d-none mb-4">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h4 class="fw-bold m-0"><i class="bi bi-basket"></i> Productos Disponibles (FastAPI / Gateway)</h4>
                <span class="badge bg-success">Conectado a puerto 8000</span>
            </div>
            <div class="table-responsive">
                <table class="table table-hover align-middle">
                    <thead class="table-dark">
                        <tr>
                            <th style="width: 15%">Código</th>
                            <th style="width: 60%">Producto</th>
                            <th style="width: 25%">Precio</th>
                        </tr>
                    </thead>
                    <tbody id="tbodyProductos"></tbody>
                </table>
            </div>
        </div>

    </main>

    <!-- Footer  -->
    <footer class="footer-custom py-4">
        <div class="container">
            <div class="row align-items-center g-3">
                <!-- Redes Sociales -->
                <div class="col-md-4 text-center text-md-start">
                    <span class="fw-semibold d-block mb-2 text-white">Social Media:</span>
                    <a href="#" class="text-light fs-5 me-3"><i class="bi bi-instagram"></i></a>
                    <a href="#" class="text-light fs-5 me-3"><i class="bi bi-facebook"></i></a>
                    <a href="#" class="text-light fs-5 me-3"><i class="bi bi-tiktok"></i></a>
                    <a href="https://github.com/fazoonzz/d.web" class="text-light fs-5"><i class="bi bi-github"></i></a>
                </div>

                <div class="col-md-4 text-center">
                    <ul class="list-unstyled m-0 small">
                        <li><a href="#" class="text-secondary text-decoration-none">Trabaja con nosotros</a></li>
                        <li><a href="#" class="text-secondary text-decoration-none">Quiénes somos</a></li>
                        <li><a href="Contacto2.php" class="text-secondary text-decoration-none">Políticas de Delivery</a></li>
                    </ul>
                </div>

                <!-- Logo Footer -->
                <div class="col-md-4 text-center text-md-end">
                    <div class="border d-inline-block px-3 py-2 rounded text-white fw-bold">
                         DULCE TENTACIÓN
                    </div>
                </div>
            </div>
            <hr class="border-secondary my-3">
            <p class="text-center text-secondary small m-0"> Pastelería Dulce Tentación </p>
        </div>
    </footer>

    <!-- Modal Login -->
    <div class="modal fade" id="myModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content border-0 shadow">
                <div class="modal-header navbar-custom text-white">
                    <h5 class="modal-title fw-bold">Acceso de Clientes</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body p-4">
                    <form onsubmit="iniciarSesion(event)">
                        <div class="mb-3">
                            <label for="email" class="form-label fw-semibold small">Correo Electrónico:</label>
                            <input type="email" class="form-control" id="email" placeholder="cliente@dulcetentacion.cl" required>
                        </div>
                        <div class="mb-3">
                            <label for="pwd" class="form-label fw-semibold small">Contraseña:</label>
                            <input type="password" class="form-control" id="pwd" placeholder="••••••••" required>
                        </div>
                        <div class="form-check mb-3">
                            <input class="form-check-input" type="checkbox" id="remember">
                            <label class="form-check-label small" for="remember">Recuérdame</label>
                        </div>
                        <button type="submit" class="btn btn-cafe w-100 py-2 fw-semibold">Ingresar</button>
                        <div id="loginError" class="text-danger mt-2 text-center small fw-semibold"></div>
                    </form>

                    <!-- Banners AD dentro del pop-up (Sketch 3) -->
                    <div class="row g-2 mt-3 pt-3 border-top">
                        <div class="col-6">
                            <div class="ad-box py-2 small">AD 1: Delivery</div>
                        </div>
                        <div class="col-6">
                            <div class="ad-box py-2 small">AD 2: Postres</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="api1.js"></script>
    <script src="main1.js"></script>
</body>
</html>