"""
WSGI config for inventory web application on Render.
"""

from app import app, db, crear_tablas

# Inicializar la aplicación
if __name__ == "__main__":
    app.run()

