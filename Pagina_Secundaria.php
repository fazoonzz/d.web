<!DOCTYPE html>
<html lang="en">
   <head>
        <title>Pagina Principal</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css" rel="stylesheet">
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js"></script>   
    </head>
    <body>
        <!-- Navbar -->
        <nav class="navbar navbar-expand-sm bg-dark navbar-dark">
        <div class="container-fluid">
            <a class="navbar-brand" href="index.php">Logo</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#collapsibleNavbar">
            <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="collapsibleNavbar">
            <ul class="navbar-nav">
                <li class="nav-item">
                    <a class="nav-link" href="https://github.com/fazoonzz/d.web">GitHub</a>
                </li>
                <li class="nav-item">
                    <a class="nav-link" href="Pagina_Secundaria.php">Pagina secundaria</a>
                </li>   
                <li class="nav-item dropdown">
                <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">Dropdown</a>
                <ul class="dropdown-menu">
                    <li><a class="dropdown-item" href="#">Quienes somos</a></li>
                    <li><a class="dropdown-item" href="https://github.com/fazoonzz/d.web">GitHub</a></li>
                    <li><a class="dropdown-item" href="#">Contacto</a></li>
                </ul>
                </li>
            </ul>
            </div>
            <div id="contenedorAcceso">
                <button type="button" class="btn btn-outline-info" data-bs-toggle="modal" data-bs-target="#myModal">Acceso</button>
            </div>
        </div>
        </nav>
        <!-- Container -->
        <div class="container-fluid">    
            Pagina secundaria<br>
            <a href="index.php">Volver a la pagina principal</a>

            <div id="seccionProductos" class="d-none mt-4">
                <h3>Productos</h3>
                <table class="table table-striped table-bordered">
                    <thead class="table-dark">
                        <tr>
                            <th>ID</th>
                            <th>Nombre</th>
                            <th>Precio</th>
                        </tr>
                    </thead>
                    <tbody id="tbodyProductos">
                        <!-- Filas generadas dinámicamente con JS -->
                    </tbody>
                </table>
            </div>
        </div>
        <!-- Footer -->
        <div class="container-fluid bg-dark text-light text-center">
            <p><strong>TestPagina1</strong></p>       
        <!-- Modal -->
         <div class="modal fade" id="myModal">
            <div class="modal-dialog">
                <div class="modal-content">
                    <!-- Modal Header -->
                    <div class="modal-header">
                        <h4 class="modal-title">Modal Heading</h4>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <!-- Modal body -->
                    <div class="modal-body">
                        <form onsubmit="iniciarSesion(event)">
                        <div class="mb-2 mt-2">
                            <label for="email" class="form-label">Email:</label>
                            <input type="email" class="form-control" id="email" placeholder="Enter email" name="email">
                        </div>
                        <div class="mb-3">
                            <label for="pwd" class="form-label">Password:</label>
                            <input type="password" class="form-control" id="pwd" placeholder="Enter password" name="pswd">
                        </div>
                        <div class="form-check mb-2">
                            <label class="form-check-label">
                            <input class="form-check-input" type="checkbox" name="remember"> Recordar Usuario
                            </label>
                        </div>
                        <button type="submit" class="btn btn-primary">Ingresar</button>
                        <div id="loginError" class="text-danger mt-2"></div>
                        </form>
                    </div>
                    <!-- Modal footer -->
                    <div class="modal-footer">
                        <button type="button" class="btn btn-danger" data-bs-dismiss="modal">Close</button>
                    </div>

                </div>
            </div>
        </div>

                <!-- Logica de la pagina: datos simulados de API + manipulacion del DOM -->
        <script src="js/api.js"></script>
        <script src="js/main.js"></script>
    </body>
</html>