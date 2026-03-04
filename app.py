import os
import json
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from datetime import datetime

# Configuración de la empresa
EMPRESA_CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'empresa_config.json')

def cargar_config_empresa():
    """Carga la configuración de la empresa desde un archivo JSON"""
    if os.path.exists(EMPRESA_CONFIG_FILE):
        with open(EMPRESA_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'nombre': 'Mi Empresa',
        'direccion': '',
        'telefono': '',
        'email': '',
        'ruc': '',
        'logo': None
    }

def guardar_config_empresa(config):
    """Guarda la configuración de la empresa en un archivo JSON"""
    with open(EMPRESA_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

app = Flask(__name__)

# Configuración de base de datos - funciona local y en producción
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///inventario.db')
if DATABASE_URL and DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Forzar PostgreSQL en producción (Render)
import os
RENDER_DB_URL = os.environ.get('RENDER_DB_URL')
if RENDER_DB_URL:
    DATABASE_URL = RENDER_DB_URL.replace('postgres://', 'postgresql://', 1)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tu_clave_secreta_aqui_12345')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ==================== MODELOS ====================

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    rol = db.Column(db.String(50), default='empleado')  # admin, empleado
    nombre = db.Column(db.String(100))
    activo = db.Column(db.Boolean, default=True)

class Categoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    descripcion = db.Column(db.String(200))
    productos = db.relationship('Producto', backref='categoria', lazy=True)

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(50), unique=True, nullable=False)
    nombre = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'))
    precio_compra = db.Column(db.Float, default=0)
    precio_venta = db.Column(db.Float, default=0)
    stock_actual = db.Column(db.Integer, default=0)
    stock_apartado = db.Column(db.Integer, default=0)  # Stock reservado en pedidos
    stock_minimo = db.Column(db.Integer, default=0)
    unidad = db.Column(db.String(20), default='und')
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    activo = db.Column(db.Boolean, default=True)
    
    movimientos = db.relationship('Movimiento', backref='producto', lazy=True)
    
    @property
    def stock_disponible(self):
        """Stock disponible para venta (stock actual - stock apartado)"""
        return self.stock_actual - self.stock_apartado

class Movimiento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # entrada, salida
    cantidad = db.Column(db.Integer, nullable=False)
    motivo = db.Column(db.String(200))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    
    producto_rel = db.relationship('Producto')
    usuario_rel = db.relationship('Usuario')

class Compra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    proveedor = db.Column(db.String(150))
    numero_factura = db.Column(db.String(50))
    total = db.Column(db.Float, default=0)
    estado = db.Column(db.String(20), default='pendiente')  # pendiente, pagada, cancelada
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    detalles = db.relationship('DetalleCompra', backref='compra', lazy=True)

class DetalleCompra(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    compra_id = db.Column(db.Integer, db.ForeignKey('compra.id'))
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'))
    cantidad = db.Column(db.Integer)
    precio_unitario = db.Column(db.Float)
    subtotal = db.Column(db.Float)
    producto = db.relationship('Producto')

class Venta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(150))
    numero_factura = db.Column(db.String(50))
    subtotal = db.Column(db.Float, default=0)
    descuento = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    estado = db.Column(db.String(20), default='completada')  # completada, cancelada
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    detalles = db.relationship('DetalleVenta', backref='venta', lazy=True)

class DetalleVenta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    venta_id = db.Column(db.Integer, db.ForeignKey('venta.id'))
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'))
    cantidad = db.Column(db.Integer)
    precio_unitario = db.Column(db.Float)
    subtotal = db.Column(db.Float)
    producto = db.relationship('Producto')

# ==================== COTIZACIONES ====================

class Cotizacion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(150))
    contacto = db.Column(db.String(100))
    email = db.Column(db.String(150))
    telefono = db.Column(db.String(50))
    validez = db.Column(db.Integer, default=30)  # días de validez
    observaciones = db.Column(db.Text)
    subtotal = db.Column(db.Float, default=0)
    descuento = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    estado = db.Column(db.String(20), default='pendiente')  # pendiente, aceptada, rechazada
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])
    detalles = db.relationship('DetalleCotizacion', backref='cotizacion', lazy=True)

class DetalleCotizacion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cotizacion_id = db.Column(db.Integer, db.ForeignKey('cotizacion.id'))
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'))
    cantidad = db.Column(db.Integer)
    precio_unitario = db.Column(db.Float)
    subtotal = db.Column(db.Float)
    producto = db.relationship('Producto')

# ==================== CLIENTES ====================

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(150), nullable=False)
    contacto = db.Column(db.String(100))
    telefono = db.Column(db.String(50))
    email = db.Column(db.String(150))
    direccion = db.Column(db.String(200))
    ruc = db.Column(db.String(50))
    cedula = db.Column(db.String(50))
    activo = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

# ==================== PEDIDOS ====================

class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente = db.Column(db.String(150))
    contacto = db.Column(db.String(100))
    telefono = db.Column(db.String(50))
    email = db.Column(db.String(150))
    observaciones = db.Column(db.Text)
    subtotal = db.Column(db.Float, default=0)
    descuento = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    estado = db.Column(db.String(20), default='pendiente')  # pendiente, completado, cancelado
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])
    detalles = db.relationship('DetallePedido', backref='pedido', lazy=True)

class DetallePedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pedido_id = db.Column(db.Integer, db.ForeignKey('pedido.id'))
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'))
    cantidad = db.Column(db.Integer)
    precio_unitario = db.Column(db.Float)
    subtotal = db.Column(db.Float)
    producto = db.relationship('Producto')

# ==================== SUCURSALES ====================

class Sucursal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    direccion = db.Column(db.String(200))
    telefono = db.Column(db.String(50))
    activa = db.Column(db.Boolean, default=True)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)

class StockSucursal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    sucursal_id = db.Column(db.Integer, db.ForeignKey('sucursal.id'), nullable=False)
    cantidad = db.Column(db.Integer, default=0)
    producto = db.relationship('Producto')
    sucursal = db.relationship('Sucursal')

