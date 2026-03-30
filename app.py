import os
from flask import Flask, render_template, request, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import csv
import psycopg2 
import cloudinary
import cloudinary.uploader

app = Flask(__name__)
# 🔒 Llave secreta necesaria para que el servidor recuerde quién inició sesión
app.secret_key = "llave_super_secreta_zimapan_2026" 

# ========================================================
# ⚙️ CONFIGURACIÓN DEL EVENTO Y SEGURIDAD
# ========================================================
USUARIO_ADMIN = "admin"
PASSWORD_ADMIN = "Zimapan2026*"

# Fecha de cierre: Año(2026), Mes(9), Día(11), Hora(12), Minuto(0), Segundo(0)
FECHA_CIERRE = datetime(2026, 9, 11, 12, 0, 0)

# ========================================================
# 🔑 TUS LLAVES DE BÓVEDA (Vuelve a pegarlas aquí)
# ========================================================
URL_BASE_DATOS = "postgresql://postgres.hszcoiulvjkuhhycodvd:Z!m4p4n_Huapang0@aws-1-us-east-1.pooler.supabase.com:5432/postgres"

cloudinary.config(
  cloud_name = "dbwkwatfe",
  api_key = "119747285193542",
  api_secret = "V8GTv2DjmX6VE1qbyIWtfo7YKMo"
)

# 1. LÓGICA DE CATEGORÍAS
def asignar_categoria_pareja(fecha_1, fecha_2):
    def obtener_edad(fecha_nacimiento):
        fecha_nac = datetime.strptime(fecha_nacimiento, '%Y-%m-%d')
        fecha_concurso = datetime(2026, 4, 4)
        edad = fecha_concurso.year - fecha_nac.year - ((fecha_concurso.month, fecha_concurso.day) < (fecha_nac.month, fecha_nac.day))
        return edad

    edad_1 = obtener_edad(fecha_1)
    edad_2 = obtener_edad(fecha_2)
    edad_mayor = max(edad_1, edad_2)

    if edad_mayor <= 6:
        return "Pequeños Huapangueros"
    elif edad_mayor <= 12:
        return "Infantil"
    elif edad_mayor <= 17:
        return "Juvenil"
    else:
        return "Adultos"

def iniciar_base_datos():
    conexion = psycopg2.connect(URL_BASE_DATOS)
    cursor = conexion.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parejas (
            id SERIAL PRIMARY KEY,
            telefono TEXT,
            curp_1 TEXT, nombre_1 TEXT, fecha_nac_1 TEXT,
            curp_2 TEXT, nombre_2 TEXT, fecha_nac_2 TEXT,
            estado TEXT, municipio TEXT, estilo TEXT,
            categoria_asignada TEXT, foto_comprobante TEXT,
            fecha_registro TEXT
        )
    ''')
    conexion.commit()
    conexion.close()

iniciar_base_datos()

# 3. RUTAS DE LA APLICACIÓN
@app.route('/')
def index():
    hora_hidalgo = datetime.utcnow() - timedelta(hours=6)
    
    # Si ya pasó la fecha de cierre, mostramos la pantalla de "Cerrado"
    if hora_hidalgo >= FECHA_CIERRE:
        return render_template('cerrado.html')
        
    # Si aún estamos a tiempo, mandamos la fecha límite al HTML para el cronómetro
    return render_template('index.html', fecha_cierre=FECHA_CIERRE.isoformat())

@app.route('/procesar_registro', methods=['POST'])
def procesar_registro():
    # Doble candado: Si alguien intenta forzar el envío después de la fecha, el servidor lo rechaza
    hora_hidalgo = datetime.utcnow() - timedelta(hours=6)
    if hora_hidalgo >= FECHA_CIERRE:
        return "El registro ha finalizado de manera oficial.", 403

    if request.method == 'POST':
        telefono = request.form.get('telefono') 
        curp_1 = request.form.get('curp_1')
        nombre_1 = request.form.get('nombre_1')
        fecha_nac_1 = request.form.get('fecha_nac_1')
        curp_2 = request.form.get('curp_2')
        nombre_2 = request.form.get('nombre_2')
        fecha_nac_2 = request.form.get('fecha_nac_2')
        estado = request.form.get('estado')
        municipio = request.form.get('municipio')
        estilo = request.form.get('estilo')

        categoria = asignar_categoria_pareja(fecha_nac_1, fecha_nac_2)

        archivo = request.files['comprobante']
        if archivo.filename != '':
            respuesta_nube = cloudinary.uploader.upload(archivo)
            enlace_imagen = respuesta_nube.get('secure_url')
        else:
            enlace_imagen = "sin_comprobante.png"

        fecha_exacta = hora_hidalgo.strftime('%Y-%m-%d %H:%M:%S')

        conexion = psycopg2.connect(URL_BASE_DATOS)
        cursor = conexion.cursor()
        
        cursor.execute('''
            INSERT INTO parejas (
                telefono, curp_1, nombre_1, fecha_nac_1, 
                curp_2, nombre_2, fecha_nac_2, 
                estado, municipio, estilo, 
                categoria_asignada, foto_comprobante, fecha_registro
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id;
        ''', (telefono, curp_1, nombre_1, fecha_nac_1, curp_2, nombre_2, fecha_nac_2, estado, municipio, estilo, categoria, enlace_imagen, fecha_exacta))
        
        folio = cursor.fetchone()[0] 
        
        conexion.commit()
        conexion.close()

        return render_template('exito.html', folio=folio, nombre_1=nombre_1, nombre_2=nombre_2, categoria=categoria)

# ========================================================
# 🛡️ RUTAS DE SEGURIDAD Y ADMINISTRACIÓN
# ========================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        password = request.form.get('password')
        if usuario == USUARIO_ADMIN and password == PASSWORD_ADMIN:
            session['admin_logueado'] = True
            return redirect(url_for('panel_admin'))
        else:
            error = "Credenciales incorrectas. Acceso denegado."
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('admin_logueado', None)
    return redirect(url_for('login'))

@app.route('/admin')
def panel_admin():
    # Candado: Si no está logueado, lo regresamos a la pantalla de login
    if 'admin_logueado' not in session:
        return redirect(url_for('login'))

    conexion = psycopg2.connect(URL_BASE_DATOS)
    cursor = conexion.cursor()
    cursor.execute('SELECT * FROM parejas ORDER BY id DESC')
    datos = cursor.fetchall()
    conexion.close()
    return render_template('admin.html', parejas=datos)

@app.route('/descargar_excel')
def descargar_excel():
    # Candado para descargas
    if 'admin_logueado' not in session:
        return redirect(url_for('login'))

    conexion = psycopg2.connect(URL_BASE_DATOS)
    cursor = conexion.cursor()
    cursor.execute('SELECT * FROM parejas ORDER BY id ASC')
    datos = cursor.fetchall()
    conexion.close()

    ruta_csv = os.path.join('static', 'registros_huapango.csv')
    with open(ruta_csv, mode='w', newline='', encoding='utf-8-sig') as archivo_csv:
        escritor = csv.writer(archivo_csv)
        escritor.writerow(['Folio', 'Teléfono', 'CURP 1', 'Nombre 1', 'Fecha Nac 1', 
                           'CURP 2', 'Nombre 2', 'Fecha Nac 2', 
                           'Estado', 'Municipio', 'Estilo', 
                           'Categoría', 'Archivo Comprobante', 'Fecha de Registro'])
        escritor.writerows(datos)

    return send_file(ruta_csv, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)