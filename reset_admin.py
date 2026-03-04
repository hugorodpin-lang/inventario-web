from app import app, db, Usuario, bcrypt

with app.app_context():
    # Buscar usuario admin
    user = Usuario.query.filter_by(username='admin').first()
    
    if user:
        print(f"Usuario encontrado: {user.username}")
        print(f"Activo: {user.activo}")
        print(f"Rol: {user.rol}")
        
        # Resetear contraseña
        nueva_password = bcrypt.generate_password_hash('admin123').decode('utf-8')
        user.password = nueva_password
        user.activo = True
        db.session.commit()
        print("Contraseña reseteada a: admin123")
    else:
        # Crear usuario admin
        hashed = bcrypt.generate_password_hash('admin123').decode('utf-8')
        admin = Usuario(username='admin', password=hashed, nombre='Administrador', rol='admin', activo=True)
        db.session.add(admin)
        db.session.commit()
        print("Usuario admin creado con contraseña: admin123")

