import os
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_manager, current_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import cloudinary
import cloudinary.uploader

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tu_clave_secreta_local')

# Configuración de Base de Datos (Cambia automáticamente a PostgreSQL en Render)
database_url = os.environ.get('DATABASE_URL', 'sqlite:///catalogo.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Configuración de Cloudinary
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET')
)

# --- Modelos de la Base de Datos ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    precio = db.Column(db.Float, nullable=False)
    url_foto = db.Column(db.String(255), nullable=False)
    public_id_cloudinary = db.Column(db.String(100), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Rutas Públicas ---
@app.route('/')
def catalogo():
    productos = Producto.query.all()
    # Enviamos el host actual para armar el link de WhatsApp correctamente
    base_url = request.host_url
    return render_template('catalogo.html', productos=productos, base_url=base_url)

# --- Autenticación ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('admin'))
        flash('Credenciales incorrectas.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('catalogo'))

# --- Panel de Administración (CRUD) ---
@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin():
    if request.method == 'POST':
        # Crear Producto
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        precio = float(request.form.get('precio'))
        file_to_upload = request.files.get('foto')

        if file_to_upload:
            upload_result = cloudinary.uploader.upload(file_to_upload)
            nuevo_producto = Producto(
                nombre=nombre,
                descripcion=descripcion,
                precio=precio,
                url_foto=upload_result['secure_url'],
                public_id_cloudinary=upload_result['public_id']
            )
            db.session.add(nuevo_producto)
            db.session.commit()
            flash('Producto agregado con éxito', 'success')
            return redirect(url_for('admin'))
        
    productos = Producto.query.all()
    return render_template('admin.html', productos=productos)

@app.route('/admin/editar/<int:id>', methods=['POST'])
@login_required
def editar_producto(id):
    producto = Producto.query.get_or_404(id)
    producto.nombre = request.form.get('nombre')
    producto.descripcion = request.form.get('descripcion')
    producto.precio = float(request.form.get('precio'))
    
    file_to_upload = request.files.get('foto')
    if file_to_upload:
        # Eliminar foto vieja e incorporar la nueva
        cloudinary.uploader.destroy(producto.public_id_cloudinary)
        upload_result = cloudinary.uploader.upload(file_to_upload)
        producto.url_foto = upload_result['secure_url']
        producto.public_id_cloudinary = upload_result['public_id']
        
    db.session.commit()
    flash('Producto actualizado', 'success')
    return redirect(url_for('admin'))

@app.route('/admin/eliminar/<int:id>', methods=['POST'])
@login_required
def eliminar_producto(id):
    producto = Producto.query.get_or_404(id)
    # Eliminar de Cloudinary
    cloudinary.uploader.destroy(producto.public_id_cloudinary)
    # Eliminar de Base de Datos
    db.session.delete(producto)
    db.session.commit()
    flash('Producto eliminado', 'success')
    return redirect(url_for('admin'))

# Inicializador de Base de Datos y cuenta de Admin por defecto si no existen
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        hashed_pw = generate_password_hash('admin123', method='pbkdf2:sha256')
        admin_user = User(username='admin', password=hashed_pw)
        db.session.add(admin_user)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)
  
