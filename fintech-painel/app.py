import os
# Permite HTTP para testes locais do OAuth (remova em produção se tiver HTTPS)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
from psycopg2.extras import RealDictCursor
from flask_dance.contrib.google import make_google_blueprint, google

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "segredo-padrao-para-dev")

# --- CONFIGURAÇÃO DO BANCO DE DADOS (PostgreSQL) ---
# No Render, a variável DATABASE_URL é fornecida automaticamente.
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    """Cria e retorna uma conexão com o banco PostgreSQL."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Erro ao conectar ao PostgreSQL: {e}")
        return None

# --- LOGIN COM GOOGLE (SSO) ---
google_bp = make_google_blueprint(
    client_id="481920209905-osru2ddlvvf017p6f40jj02al0cbu3eo.apps.googleusercontent.com",
    client_secret="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",
    redirect_to="dashboard",
    scope=[
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
        "openid"
    ]
)
app.register_blueprint(google_bp, url_prefix="/login")

# --- ROTA PRINCIPAL (LOGIN) ---
@app.route('/', methods=['GET', 'POST'])
def login():
    erro = None
    
    # Define o modo padrão na sessão se não existir
    if 'security_mode' not in session:
        session['security_mode'] = 'seguro'

    if request.method == 'POST':
        username = request.form['usuario']
        password = request.form['senha']

        conn = get_db_connection()
        if not conn:
             return "Erro de conexão com o banco de dados.", 500

        # RealDictCursor permite acessar colunas por nome (ex: user['username'])
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        mode = session.get('security_mode', 'seguro')
        user = None

        if mode == 'inseguro':
            # --- MODO INSEGURO (VULNERÁVEL A SQLi) ---
            try:
                # AVISO: Vulnerabilidade intencional para fins educativos
                query = "SELECT * FROM admin WHERE username='%s' AND password='%s'" % (username, password)
                print(f"[MODO INSEGURO] Executando: {query}")
                cursor.execute(query)
                user = cursor.fetchone()
            except Exception as e:
                print(f"Erro SQL (Inseguro): {e}")
                erro = "Erro ao processar login (modo inseguro)."

        else:
            # --- MODO SEGURO (PROTEGIDO) ---
            try:
                # Uso de placeholders (%s) previne SQL Injection
                query = "SELECT * FROM admin WHERE username=%s AND password=%s"
                print(f"[MODO SEGURO] Executando: {query}")
                cursor.execute(query, (username, password))
                user = cursor.fetchone()
            except Exception as e:
                print(f"Erro SQL (Seguro): {e}")
                erro = "Erro ao processar login (modo seguro)."

        cursor.close()
        conn.close()

        if user:
            session['user'] = user['username']
            return redirect(url_for('dashboard'))
        else:
            if not erro:
                erro = 'Usuário ou senha inválidos!'

    return render_template('login.html', erro=erro)

# --- ROTA PARA ALTERNAR MODO DE SEGURANÇA ---
@app.route('/toggle_mode', methods=['POST'])
def toggle_mode():
    if session.get('security_mode') == 'seguro':
        session['security_mode'] = 'inseguro'
        flash('Modo Inseguro (Vulnerável a SQL Injection) ATIVADO!', 'warning')
    else:
        session['security_mode'] = 'seguro'
        flash('Modo de Segurança ATIVADO. Aplicação protegida.', 'success')
    return redirect(url_for('login'))

# --- DASHBOARD (PROTEGIDO) ---
@app.route('/dashboard')
def dashboard():
    # Verifica login local OU login Google
    if 'user' not in session:
        if google.authorized:
            try:
                resp = google.get("/oauth2/v2/userinfo")
                if resp.ok:
                    user_info = resp.json()
                    session['user'] = user_info['email']
                else:
                     return redirect(url_for("google.login"))
            except:
                return redirect(url_for("google.login"))
        else:
            return redirect(url_for('login')) # Redireciona para o login padrão se não estiver autenticado

    pagina = int(request.args.get('pagina', 1))
    busca = request.args.get('busca', '').strip()
    por_pagina = 25
    offset = (pagina - 1) * por_pagina

    conn = get_db_connection()
    if not conn: return "Erro de banco de dados", 500
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        if busca:
            cursor.execute("SELECT COUNT(*) FROM clientes WHERE nome ILIKE %s", (f'%{busca}%',))
            total_clientes = cursor.fetchone()['count']
            cursor.execute("SELECT * FROM clientes WHERE nome ILIKE %s ORDER BY id LIMIT %s OFFSET %s", (f'%{busca}%', por_pagina, offset))
        else:
            cursor.execute("SELECT COUNT(*) FROM clientes")
            total_clientes = cursor.fetchone()['count']
            cursor.execute("SELECT * FROM clientes ORDER BY id LIMIT %s OFFSET %s", (por_pagina, offset))

        clientes = cursor.fetchall()
        total_paginas = (total_clientes + por_pagina - 1) // por_pagina
    except Exception as e:
        print(f"Erro no dashboard: {e}")
        clientes = []
        total_paginas = 1
    finally:
        cursor.close()
        conn.close()

    return render_template('dashboard.html', clientes=clientes, pagina=pagina, total_paginas=total_paginas, busca=busca)

# --- CRUD CLIENTES ---
@app.route('/novo', methods=['GET', 'POST'])
def novo_cliente():
    if 'user' not in session: return redirect(url_for('login'))

    if request.method == 'POST':
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO clientes (nome, email, saldo) VALUES (%s, %s, %s)", 
                       (request.form['nome'], request.form['email'], request.form['saldo']))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))

    return render_template('form_cliente.html', acao='Criar', cliente=None)

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar_cliente(id):
    if 'user' not in session: return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    if request.method == 'POST':
        cursor.execute("UPDATE clientes SET nome=%s, email=%s, saldo=%s WHERE id=%s", 
                       (request.form['nome'], request.form['email'], request.form['saldo'], id))
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard', pagina=request.args.get('pagina', 1)))

    cursor.execute("SELECT * FROM clientes WHERE id=%s", (id,))
    cliente = cursor.fetchone()
    cursor.close()
    conn.close()
    return render_template('form_cliente.html', acao='Editar', cliente=cliente)

@app.route('/excluir/<int:id>')
def excluir_cliente(id):
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clientes WHERE id=%s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('dashboard'))

# --- LOGOUT ---
@app.route('/logout')
def logout():
    session.clear() # Limpa toda a sessão (incluindo token do Google)
    flash('Você saiu da sua conta.', 'success')
    return redirect(url_for('login'))

# --- INICIALIZAÇÃO DO BANCO (OPCIONAL) ---
def init_db():
    conn = get_db_connection()
    if not conn: return
    cursor = conn.cursor()
    # Cria tabelas se não existirem (SERIAL é o AUTO_INCREMENT do Postgres)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password VARCHAR(255) NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id SERIAL PRIMARY KEY,
            nome VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL,
            saldo DECIMAL(10, 2) NOT NULL
        )
    ''')
    # Tenta inserir admin (ON CONFLICT DO NOTHING evita erro se já existir)
    cursor.execute("INSERT INTO admin (username, password) VALUES ('admin', '123') ON CONFLICT DO NOTHING")
    conn.commit()
    cursor.close()
    conn.close()

if __name__ == '__main__':
    # No Render, não chamamos init_db() aqui a cada boot, 
    # mas para testes locais pode ser útil descomentar a linha abaixo:
    # init_db() 
    app.run(debug=True)

