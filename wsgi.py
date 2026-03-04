"""
WSGI config for inventory web application on Render.
"""

from app import app, db

# Inicializar tablas en producción al iniciar
with app.app_context():
    try:
        db.create_all()
        print("Tablas creadas exitosamente")
        
        # Crear admin si no existe
        from app import Usuario, bcrypt
        if not Usuario.query.filter_by(username='admin').first():
            hashed = bcrypt.generate_password_hash('admin123').decode('utf-8')
            admin = Usuario(username='admin', password=hashed, nombre='Administrador', rol='admin')
            db.session.add(admin)
            db.session.commit()
            print("Usuario admin creado (admin/admin123)")
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")

if __name__ == "__main__":
    app.run()

