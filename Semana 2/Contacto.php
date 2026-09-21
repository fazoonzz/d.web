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
            <button type="button" class="btn btn-outline-info">Acceso</button>    
        </div>
        </nav>
        <!-- Container -->
        <div class="container-fluid">    
            <form action="index.php">
                <div class="mb-2 mt-2">
                    <label for="email" class="form-label">Email:</label>
                    <input type="email" class="form-control" id="email" placeholder="Enter email" name="email">
                </div>
                <label for="comment">Comentarios:</label>
                <textarea class="form-control" rows="5" id="comment" name="text"></textarea>
                <button class="btn btn-primary mt-2" type="submit">Enviar</button>
            </form>
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
                        Modal body..
                    </div>
                    <!-- Modal footer -->
                    <div class="modal-footer">
                        <button type="button" class="btn btn-danger" data-bs-dismiss="modal">Close</button>
                    </div>

                </div>
            </div>
        </div>
    </body>
</html>