class Traslado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sucursal_origen_id = db.Column(db.Integer, db.ForeignKey('sucursal.id'), nullable=False)
    sucursal_destino_id = db.Column(db.Integer, db.ForeignKey('sucursal.id'), nullable=False)
    estado = db.Column(db.String(20), default='pendiente')  # pendiente, en_transito, recibido, cancelado
    observaciones = db.Column(db.Text)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_recibido = db.Column(db.DateTime)
    usuario_envia_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    usuario_recibe_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    detalles = db.relationship('DetalleTraslado', backref='traslado', lazy=True)
    sucursal_origen = db.relationship('Sucursal', foreign_keys=[sucursal_origen_id])
    sucursal_destino = db.relationship('Sucursal', foreign_keys=[sucursal_destino_id])

class DetalleTraslado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    traslado_id = db.Column(db.Integer, db.ForeignKey('traslado.id'), nullable=False)
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'), nullable=False)
    cantidad = db.Column(db.Integer, nullable=False)
    producto = db.relationship('Producto')

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# ==================== RUTAS ====================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        usuario = Usuario.query.filter_by(username=username).first()
        if usuario and bcrypt.check_password_hash(usuario.password, password):
            if usuario.activo:
                login_user(usuario)
                return redirect(url_for('dashboard'))
            else:
                flash('Usuario inactivo', 'danger')
        else:
            flash('Credenciales incorrectas', 'danger')
    return render_template('login.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        nombre = request.form.get('nombre')
        rol = request.form.get('rol', 'empleado')
        
        if Usuario.query.filter_by(username=username).first():
            flash('El usuario ya existe', 'danger')
            return redirect(url_for('registro'))
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        nuevo_usuario = Usuario(username=username, password=hashed_password, nombre=nombre, rol=rol)
        db.session.add(nuevo_usuario)
        db.session.commit()
        flash('Usuario registrado exitosamente', 'success')
        return redirect(url_for('login'))
    return render_template('registro.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Estadísticas
    total_productos = Producto.query.filter_by(activo=True).count()
    productos_bajos = Producto.query.filter(Producto.stock_actual <= Producto.stock_minimo, Producto.activo==True).count()
    ventas_hoy = Venta.query.filter(db.func.date(Venta.fecha) == datetime.now().date()).count()
    compras_pendientes = Compra.query.filter_by(estado='pendiente').count()
    
    # Últimos movimientos
    ultimos_movimientos = Movimiento.query.order_by(Movimiento.fecha.desc()).limit(10).all()
    
    # Ventas del mes
    ventas_mes = Venta.query.filter(
        db.func.strftime('%Y-%m', Venta.fecha) == datetime.now().strftime('%Y-%m')
    ).all()
    total_ventas_mes = sum(v.total for v in ventas_mes)
    
    return render_template('dashboard.html', 
                           total_productos=total_productos,
                           productos_bajos=productos_bajos,
                           ventas_hoy=ventas_hoy,
                           compras_pendientes=compras_pendientes,
                           ultimos_movimientos=ultimos_movimientos,
                           total_ventas_mes=total_ventas_mes)

# ==================== PRODUCTOS ====================

@app.route('/productos')
@login_required
def productos():
    categoria_id = request.args.get('categoria')
    if categoria_id:
        lista_productos = Producto.query.filter_by(categoria_id=categoria_id, activo=True).all()
    else:
        lista_productos = Producto.query.filter_by(activo=True).all()
    categorias = Categoria.query.all()
    return render_template('productos.html', productos=lista_productos, categorias=categorias)

@app.route('/producto/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_producto():
    if current_user.rol != 'admin':
        flash('Solo administradores pueden crear productos', 'danger')
        return redirect(url_for('productos'))
    categorias = Categoria.query.all()
    if request.method == 'POST':
        codigo = request.form.get('codigo')
        if Producto.query.filter_by(codigo=codigo).first():
            flash('El código ya existe', 'danger')
            return redirect(url_for('nuevo_producto'))
        
        producto = Producto(
            codigo=codigo,
            nombre=request.form.get('nombre'),
            descripcion=request.form.get('descripcion'),
            categoria_id=request.form.get('categoria_id'),
            precio_compra=float(request.form.get('precio_compra', 0)),
            precio_venta=float(request.form.get('precio_venta', 0)),
            stock_actual=int(request.form.get('stock_actual', 0)),
            stock_minimo=int(request.form.get('stock_minimo', 0)),
            unidad=request.form.get('unidad', 'und')
        )
        db.session.add(producto)
        db.session.commit()
        
        # Movimiento inicial
        if producto.stock_actual > 0:
            movimiento = Movimiento(
                producto_id=producto.id,
                tipo='entrada',
                cantidad=producto.stock_actual,
                motivo='Stock inicial',
                usuario_id=current_user.id
            )
            db.session.add(movimiento)
            db.session.commit()
        
        flash('Producto creado exitosamente', 'success')
        return redirect(url_for('productos'))
    return render_template('producto_form.html', categorias=categorias, producto=None)

@app.route('/producto/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_producto(id):
    if current_user.rol != 'admin':
        flash('Solo administradores pueden editar productos', 'danger')
        return redirect(url_for('productos'))
    producto = Producto.query.get_or_404(id)
    categorias = Categoria.query.all()
    if request.method == 'POST':
        producto.codigo = request.form.get('codigo')
        producto.nombre = request.form.get('nombre')
        producto.descripcion = request.form.get('descripcion')
        producto.categoria_id = request.form.get('categoria_id')
        producto.precio_compra = float(request.form.get('precio_compra', 0))
        producto.precio_venta = float(request.form.get('precio_venta', 0))
        producto.stock_minimo = int(request.form.get('stock_minimo', 0))
        producto.unidad = request.form.get('unidad', 'und')
        db.session.commit()
        flash('Producto actualizado', 'success')
        return redirect(url_for('productos'))
    return render_template('producto_form.html', categorias=categorias, producto=producto)

@app.route('/producto/eliminar/<int:id>')
@login_required
def eliminar_producto(id):
    if current_user.rol != 'admin':
        flash('Solo administradores pueden eliminar productos', 'danger')
        return redirect(url_for('productos'))
    producto = Producto.query.get_or_404(id)
    producto.activo = False
    db.session.commit()
    flash('Producto eliminado', 'success')
    return redirect(url_for('productos'))

# ==================== KARDEX ====================

@app.route('/kardex')
@login_required
def kardex():
    """Kardex general de todos los productos"""
    # Obtener todos los productos con sus movimientos
    productos = Producto.query.filter_by(activo=True).all()
    
    # Obtener filtro de fecha
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    
    # Calcular kardex para cada producto
    kardex_data = []
    for producto in productos:
        query = Movimiento.query.filter_by(producto_id=producto.id)
        
        if fecha_inicio:
            query = query.filter(Movimiento.fecha >= fecha_inicio)
        if fecha_fin:
            query = query.filter(Movimiento.fecha <= fecha_fin)
        
        movimientos = query.order_by(Movimiento.fecha.asc()).all()
        
        # Calcular saldo acumulado
        saldo = 0
        entradas = 0
        salidas = 0
        
        for m in movimientos:
            if m.tipo == 'entrada':
                saldo += m.cantidad
                entradas += m.cantidad
            else:
                saldo -= m.cantidad
                salidas += m.cantidad
        
        if movimientos:  # Solo mostrar productos con movimientos
            kardex_data.append({
                'producto': producto,
                'entradas': entradas,
                'salidas': salidas,
                'saldo_actual': saldo,
                'movimientos_count': len(movimientos)
            })
    
    return render_template('kardex_general.html', kardex_data=kardex_data, 
                           fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)

@app.route('/kardex/producto/<int:producto_id>')
@login_required
def kardex_producto(producto_id):
    """Kardex detallado de un producto específico"""
    producto = Producto.query.get_or_404(producto_id)
    
    # Obtener filtro de fecha
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    
    query = Movimiento.query.filter_by(producto_id=producto_id)
    
    if fecha_inicio:
        query = query.filter(Movimiento.fecha >= fecha_inicio)
    if fecha_fin:
        query = query.filter(Movimiento.fecha <= fecha_fin)
    
    movimientos = query.order_by(Movimiento.fecha.asc()).all()
    
    # Calcular saldo acumulativo
    saldo = 0
    kardex_movimientos = []
    for m in movimientos:
        if m.tipo == 'entrada':
            saldo += m.cantidad
        else:
            saldo -= m.cantidad
        
        kardex_movimientos.append({
            'movimiento': m,
            'saldo': saldo
        })
    
    return render_template('kardex.html', producto=producto, 
                           movimientos=kardex_movimientos,
                           fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)

# ==================== MOVIMIENTOS ====================

@app.route('/movimientos')
@login_required
def movimientos():
    tipo = request.args.get('tipo')
    if tipo:
        lista_movimientos = Movimiento.query.filter_by(tipo=tipo).order_by(Movimiento.fecha.desc()).all()
    else:
        lista_movimientos = Movimiento.query.order_by(Movimiento.fecha.desc()).all()
    return render_template('movimientos.html', movimientos=lista_movimientos)

@app.route('/movimiento/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_movimiento():
    productos = Producto.query.filter_by(activo=True).all()
    if request.method == 'POST':
        producto_id = request.form.get('producto_id')
        cantidad = int(request.form.get('cantidad', 0))
        tipo = request.form.get('tipo')
        motivo = request.form.get('motivo')
        
        producto = Producto.query.get(producto_id)
        if not producto:
            flash('Producto no encontrado', 'danger')
            return redirect(url_for('nuevo_movimiento'))
        
        if tipo == 'salida' and producto.stock_actual < cantidad:
            flash('Stock insuficiente', 'danger')
            return redirect(url_for('nuevo_movimiento'))
        
        # Actualizar stock
        if tipo == 'entrada':
            producto.stock_actual += cantidad
        else:
            producto.stock_actual -= cantidad
        
        # Registrar movimiento
        movimiento = Movimiento(
            producto_id=producto_id,
            tipo=tipo,
            cantidad=cantidad,
            motivo=motivo,
            usuario_id=current_user.id
        )
        db.session.add(movimiento)
        db.session.commit()
        
        flash(f'Movimiento de {tipo} registrado', 'success')
        return redirect(url_for('movimientos'))
    return render_template('movimiento_form.html', productos=productos)

# ==================== COMPRAS ====================

@app.route('/compras')
@login_required
def compras():
    estado = request.args.get('estado')
    if estado:
        lista_compras = Compra.query.filter_by(estado=estado).order_by(Compra.fecha.desc()).all()
    else:
        lista_compras = Compra.query.order_by(Compra.fecha.desc()).all()
    return render_template('compras.html', compras=lista_compras)

@app.route('/compra/nueva', methods=['GET', 'POST'])
@login_required
def nueva_compra():
    productos = Producto.query.filter_by(activo=True).all()
    if request.method == 'POST':
        compra = Compra(
            proveedor=request.form.get('proveedor'),
            numero_factura=request.form.get('numero_factura'),
            usuario_id=current_user.id
        )
        db.session.add(compra)
        db.session.flush()
        
        total = 0
        producto_ids = request.form.getlist('producto_id[]')
        cantidades = request.form.getlist('cantidad[]')
        precios = request.form.getlist('precio[]')
        
        for i in range(len(producto_ids)):
            if producto_ids[i] and cantidades[i]:
                cantidad = int(cantidades[i])
                precio = float(precios[i])
                subtotal = cantidad * precio
                
                detalle = DetalleCompra(
                    compra_id=compra.id,
                    producto_id=int(producto_ids[i]),
                    cantidad=cantidad,
                    precio_unitario=precio,
                    subtotal=subtotal
                )
                db.session.add(detalle)
                
                # Actualizar stock
                producto = Producto.query.get(int(producto_ids[i]))
                producto.stock_actual += cantidad
                
                # Movimiento de entrada
                movimiento = Movimiento(
                    producto_id=int(producto_ids[i]),
                    tipo='entrada',
                    cantidad=cantidad,
                    motivo=f'Compra #{compra.id}',
                    usuario_id=current_user.id
                )
                db.session.add(movimiento)
                
                total += subtotal
        
        compra.total = total
        db.session.commit()
        
        flash('Compra registrada', 'success')
        return redirect(url_for('compras'))
    return render_template('compra_form.html', productos=productos)

@app.route('/compra/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_compra(id):
    compra = Compra.query.get_or_404(id)
    if request.method == 'POST':
        compra.estado = request.form.get('estado')
        db.session.commit()
        flash('Compra actualizada', 'success')
        return redirect(url_for('compras'))
    return render_template('compra_editar.html', compra=compra)

# ==================== VENTAS ====================

@app.route('/ventas')
@login_required
def ventas():
    estado = request.args.get('estado')
    if estado:
        lista_ventas = Venta.query.filter_by(estado=estado).order_by(Venta.fecha.desc()).all()
    else:
        lista_ventas = Venta.query.order_by(Venta.fecha.desc()).all()
    return render_template('ventas.html', ventas=lista_ventas)

@app.route('/venta/nueva', methods=['GET', 'POST'])
@login_required
def nueva_venta():
    productos = Producto.query.filter_by(activo=True).all()
    if request.method == 'POST':
        venta = Venta(
            cliente=request.form.get('cliente'),
            numero_factura=request.form.get('numero_factura'),
            descuento=float(request.form.get('descuento', 0)),
            usuario_id=current_user.id
        )
        db.session.add(venta)
        db.session.flush()
        
        subtotal = 0
        producto_ids = request.form.getlist('producto_id[]')
        cantidades = request.form.getlist('cantidad[]')
        precios = request.form.getlist('precio[]')
        
        for i in range(len(producto_ids)):
            if producto_ids[i] and cantidades[i]:
                cantidad = int(cantidades[i])
                precio = float(precios[i])
                subtotal_detalle = cantidad * precio
                
                producto = Producto.query.get(int(producto_ids[i]))
                if producto.stock_actual < cantidad:
                    flash(f'Stock insuficiente para {producto.nombre}', 'danger')
                    db.session.rollback()
                    return redirect(url_for('nueva_venta'))
                
                detalle = DetalleVenta(
                    venta_id=venta.id,
                    producto_id=int(producto_ids[i]),
                    cantidad=cantidad,
                    precio_unitario=precio,
                    subtotal=subtotal_detalle
                )
                db.session.add(detalle)
                
                # Actualizar stock
                producto.stock_actual -= cantidad
                
                # Movimiento de salida
                movimiento = Movimiento(
                    producto_id=int(producto_ids[i]),
                    tipo='salida',
                    cantidad=cantidad,
                    motivo=f'Venta #{venta.id}',
                    usuario_id=current_user.id
                )
                db.session.add(movimiento)
                
                subtotal += subtotal_detalle
        
        venta.subtotal = subtotal
        venta.total = subtotal - venta.descuento
        db.session.commit()
        
        flash('Venta registrada', 'success')
        return redirect(url_for('ventas'))
    return render_template('venta_form.html', productos=productos)

@app.route('/venta/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_venta(id):
    venta = Venta.query.get_or_404(id)
    if request.method == 'POST':
        venta.estado = request.form.get('estado')
        db.session.commit()
        flash('Venta actualizada', 'success')
        return redirect(url_for('ventas'))
    return render_template('venta_editar.html', venta=venta)

# ==================== CATEGORÍAS ====================

@app.route('/categorias')
@login_required
def categorias():
    if current_user.rol != 'admin':
        flash('Solo administradores pueden gestionar categorías', 'danger')
        return redirect(url_for('dashboard'))
    lista_categorias = Categoria.query.all()
    return render_template('categorias.html', categorias=lista_categorias)

@app.route('/categoria/nueva', methods=['POST'])
@login_required
def nueva_categoria():
    if current_user.rol != 'admin':
        flash('Solo administradores pueden gestionar categorías', 'danger')
        return redirect(url_for('dashboard'))
    nombre = request.form.get('nombre')
    descripcion = request.form.get('descripcion')
    categoria = Categoria(nombre=nombre, descripcion=descripcion)
    db.session.add(categoria)
    db.session.commit()
    flash('Categoría creada', 'success')
    return redirect(url_for('categorias'))

@app.route('/categoria/eliminar/<int:id>')
@login_required
def eliminar_categoria(id):
    if current_user.rol != 'admin':
        flash('Solo administradores pueden gestionar categorías', 'danger')
        return redirect(url_for('dashboard'))
    categoria = Categoria.query.get_or_404(id)
    db.session.delete(categoria)
    db.session.commit()
    flash('Categoría eliminada', 'success')
    return redirect(url_for('categorias'))

# ==================== USUARIOS ====================

@app.route('/usuarios')
@login_required
def usuarios():
    if current_user.rol != 'admin':
        flash('Solo administradores pueden gestionar usuarios', 'danger')
        return redirect(url_for('dashboard'))
    lista_usuarios = Usuario.query.all()
    return render_template('usuarios.html', usuarios=lista_usuarios)

@app.route('/usuario/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_usuario():
    if current_user.rol != 'admin':
        flash('Solo administradores pueden gestionar usuarios', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        nombre = request.form.get('nombre')
        rol = request.form.get('rol')
        
        if Usuario.query.filter_by(username=username).first():
            flash('El usuario ya existe', 'danger')
            return redirect(url_for('nuevo_usuario'))
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        usuario = Usuario(username=username, password=hashed_password, nombre=nombre, rol=rol)
        db.session.add(usuario)
        db.session.commit()
        flash('Usuario creado', 'success')
        return redirect(url_for('usuarios'))
    return render_template('usuario_form.html')

@app.route('/usuario/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_usuario(id):
    if current_user.rol != 'admin':
        flash('Solo administradores pueden gestionar usuarios', 'danger')
        return redirect(url_for('dashboard'))
    usuario = Usuario.query.get_or_404(id)
    if request.method == 'POST':
        usuario.nombre = request.form.get('nombre')
        usuario.rol = request.form.get('rol')
        if request.form.get('password'):
            usuario.password = bcrypt.generate_password_hash(request.form.get('password')).decode('utf-8')
        db.session.commit()
        flash('Usuario actualizado', 'success')
        return redirect(url_for('usuarios'))
    return render_template('usuario_form.html', usuario=usuario)

@app.route('/usuario/eliminar/<int:id>')
@login_required
def eliminar_usuario(id):
    if current_user.rol != 'admin':
        flash('Solo administradores pueden gestionar usuarios', 'danger')
        return redirect(url_for('dashboard'))
    usuario = Usuario.query.get_or_404(id)
    usuario.activo = False
    db.session.commit()
    flash('Usuario eliminado', 'success')
    return redirect(url_for('usuarios'))

# ==================== REPORTES ====================

@app.route('/reportes')
@login_required
def reportes():
    return render_template('reportes.html')

@app.route('/reporte/inventario')
@login_required
def reporte_inventario():
    productos = Producto.query.filter_by(activo=True).all()
    return render_template('reporte_inventario.html', productos=productos)

@app.route('/reporte/ventas')
@login_required
def reporte_ventas():
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    
    query = Venta.query
    if fecha_inicio:
        query = query.filter(Venta.fecha >= fecha_inicio)
    if fecha_fin:
        query = query.filter(Venta.fecha <= fecha_fin)
    
    ventas = query.order_by(Venta.fecha.desc()).all()
    total = sum(v.total for v in ventas)
    return render_template('reporte_ventas.html', ventas=ventas, total=total)

# ==================== API ====================

@app.route('/api/productos')
@login_required
def api_productos():
    productos = Producto.query.filter_by(activo=True).all()
    return jsonify([{
        'id': p.id,
        'codigo': p.codigo,
        'nombre': p.nombre,
        'stock': p.stock_actual,
        'precio': p.precio_venta
    } for p in productos])

@app.route('/api/producto/<int:id>')
@login_required
def api_producto(id):
    producto = Producto.query.get_or_404(id)
    return jsonify({
        'id': producto.id,
        'codigo': producto.codigo,
        'nombre': producto.nombre,
        'stock': producto.stock_actual,
        'precio': producto.precio_venta
    })

@app.route('/api/verificar-codigo')
@login_required
def verificar_codigo():
    """API para verificar si un código de producto ya existe"""
    codigo = request.args.get('codigo', '')
    producto_id = request.args.get('producto_id', None)
    
    if not codigo:
        return jsonify({'existe': False})
    
    query = Producto.query.filter_by(codigo=codigo, activo=True)
    
    # Si se está editando un producto, excluir ese producto de la búsqueda
    if producto_id:
        query = query.filter(Producto.id != int(producto_id))
    
    producto_existe = query.first() is not None
    
    return jsonify({'existe': producto_existe})

# ==================== COTIZACIONES ====================

@app.route('/cotizaciones')
@login_required
def cotizaciones():
    estado = request.args.get('estado')
    if estado:
        lista_cotizaciones = Cotizacion.query.filter_by(estado=estado).order_by(Cotizacion.fecha.desc()).all()
    else:
        lista_cotizaciones = Cotizacion.query.order_by(Cotizacion.fecha.desc()).all()
    return render_template('cotizaciones.html', cotizaciones=lista_cotizaciones)

@app.route('/cotizacion/nueva', methods=['GET', 'POST'])
@login_required
def nueva_cotizacion():
    productos = Producto.query.filter_by(activo=True).all()
    if request.method == 'POST':
        cotizacion = Cotizacion(
            cliente=request.form.get('cliente'),
            contacto=request.form.get('contacto'),
            email=request.form.get('email'),
            telefono=request.form.get('telefono'),
            validez=int(request.form.get('validez', 30)),
            observaciones=request.form.get('observaciones'),
            descuento=float(request.form.get('descuento', 0)),
            usuario_id=current_user.id
        )
        db.session.add(cotizacion)
        db.session.flush()
        
        subtotal = 0
        producto_ids = request.form.getlist('producto_id[]')
        cantidades = request.form.getlist('cantidad[]')
        precios = request.form.getlist('precio[]')
        
        for i in range(len(producto_ids)):
            if producto_ids[i] and cantidades[i]:
                cantidad = int(cantidades[i])
                precio = float(precios[i])
                subtotal_detalle = cantidad * precio
                
                detalle = DetalleCotizacion(
                    cotizacion_id=cotizacion.id,
                    producto_id=int(producto_ids[i]),
                    cantidad=cantidad,
                    precio_unitario=precio,
                    subtotal=subtotal_detalle
                )
                db.session.add(detalle)
                subtotal += subtotal_detalle
        
        cotizacion.subtotal = subtotal
        cotizacion.total = subtotal - cotizacion.descuento
        db.session.commit()
        
        flash('Cotización creada', 'success')
        return redirect(url_for('cotizaciones'))
    return render_template('cotizacion_form.html', productos=productos)

@app.route('/cotizacion/ver/<int:id>')
@login_required
def ver_cotizacion(id):
    cotizacion = Cotizacion.query.get_or_404(id)
    empresa = cargar_config_empresa()
    return render_template('cotizacion_ver.html', cotizacion=cotizacion, empresa=empresa)

@app.route('/cotizacion/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_cotizacion(id):
    cotizacion = Cotizacion.query.get_or_404(id)
    if request.method == 'POST':
        cotizacion.estado = request.form.get('estado')
        db.session.commit()
        flash('Cotización actualizada', 'success')
        return redirect(url_for('cotizaciones'))
    return render_template('cotizacion_editar.html', cotizacion=cotizacion)

@app.route('/cotizacion/eliminar/<int:id>')
@login_required
def eliminar_cotizacion(id):
    cotizacion = Cotizacion.query.get_or_404(id)
    db.session.delete(cotizacion)
    db.session.commit()
    flash('Cotización eliminada', 'success')
    return redirect(url_for('cotizaciones'))

# ==================== CONFIGURACIÓN DE EMPRESA ====================

@app.route('/configuracion', methods=['GET', 'POST'])
@login_required
def configuracion():
    if current_user.rol != 'admin':
        flash('Solo administradores pueden configurar la empresa', 'danger')
        return redirect(url_for('dashboard'))
    
    config = cargar_config_empresa()
    
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        direccion = request.form.get('direccion')
        telefono = request.form.get('telefono')
        email = request.form.get('email')
        ruc = request.form.get('ruc')
        
        # Manejar logo
        logo_filename = config.get('logo')
        if 'logo' in request.files and request.files['logo'].filename:
            file = request.files['logo']
            # Crear directorio static si no existe
            static_dir = os.path.join(os.path.dirname(__file__), 'static')
            if not os.path.exists(static_dir):
                os.makedirs(static_dir)
            
            # Guardar archivo
            filename = 'logo_empresa.' + file.filename.rsplit('.', 1)[-1].lower()
            filepath = os.path.join(static_dir, filename)
            file.save(filepath)
            logo_filename = filename
        
        # Guardar configuración
        config = {
            'nombre': nombre,
            'direccion': direccion,
            'telefono': telefono,
            'email': email,
            'ruc': ruc,
            'logo': logo_filename
        }
        guardar_config_empresa(config)
        flash('Configuración guardada exitosamente', 'success')
        return redirect(url_for('configuracion'))
    
    return render_template('configuracion.html', config=config)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(os.path.join(os.path.dirname(__name__), 'static'), filename)

# ==================== SUCURSALES ====================

@app.route('/sucursales')
@login_required
def sucursales():
    if current_user.rol != 'admin':
        flash('Solo administradores pueden gestionar sucursales', 'danger')
        return redirect(url_for('dashboard'))
    lista_sucursales = Sucursal.query.all()
    return render_template('sucursales.html', sucursales=lista_sucursales)

@app.route('/sucursal/nueva', methods=['GET', 'POST'])
@login_required
def nueva_sucursal():
    if current_user.rol != 'admin':
        flash('Solo administradores pueden gestionar sucursales', 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        direccion = request.form.get('direccion')
        telefono = request.form.get('telefono')
        
        if Sucursal.query.filter_by(nombre=nombre).first():
            flash('La sucursal ya existe', 'danger')
            return redirect(url_for('nueva_sucursal'))
        
        sucursal = Sucursal(
            nombre=nombre,
            direccion=direccion,
            telefono=telefono
        )
        db.session.add(sucursal)
        db.session.commit()
        
        # Inicializar stock en cero para todos los productos
        productos = Producto.query.filter_by(activo=True).all()
        for producto in productos:
            stock = StockSucursal(
                producto_id=producto.id,
                sucursal_id=sucursal.id,
                cantidad=0
            )
            db.session.add(stock)
        db.session.commit()
        
        flash('Sucursal creada exitosamente', 'success')
        return redirect(url_for('sucursales'))
    return render_template('sucursal_form.html', sucursal=None)

@app.route('/sucursal/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_sucursal(id):
    if current_user.rol != 'admin':
        flash('Solo administradores pueden gestionar sucursales', 'danger')
        return redirect(url_for('dashboard'))
    sucursal = Sucursal.query.get_or_404(id)
    if request.method == 'POST':
        sucursal.nombre = request.form.get('nombre')
        sucursal.direccion = request.form.get('direccion')
        sucursal.telefono = request.form.get('telefono')
        sucursal.activa = 'activa' in request.form
        db.session.commit()
        flash('Sucursal actualizada', 'success')
        return redirect(url_for('sucursales'))
    return render_template('sucursal_form.html', sucursal=sucursal)

@app.route('/sucursal/eliminar/<int:id>')
@login_required
def eliminar_sucursal(id):
    if current_user.rol != 'admin':
        flash('Solo administradores pueden gestionar sucursales', 'danger')
        return redirect(url_for('dashboard'))
    sucursal = Sucursal.query.get_or_404(id)
    
    # Verificar si hay stock en la sucursal
    stocks = StockSucursal.query.filter_by(sucursal_id=id).all()
    tiene_stock = any(s.cantidad > 0 for s in stocks)
    
    if tiene_stock:
        flash('No se puede eliminar la sucursal porque tiene productos en stock', 'danger')
        return redirect(url_for('sucursales'))
    
    # Eliminar stocks relacionados
    for stock in stocks:
        db.session.delete(stock)
    
    db.session.delete(sucursal)
    db.session.commit()
    flash('Sucursal eliminada', 'success')
    return redirect(url_for('sucursales'))

# ==================== TRASLADOS ====================

@app.route('/traslados')
@login_required
def traslados():
    estado = request.args.get('estado')
    if estado:
        lista_traslados = Traslado.query.filter_by(estado=estado).order_by(Traslado.fecha_creacion.desc()).all()
    else:
        lista_traslados = Traslado.query.order_by(Traslado.fecha_creacion.desc()).all()
    return render_template('traslados.html', traslados=lista_traslados)

@app.route('/traslado/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_traslado():
    sucursales = Sucursal.query.filter_by(activa=True).all()
    productos = Producto.query.filter_by(activo=True).all()
    
    if len(sucursales) < 2:
        flash('Se necesitan al menos 2 sucursales para crear un traslado', 'warning')
        return redirect(url_for('sucursales'))
    
    if request.method == 'POST':
        sucursal_origen_id = int(request.form.get('sucursal_origen_id'))
        sucursal_destino_id = int(request.form.get('sucursal_destino_id'))
        observaciones = request.form.get('observaciones')
        
        if sucursal_origen_id == sucursal_destino_id:
            flash('La sucursal de origen y destino no pueden ser iguales', 'danger')
            return redirect(url_for('nuevo_traslado'))
        
        traslado = Traslado(
            sucursal_origen_id=sucursal_origen_id,
            sucursal_destino_id=sucursal_destino_id,
            observaciones=observaciones,
            usuario_envia_id=current_user.id,
            estado='pendiente'
        )
        db.session.add(traslado)
        db.session.flush()
        
        producto_ids = request.form.getlist('producto_id[]')
        cantidades = request.form.getlist('cantidad[]')
        
        for i in range(len(producto_ids)):
            if producto_ids[i] and cantidades[i]:
                cantidad = int(cantidades[i])
                if cantidad <= 0:
                    continue
                
                producto_id = int(producto_ids[i])
                
                # Verificar stock en sucursal origen
                stock_origen = StockSucursal.query.filter_by(
                    producto_id=producto_id,
                    sucursal_id=sucursal_origen_id
                ).first()
                
                if not stock_origen or stock_origen.cantidad < cantidad:
                    db.session.rollback()
                    flash(f'Stock insuficiente para el producto {Producto.query.get(producto_id).nombre}', 'danger')
                    return redirect(url_for('nuevo_traslado'))
                
                # Crear detalle del traslado
                detalle = DetalleTraslado(
                    traslado_id=traslado.id,
                    producto_id=producto_id,
                    cantidad=cantidad
                )
                db.session.add(detalle)
                
                # Reducir stock en origen
                stock_origen.cantidad -= cantidad
        
        db.session.commit()
        flash('Traslado creado exitosamente', 'success')
        return redirect(url_for('traslados'))
    
    return render_template('traslado_form.html', sucursales=sucursales, productos=productos)

@app.route('/traslado/ver/<int:id>')
@login_required
def ver_traslado(id):
    traslado = Traslado.query.get_or_404(id)
    empresa = cargar_config_empresa()
    return render_template('traslado_ver.html', traslado=traslado, empresa=empresa)

@app.route('/traslado/confirmar/<int:id>', methods=['POST'])
@login_required
def confirmar_traslado(id):
    traslado = Traslado.query.get_or_404(id)
    
    if traslado.estado != 'pendiente':
        flash('Este traslado ya no puede ser confirmado', 'warning')
        return redirect(url_for('traslados'))
    
    # Actualizar estado
    traslado.estado = 'recibido'
    traslado.fecha_recibido = datetime.utcnow()
    traslado.usuario_recibe_id = current_user.id
    
    # Agregar stock a la sucursal destino
    for detalle in traslado.detalles:
        stock_destino = StockSucursal.query.filter_by(
            producto_id=detalle.producto_id,
            sucursal_id=traslado.sucursal_destino_id
        ).first()
        
        if stock_destino:
            stock_destino.cantidad += detalle.cantidad
        else:
            nuevo_stock = StockSucursal(
                producto_id=detalle.producto_id,
                sucursal_id=traslado.sucursal_destino_id,
                cantidad=detalle.cantidad
            )
            db.session.add(nuevo_stock)
    
    db.session.commit()
    flash('Traslado recibido y stock actualizado', 'success')
    return redirect(url_for('traslados'))

@app.route('/traslado/cancelar/<int:id>')
@login_required
def cancelar_traslado(id):
    traslado = Traslado.query.get_or_404(id)
    
    if traslado.estado != 'pendiente':
        flash('Este traslado no puede ser cancelado', 'warning')
        return redirect(url_for('traslados'))
    
    # Devolver stock a la sucursal origen
    for detalle in traslado.detalles:
        stock_origen = StockSucursal.query.filter_by(
            producto_id=detalle.producto_id,
            sucursal_id=traslado.sucursal_origen_id
        ).first()
        
        if stock_origen:
            stock_origen.cantidad += detalle.cantidad
    
    traslado.estado = 'cancelado'
    db.session.commit()
    flash('Traslado cancelado y stock restaurado', 'success')
    return redirect(url_for('traslados'))

# ==================== STOCK POR SUCURSAL ====================

@app.route('/stock/sucursal/<int:sucursal_id>')
@login_required
def stock_sucursal(sucursal_id):
    sucursal = Sucursal.query.get_or_404(sucursal_id)
    stocks = StockSucursal.query.filter_by(sucursal_id=sucursal_id).all()
    return render_template('stock_sucursal.html', sucursal=sucursal, stocks=stocks)

@app.route('/api/stock/sucursal/<int:sucursal_id>')
@login_required
def api_stock_sucursal(sucursal_id):
    """API para obtener el stock de todos los productos en una sucursal"""
    stocks = StockSucursal.query.filter_by(sucursal_id=sucursal_id).all()
    return jsonify([{
        'producto_id': s.producto_id,
        'cantidad': s.cantidad,
        'producto_nombre': s.producto.nombre
    } for s in stocks])

# ==================== CLIENTES ====================

@app.route('/clientes')
@login_required
def clientes():
    lista_clientes = Cliente.query.filter_by(activo=True).order_by(Cliente.nombre).all()
    return render_template('clientes.html', clientes=lista_clientes)

@app.route('/cliente/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_cliente():
    if request.method == 'POST':
        cliente = Cliente(
            nombre=request.form.get('nombre'),
            contacto=request.form.get('contacto'),
            telefono=request.form.get('telefono'),
            email=request.form.get('email'),
            direccion=request.form.get('direccion'),
            ruc=request.form.get('ruc'),
            cedula=request.form.get('cedula')
        )
        db.session.add(cliente)
        db.session.commit()
        flash('Cliente creado exitosamente', 'success')
        return redirect(url_for('clientes'))
    return render_template('cliente_form.html', cliente=None)

@app.route('/cliente/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    if request.method == 'POST':
        cliente.nombre = request.form.get('nombre')
        cliente.contacto = request.form.get('contacto')
        cliente.telefono = request.form.get('telefono')
        cliente.email = request.form.get('email')
        cliente.direccion = request.form.get('direccion')
        cliente.ruc = request.form.get('ruc')
        cliente.cedula = request.form.get('cedula')
        db.session.commit()
        flash('Cliente actualizado', 'success')
        return redirect(url_for('clientes'))
    return render_template('cliente_form.html', cliente=cliente)

@app.route('/cliente/eliminar/<int:id>')
@login_required
def eliminar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    cliente.activo = False
    db.session.commit()
    flash('Cliente eliminado', 'success')
    return redirect(url_for('clientes'))

@app.route('/api/clientes')
@login_required
def api_clientes():
    """API para obtener clientes activos"""
    clientes = Cliente.query.filter_by(activo=True).order_by(Cliente.nombre).all()
    return jsonify([{
        'id': c.id,
        'nombre': c.nombre,
        'telefono': c.telefono,
        'email': c.email,
        'contacto': c.contacto,
        'direccion': c.direccion,
        'ruc': c.ruc,
        'cedula': c.cedula
    } for c in clientes])

@app.route('/api/cliente/<int:id>')
@login_required
def api_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    return jsonify({
        'id': cliente.id,
        'nombre': cliente.nombre,
        'telefono': cliente.telefono,
        'email': cliente.email,
        'contacto': cliente.contacto,
        'direccion': cliente.direccion,
        'ruc': cliente.ruc,
        'cedula': cliente.cedula
    })

# ==================== PEDIDOS ====================

@app.route('/pedidos')
@login_required
def pedidos():
    estado = request.args.get('estado')
    if estado:
        lista_pedidos = Pedido.query.filter_by(estado=estado).order_by(Pedido.fecha.desc()).all()
    else:
        lista_pedidos = Pedido.query.order_by(Pedido.fecha.desc()).all()
    return render_template('pedidos.html', pedidos=lista_pedidos)

@app.route('/pedido/nuevo', methods=['GET', 'POST'])
@login_required
def nuevo_pedido():
    productos = Producto.query.filter_by(activo=True).all()
    if request.method == 'POST':
        pedido = Pedido(
            cliente=request.form.get('cliente'),
            contacto=request.form.get('contacto'),
            telefono=request.form.get('telefono'),
            email=request.form.get('email'),
            observaciones=request.form.get('observaciones'),
            descuento=float(request.form.get('descuento', 0)),
            usuario_id=current_user.id
        )
        db.session.add(pedido)
        db.session.flush()
        
        subtotal = 0
        producto_ids = request.form.getlist('producto_id[]')
        cantidades = request.form.getlist('cantidad[]')
        precios = request.form.getlist('precio[]')
        
        for i in range(len(producto_ids)):
            if producto_ids[i] and cantidades[i]:
                cantidad = int(cantidades[i])
                precio = float(precios[i])
                subtotal_detalle = cantidad * precio
                
                producto = Producto.query.get(int(producto_ids[i]))
                
                # Verificar stock disponible (stock actual - stock apartado)
                stock_disponible = producto.stock_actual - producto.stock_apartado
                if stock_disponible < cantidad:
                    flash(f'Stock disponible insuficiente para {producto.nombre}. Disponible: {stock_disponible}', 'danger')
                    db.session.rollback()
                    return redirect(url_for('nuevo_pedido'))
                
                detalle = DetallePedido(
                    pedido_id=pedido.id,
                    producto_id=int(producto_ids[i]),
                    cantidad=cantidad,
                    precio_unitario=precio,
                    subtotal=subtotal_detalle
                )
                db.session.add(detalle)
                
                # Apartar stock (aumentar stock_apartado)
                producto.stock_apartado += cantidad
                
                subtotal += subtotal_detalle
        
        pedido.subtotal = subtotal
        pedido.total = subtotal - pedido.descuento
        db.session.commit()
        
        flash('Pedido creado - productos apartados', 'success')
        return redirect(url_for('pedidos'))
    return render_template('pedido_form.html', productos=productos)

@app.route('/pedido/ver/<int:id>')
@login_required
def ver_pedido(id):
    pedido = Pedido.query.get_or_404(id)
    empresa = cargar_config_empresa()
    return render_template('pedido_ver.html', pedido=pedido, empresa=empresa)

@app.route('/pedido/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_pedido(id):
    pedido = Pedido.query.get_or_404(id)
    if request.method == 'POST':
        pedido.estado = request.form.get('estado')
        db.session.commit()
        flash('Pedido actualizado', 'success')
        return redirect(url_for('pedidos'))
    return render_template('pedido_editar.html', pedido=pedido)

@app.route('/pedido/eliminar/<int:id>')
@login_required
def eliminar_pedido(id):
    pedido = Pedido.query.get_or_404(id)
    
    # Si el pedido está pendiente, liberar el stock apartado
    if pedido.estado == 'pendiente':
        for detalle in pedido.detalles:
            producto = Producto.query.get(detalle.producto_id)
            producto.stock_apartado -= detalle.cantidad
            if producto.stock_apartado < 0:
                producto.stock_apartado = 0
    
    db.session.delete(pedido)
    db.session.commit()
    flash('Pedido eliminado', 'success')
    return redirect(url_for('pedidos'))

@app.route('/pedido/completar/<int:id>', methods=['POST'])
@login_required
def completar_pedido(id):
    """Convierte el pedido en venta y descuenta el stock"""
    pedido = Pedido.query.get_or_404(id)
    
    if pedido.estado != 'pendiente':
        flash('Este pedido ya no puede ser completado', 'warning')
        return redirect(url_for('pedidos'))
    
    # Crear la venta asociada al pedido
    venta = Venta(
        cliente=pedido.cliente,
        numero_factura=request.form.get('numero_factura', ''),
        descuento=pedido.descuento,
        usuario_id=current_user.id,
        estado='completada'
    )
    db.session.add(venta)
    db.session.flush()
    
    # Procesar cada detalle del pedido
    for detalle in pedido.detalles:
        producto = Producto.query.get(detalle.producto_id)
        
        # Verificar que hay suficiente stock
        if producto.stock_actual < detalle.cantidad:
            flash(f'Stock insuficiente para {producto.nombre}. Stock actual: {producto.stock_actual}', 'danger')
            db.session.rollback()
            return redirect(url_for('pedidos'))
        
        # Reducir stock actual y mantener stock_apartado como ya estaba separado
        producto.stock_actual -= detalle.cantidad
        
        # Reducir stock apartado (ya que se usó ese stock)
        producto.stock_apartado -= detalle.cantidad
        if producto.stock_apartado < 0:
            producto.stock_apartado = 0
        
        # Crear detalle de venta
        detalle_venta = DetalleVenta(
            venta_id=venta.id,
            producto_id=detalle.producto_id,
            cantidad=detalle.cantidad,
            precio_unitario=detalle.precio_unitario,
            subtotal=detalle.subtotal
        )
        db.session.add(detalle_venta)
        
        # Registrar movimiento de salida
        movimiento = Movimiento(
            producto_id=detalle.producto_id,
            tipo='salida',
            cantidad=detalle.cantidad,
            motivo=f'Venta por pedido #{pedido.id}',
            usuario_id=current_user.id
        )
        db.session.add(movimiento)
    
    venta.subtotal = pedido.subtotal
    venta.total = pedido.total
    
    # Actualizar estado del pedido
    pedido.estado = 'completado'
    
    db.session.commit()
    flash('Pedido completado y convertido en venta', 'success')
    return redirect(url_for('pedidos'))

@app.route('/pedido/cancelar/<int:id>')
@login_required
def cancelar_pedido(id):
    """Cancela el pedido y libera el stock apartado"""
    pedido = Pedido.query.get_or_404(id)
    
    if pedido.estado != 'pendiente':
        flash('Este pedido no puede ser cancelado', 'warning')
        return redirect(url_for('pedidos'))
    
    # Liberar el stock apartado
    for detalle in pedido.detalles:
        producto = Producto.query.get(detalle.producto_id)
        producto.stock_apartado -= detalle.cantidad
        if producto.stock_apartado < 0:
            producto.stock_apartado = 0
    
    pedido.estado = 'cancelado'
    db.session.commit()
    flash('Pedido cancelado y stock liberado', 'success')
    return redirect(url_for('pedidos'))

# ==================== INICIALIZAR ====================

def crear_tablas():
    with app.app_context():
        db.create_all()
        
        # Crear admin si no existe
        if not Usuario.query.filter_by(username='admin').first():
            hashed = bcrypt.generate_password_hash('admin123').decode('utf-8')
            admin = Usuario(username='admin', password=hashed, nombre='Administrador', rol='admin')
            db.session.add(admin)
            db.session.commit()
            print("Usuario admin creado (admin/admin123)")

if __name__ == '__main__':
    crear_tablas()
    app.run(debug=True, host='0.0.0.0', port=5000)

