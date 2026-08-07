import os
from flask import Flask, render_template, request, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import csv
import psycopg2 

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
# 🔑 TUS LLAVES DE BÓVEDA
# ========================================================
URL_BASE_DATOS = "postgresql://postgres.hszcoiulvjkuhhycodvd:Z!m4p4n_Huapang0@aws-1-us-east-1.pooler.supabase.com:5432/postgres"


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
    
    # NUEVO: Asegurarnos de que exista la tabla de jueces
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jueces (
            id SERIAL PRIMARY KEY,
            nombre_real TEXT,
            usuario TEXT UNIQUE,
            password TEXT
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

        # ¡MAGIA AQUÍ! Ya no subimos archivo a la nube, la respuesta es inmediata
        enlace_imagen = "Pago en efectivo el día del evento"

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
        cursor.close()
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
    if 'admin_logueado' not in session:
        return redirect(url_for('login'))

    conexion = psycopg2.connect(URL_BASE_DATOS)
    cursor = conexion.cursor()
    cursor.execute('SELECT * FROM parejas ORDER BY id DESC')
    datos = cursor.fetchall()
    
    # ACTUALIZACIÓN: Ahora también traemos el "estilo" de la base de datos
    cursor.execute('''
        SELECT id, categoria_asignada, nombre_1, nombre_2, estilo 
        FROM parejas 
        WHERE id NOT IN (SELECT DISTINCT folio_pareja FROM calificaciones)
        ORDER BY id ASC
    ''')
    parejas_disponibles = cursor.fetchall()
    conexion.close()
    
    return render_template('admin.html', parejas=datos, disponibles=parejas_disponibles)

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

# ==========================================
# NUEVO: MÓDULO DE GESTIÓN DE JUECES
# ==========================================
@app.route('/admin_jueces')
def admin_jueces():
    if 'admin_logueado' not in session:
        return redirect(url_for('login'))
        
    conexion = psycopg2.connect(URL_BASE_DATOS)
    cursor = conexion.cursor()
    cursor.execute("SELECT id, nombre_real, usuario, password FROM jueces ORDER BY id ASC")
    lista_jueces = cursor.fetchall()
    conexion.close()
    
    return render_template('jueces.html', jueces=lista_jueces)

@app.route('/agregar_juez', methods=['POST'])
def agregar_juez():
    if 'admin_logueado' not in session:
        return redirect(url_for('login'))
        
    nombre_real = request.form.get('nombre_real')
    usuario = request.form.get('usuario')
    password = request.form.get('password')
    
    conexion = psycopg2.connect(URL_BASE_DATOS)
    cursor = conexion.cursor()
    try:
        cursor.execute("INSERT INTO jueces (nombre_real, usuario, password) VALUES (%s, %s, %s)", 
                       (nombre_real, usuario, password))
        conexion.commit()
    except psycopg2.IntegrityError:
        conexion.rollback() # Ignora si el usuario ya existe para no chocar
    finally:
        cursor.close()
        conexion.close()
        
    return redirect('/admin_jueces')

@app.route('/eliminar_juez/<int:id_juez>')
def eliminar_juez(id_juez):
    if 'admin_logueado' not in session:
        return redirect(url_for('login'))
        
    conexion = psycopg2.connect(URL_BASE_DATOS)
    cursor = conexion.cursor()
    
    # 1. Liberamos el candado: Borramos las calificaciones de prueba que haya dado este juez
    cursor.execute("DELETE FROM calificaciones WHERE id_juez = %s", (id_juez,))
    
    # 2. Ahora sí, borramos al juez sin que el servidor marque error
    cursor.execute("DELETE FROM jueces WHERE id = %s", (id_juez,))
    
    conexion.commit()
    cursor.close()
    conexion.close()
    
    return redirect('/admin_jueces')

# ==========================================
# MÓDULO DEL JURADO CALIFICADOR
# ==========================================

@app.route('/juez')
def juez_login():
    # Si el juez ya había iniciado sesión, lo mandamos directo a calificar
    if 'juez_id' in session:
        return redirect('/pista_juez')
    return render_template('juez_login.html')

@app.route('/procesar_login_juez', methods=['POST'])
def procesar_login_juez():
    usuario = request.form.get('usuario')
    password = request.form.get('password')

    conexion = psycopg2.connect(URL_BASE_DATOS)
    cursor = conexion.cursor()
    
    # Buscamos al juez en la base de datos
    cursor.execute("SELECT id, nombre_real FROM jueces WHERE usuario = %s AND password = %s", (usuario, password))
    juez = cursor.fetchone()
    
    cursor.close()
    conexion.close()

    if juez:
        # Creamos una sesión segura para la tableta del juez
        session['juez_id'] = juez[0]
        session['juez_nombre'] = juez[1]
        return redirect('/pista_juez')
    else:
        return render_template('juez_login.html', error="Credenciales incorrectas. Intente de nuevo.")

@app.route('/pista_juez')
def pista_juez():
    if 'juez_id' not in session:
        return redirect('/juez')
    
    conexion = psycopg2.connect(URL_BASE_DATOS)
    cursor = conexion.cursor()
    
    cursor.execute("SELECT estado, categoria_actual, folio_1, folio_2, folio_3, folio_4 FROM pista_activa WHERE id = 1")
    semaforo = cursor.fetchone()
    
    # 🛡️ ESCUDO ANTI-ERROR 500: Si la tabla está vacía, no crasheamos
    if not semaforo:
        estado = 'inactiva'
        categoria = None
        folios_en_pista = []
    else:
        estado = semaforo[0]
        categoria = semaforo[1]
        folios_en_pista = [f for f in [semaforo[2], semaforo[3], semaforo[4], semaforo[5]] if f is not None]
    
    parejas_activas = []
    folios_ya_calificados = [] 
    
    if estado == 'calificando' and folios_en_pista:
        placeholders = ','.join(['%s'] * len(folios_en_pista))
        query = f"SELECT id, estilo FROM parejas WHERE id IN ({placeholders}) ORDER BY id"
        cursor.execute(query, tuple(folios_en_pista))
        parejas_activas = cursor.fetchall()
        
        query_calificados = f"SELECT folio_pareja FROM calificaciones WHERE id_juez = %s AND folio_pareja IN ({placeholders})"
        cursor.execute(query_calificados, [session['juez_id']] + folios_en_pista)
        folios_ya_calificados = [row[0] for row in cursor.fetchall()]
        
    cursor.close()
    conexion.close()
    
    return render_template('pista_juez.html', 
                           nombre_juez=session['juez_nombre'],
                           estado=estado,
                           categoria=categoria,
                           parejas=parejas_activas,
                           folios_ya_calificados=folios_ya_calificados)

# ==========================================
# NUEVO: RUTA PARA RECIBIR Y GUARDAR PUNTOS
# ==========================================
@app.route('/guardar_calificacion', methods=['POST'])
def guardar_calificacion():
    if 'juez_id' not in session:
        return redirect('/juez')
        
    juez_id = session['juez_id']
    folio_pareja = request.form.get('folio_pareja')
    categoria = request.form.get('categoria')
    ronda = "Final" 
    
    # Capturamos los puntos de los deslizadores (si algo falla, ponemos 5 por defecto)
    try:
        vestuario = int(request.form.get('vestuario', 5))
        ritmo = int(request.form.get('ritmo', 5))
        precision = int(request.form.get('precision', 5))
        coreografia = int(request.form.get('coreografia', 5))
        dificultad = int(request.form.get('dificultad', 5))
        proyeccion = int(request.form.get('proyeccion', 5))
    except ValueError:
        return "Error en los valores", 400
        
    # Suma matemática total
    total = vestuario + ritmo + precision + coreografia + dificultad + proyeccion
    
    conexion = psycopg2.connect(URL_BASE_DATOS)
    cursor = conexion.cursor()
    
    try:
        # Inyectamos la calificación a Supabase
        cursor.execute("""
            INSERT INTO calificaciones (
                folio_pareja, id_juez, categoria, ronda, 
                vestuario, ritmo, precision_paso, coreografia, 
                dificultad, proyeccion, total
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (folio_pareja, juez_id, categoria, ronda, vestuario, ritmo, precision, coreografia, dificultad, proyeccion, total))
        
        conexion.commit()
    except Exception as e:
        conexion.rollback()
        # Si choca con el candado UNIQUE de la base de datos, lo ignoramos de forma segura
    finally:
        cursor.close()
        conexion.close()
        
    # Recargamos la pantalla del juez al instante
    return redirect('/pista_juez')

@app.route('/logout_juez')
def logout_juez():
    # Destruimos la sesión de la tableta
    session.pop('juez_id', None)
    session.pop('juez_nombre', None)
    return redirect('/juez')

# ==========================================
# MÓDULO DE CONTROL DE PISTA (ADMINISTRADOR)
# ==========================================

@app.route('/activar_pista', methods=['POST'])
def activar_pista():
    if 'admin_logueado' not in session:
        return redirect(url_for('login'))
    
    categoria = request.form.get('categoria')
    f1 = request.form.get('folio_1') if request.form.get('folio_1') else None
    f2 = request.form.get('folio_2') if request.form.get('folio_2') else None
    f3 = request.form.get('folio_3') if request.form.get('folio_3') else None
    f4 = request.form.get('folio_4') if request.form.get('folio_4') else None
    
    conexion = psycopg2.connect(URL_BASE_DATOS)
    cursor = conexion.cursor()
    
    # 🛡️ ESCUDO: Si no existe el registro de la pista, lo creamos desde cero
    cursor.execute("SELECT id FROM pista_activa WHERE id = 1")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO pista_activa (id, categoria_actual, folio_1, folio_2, folio_3, folio_4, estado, ultima_actualizacion) 
            VALUES (1, %s, %s, %s, %s, %s, 'calificando', CURRENT_TIMESTAMP)
        """, (categoria, f1, f2, f3, f4))
    else:
        cursor.execute("""
            UPDATE pista_activa 
            SET categoria_actual = %s, folio_1 = %s, folio_2 = %s, folio_3 = %s, folio_4 = %s, 
                estado = 'calificando', ultima_actualizacion = CURRENT_TIMESTAMP
            WHERE id = 1
        """, (categoria, f1, f2, f3, f4))
    
    conexion.commit()
    cursor.close()
    conexion.close()
    
    return redirect(url_for('panel_admin'))

@app.route('/desactivar_pista', methods=['POST'])
def desactivar_pista():
    if 'admin_logueado' not in session:
        return redirect(url_for('login'))
        
    conexion = psycopg2.connect(URL_BASE_DATOS)
    cursor = conexion.cursor()
    
    cursor.execute("UPDATE pista_activa SET estado = 'inactiva' WHERE id = 1")
    
    conexion.commit()
    cursor.close()
    conexion.close()
    
    return redirect(url_for('panel_admin'))

# ==========================================
# MÓDULO DE RESULTADOS Y GANADORES
# ==========================================
@app.route('/resultados')
def panel_resultados():
    # Candado de seguridad
    if 'admin_logueado' not in session:
        return redirect(url_for('login'))

    conexion = psycopg2.connect(URL_BASE_DATOS)
    cursor = conexion.cursor()
    
    # 1. Consulta SQL que suma los puntos de todos los jueces y los ordena
    cursor.execute("""
        SELECT 
            p.id as folio, 
            p.nombre_1, 
            p.nombre_2, 
            p.municipio, 
            p.estado,
            p.estilo,
            p.categoria_asignada,
            SUM(c.total) as puntaje_total,
            COUNT(c.id_juez) as jueces_evaluadores
        FROM parejas p
        INNER JOIN calificaciones c ON p.id = c.folio_pareja
        GROUP BY p.id, p.nombre_1, p.nombre_2, p.municipio, p.estado, p.estilo, p.categoria_asignada
        ORDER BY p.categoria_asignada, puntaje_total DESC
    """)
    
    datos_crudos = cursor.fetchall()
    conexion.close()

    # 2. Separamos los resultados en "cajitas" por categoría para mandarlos limpios al HTML
    resultados_por_categoria = {
        "Pequeños Huapangueros": [],
        "Infantil": [],
        "Juvenil": [],
        "Adultos": []
    }
    
    for fila in datos_crudos:
        categoria = fila[6]
        if categoria in resultados_por_categoria:
            resultados_por_categoria[categoria].append(fila)

    return render_template('resultados.html', resultados=resultados_por_categoria)

# ==========================================
# ZONA DE PELIGRO: LIMPIEZA DE BASE DE DATOS
# ==========================================
@app.route('/limpiar_base', methods=['POST'])
def limpiar_base():
    # Solo el administrador puede usar este botón
    if 'admin_logueado' not in session:
        return redirect(url_for('login'))
        
    conexion = psycopg2.connect(URL_BASE_DATOS)
    cursor = conexion.cursor()
    
    # 1. Borramos TODAS las calificaciones registradas
    cursor.execute("DELETE FROM calificaciones")
    
    # 2. Apagamos el semáforo para que quede todo limpio
    cursor.execute("UPDATE pista_activa SET estado = 'inactiva' WHERE id = 1")
    
    conexion.commit()
    cursor.close()
    conexion.close()
    
    # Regresamos al panel
    return redirect(url_for('panel_admin'))

@app.route('/limpiar_participantes', methods=['POST'])
def limpiar_participantes():
    # Solo el administrador puede usar este botón
    if 'admin_logueado' not in session:
        return redirect(url_for('login'))
        
    conexion = psycopg2.connect(URL_BASE_DATOS)
    cursor = conexion.cursor()
    
    try:
        # TRUNCATE es el borrador maestro de PostgreSQL.
        # RESTART IDENTITY: Obliga a que el ID (Folio) vuelva a empezar en 1.
        # CASCADE: Si hay calificaciones ligadas a estas parejas, también las borra por seguridad.
        cursor.execute("TRUNCATE TABLE parejas, calificaciones RESTART IDENTITY CASCADE;")
        
        # Apagamos la pista
        cursor.execute("UPDATE pista_activa SET estado = 'inactiva' WHERE id = 1")
        
        conexion.commit()
    except Exception as e:
        conexion.rollback()
        print(f"Error detectado al limpiar: {e}") # Esto nos avisará en la terminal negra si algo falla
    finally:
        cursor.close()
        conexion.close()
        
    return redirect(url_for('panel_admin'))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)