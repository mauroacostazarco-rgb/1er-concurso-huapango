from flask import Flask, render_template, request
from werkzeug.utils import secure_filename
from datetime import datetime
import sqlite3
import os
import csv
import io
from flask import make_response

app = Flask(__name__)

# Configuración para guardar las imágenes
CARPETA_SUBIDAS = 'static/uploads'
app.config['CARPETA_SUBIDAS'] = CARPETA_SUBIDAS

# Aseguramos que la carpeta de subidas exista al iniciar
os.makedirs(CARPETA_SUBIDAS, exist_ok=True)

# ==========================================
# 1. CONFIGURACIÓN DEL CONCURSO Y CATEGORÍAS
# ==========================================
CONFIGURACION_CONCURSO = {
    "fecha_corte": datetime(2026, 8, 15),
    "categorias": {
        "Huapangueritos": {"min": 3, "max": 5},
        "Infantil": {"min": 6, "max": 12},
        "Juvenil": {"min": 13, "max": 17},
        "Adultos": {"min": 18, "max": 99}
    }
}

def calcular_edad(fecha_nacimiento, fecha_corte):
    edad = fecha_corte.year - fecha_nacimiento.year
    if (fecha_corte.month, fecha_corte.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
        edad -= 1
    return edad

def asignar_categoria_pareja(fecha_nac_1_str, fecha_nac_2_str):
    formato_fecha = "%Y-%m-%d"
    fecha_nac_1 = datetime.strptime(fecha_nac_1_str, formato_fecha)
    fecha_nac_2 = datetime.strptime(fecha_nac_2_str, formato_fecha)
    fecha_corte = CONFIGURACION_CONCURSO["fecha_corte"]
    
    edad_1 = calcular_edad(fecha_nac_1, fecha_corte)
    edad_2 = calcular_edad(fecha_nac_2, fecha_corte)
    edad_competencia = max(edad_1, edad_2)
    
    for nombre_categoria, rangos in CONFIGURACION_CONCURSO["categorias"].items():
        if rangos["min"] <= edad_competencia <= rangos["max"]:
            return nombre_categoria
    return "Fuera de Rango"

# ==========================================
# 2. BASE DE DATOS
# ==========================================
def iniciar_base_datos():
    conexion = sqlite3.connect('registro_huapango.db')
    cursor = conexion.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parejas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            curp_1 TEXT, nombre_1 TEXT, fecha_nac_1 TEXT,
            curp_2 TEXT, nombre_2 TEXT, fecha_nac_2 TEXT,
            estado TEXT, municipio TEXT, estilo TEXT,
            categoria_asignada TEXT, foto_comprobante TEXT,
            fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conexion.commit()
    conexion.close()

iniciar_base_datos()

# ==========================================
# 3. RUTAS DE LA APLICACIÓN WEB
# ==========================================
@app.route('/')
def inicio():
    return render_template('index.html')

@app.route('/procesar_registro', methods=['POST'])
def procesar_registro():
    if request.method == 'POST':
        # 1. Atrapamos los textos del formulario
        curp_1 = request.form.get('curp_1')
        nombre_1 = request.form.get('nombre_1')
        fecha_nac_1 = request.form.get('fecha_nac_1')
        
        curp_2 = request.form.get('curp_2')
        nombre_2 = request.form.get('nombre_2')
        fecha_nac_2 = request.form.get('fecha_nac_2')
        
        estado = request.form.get('estado')
        municipio = request.form.get('municipio')
        estilo = request.form.get('estilo')

        # 2. Calculamos la categoría mágicamente en el backend
        categoria = asignar_categoria_pareja(fecha_nac_1, fecha_nac_2)

        # 3. Procesamos y guardamos la imagen de forma segura
        archivo = request.files['comprobante']
        if archivo.filename != '':
            # secure_filename limpia el nombre del archivo (quita espacios raros o caracteres peligrosos)
            nombre_archivo = secure_filename(archivo.filename)
            ruta_guardado = os.path.join(app.config['CARPETA_SUBIDAS'], nombre_archivo)
            archivo.save(ruta_guardado)
        else:
            nombre_archivo = "sin_comprobante.png"

        # 4. Inyectamos todo a la Base de Datos
        conexion = sqlite3.connect('registro_huapango.db')
        cursor = conexion.cursor()
        cursor.execute('''
            INSERT INTO parejas (
                curp_1, nombre_1, fecha_nac_1, 
                curp_2, nombre_2, fecha_nac_2, 
                estado, municipio, estilo, 
                categoria_asignada, foto_comprobante
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (curp_1, nombre_1, fecha_nac_1, curp_2, nombre_2, fecha_nac_2, estado, municipio, estilo, categoria, nombre_archivo))
        
        conexion.commit()
        conexion.close()

        # 5. Respuesta temporal de éxito
        return f"<h1>¡Registro Exitoso!</h1><p>La pareja ha sido inscrita en la categoría: <strong>{categoria}</strong></p>"
    
    # ==========================================
# 4. PANEL DE ADMINISTRACIÓN
# ==========================================
@app.route('/admin')
def panel_admin():
    # Nos conectamos a la base de datos
    conexion = sqlite3.connect('registro_huapango.db')
    cursor = conexion.cursor()
    
    # Traemos todos los registros, ordenados del más reciente al más antiguo
    cursor.execute('SELECT * FROM parejas ORDER BY id DESC')
    registros = cursor.fetchall()
    
    conexion.close()
    
    # Mandamos los datos a una nueva plantilla HTML
    return render_template('admin.html', parejas=registros)

# ==========================================
# 5. EXPORTAR A EXCEL (CSV)
# ==========================================
@app.route('/descargar_excel')
def descargar_excel():
    # 1. Nos conectamos a la base de datos
    conexion = sqlite3.connect('registro_huapango.db')
    cursor = conexion.cursor()
    cursor.execute('SELECT * FROM parejas ORDER BY id DESC')
    registros = cursor.fetchall()
    conexion.close()

    # 2. Creamos un archivo en la memoria del servidor
    salida = io.StringIO()
    # Agregamos este código (BOM) para que Excel lea perfectamente los acentos y las "ñ"
    salida.write('\ufeff')
    escritor = csv.writer(salida)

    # 3. Escribimos la fila de los encabezados
    escritor.writerow(['Folio', 'CURP 1', 'Nombre 1', 'Fecha Nac 1', 
                       'CURP 2', 'Nombre 2', 'Fecha Nac 2', 
                       'Estado', 'Municipio', 'Estilo', 
                       'Categoría', 'Archivo Comprobante', 'Fecha de Registro'])

    # 4. Volcamos todos los datos de la base de datos
    escritor.writerows(registros)

    # 5. Preparamos la respuesta para que el navegador descargue el archivo
    respuesta = make_response(salida.getvalue())
    respuesta.headers["Content-Disposition"] = "attachment; filename=Registros_Huapango_Zimapan.csv"
    respuesta.headers["Content-type"] = "text/csv"

    return respuesta

if __name__ == '__main__':
    app.run(debug=True)