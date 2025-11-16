import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from google.oauth2 import id_token
from google.auth.transport import requests

from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3 

import jwt
import datetime

# Chave secreta para gerar o JWT do admin
SECRET_KEY = "supersecreto123"

# Função para gerar token JWT do admin
def gerar_token_admin(admin):
    payload = {
        "sub": str(admin["id"]),          # id do admin como string
        "username": admin["username"],
        "role": "admin",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)  # expira em 2h
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    print("\n===== TOKEN DO ADMIN =====")
    print(token)
    print("\n===== DADOS DECODIFICADOS =====")
    print(jwt.decode(token, SECRET_KEY, algorithms=["HS256"]))
    return token

# função para validar o token
def verificar_token_google(token, CLIENT_ID):
    try:
        info = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            CLIENT_ID
        )
        return info
    except Exception as e:
        print("TOKEN INVÁLIDO MEU NOBRE")
        return None

app = Flask(__name__)
app.secret_key = 'segredo-vulneravel'

# --- login com Google ---
from flask_dance.contrib.google import make_google_blueprint, google

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

# --- Rota de login ---
@app.route('/', methods=['GET', 'POST'])
def login():
    erro = None
    
    if 'security_mode' not in session:
        session['security_mode'] = 'seguro'

    if request.method == 'POST':
        username = request.form['usuario']
        password = request.form['senha']

        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        mode = session.get('security_mode', 'seguro')

        user = None

        if mode == 'inseguro':
            try:
                query = "SELECT * FROM admin WHERE username='%s' AND password='%s'" % (username, password)
                print(f"[MODO INSEGURO] Executando: {query}")
                cursor.execute(query)
                user = cursor.fetchone()
            except Exception as e:
                print(f"Erro no modo inseguro: {e}")
                erro = "Erro ao processar login (modo inseguro)."
        else:
            try:
                query = "SELECT * FROM admin WHERE username=? AND password=?"
                print(f"[MODO SEGURO] Executando: {query}")
                cursor.execute(query, (username, password))
                user = cursor.fetchone()
            except Exception as e:
                print(f"Erro no modo seguro: {e}")
                erro = "Erro ao processar login (modo seguro)."

        conn.close()

        if user:
            session['user'] = user['username']
            # gerando o token jwt do admin HEHE
            token_admin = gerar_token_admin(user)
            # printando dados do token
            decoded = jwt.decode(token_admin, SECRET_KEY, algorithms=["HS256"])
            print("\n===== TOKEN DO ADMIN (IMEDIATO) =====")
            print(token_admin)
            print("\n===== DADOS DECODIFICADOS (IMEDIATO) =====")
            print(decoded)

            return redirect(url_for('dashboard'))
        else:
            if not erro:
                erro = 'Usuário ou senha inválidos!'

    return render_template('login.html', erro=erro)

# alternar modo
@app.route('/toggle_mode', methods=['POST'])
def toggle_mode():
    if session.get('security_mode') == 'seguro':
        session['security_mode'] = 'inseguro'
        flash('Modo Inseguro (Vulnerável a SQL Injection) ATIVADO!', 'warning')
    else:
        session['security_mode'] = 'seguro'
        flash('Modo de Segurança ATIVADO. Aplicação protegida.', 'success')

    return redirect(url_for('login'))

# --- Dashboard com SSO Google ---
@app.route('/dashboard')
def dashboard():
    # Se não estiver logado localmente
    if 'user' not in session:
        # tenta autenticar pelo Google
        if google.authorized:
            token_google = google.token["id_token"]

            CLIENT_ID = "481920209905-osru2ddlvvf017p6f40jj02al0cbu3eo.apps.googleusercontent.com"
            dados_validados = verificar_token_google(token_google, CLIENT_ID)

            # print imediato do token do Google
            print("\n===== TOKEN DO GOOGLE (IMEDIATO) =====")
            print(token_google)
            print("\n===== DADOS VALIDADOS PELO GOOGLE (IMEDIATO) =====")
            print(dados_validados)

            if dados_validados is None:
                return "Token inválido! Login recusado.", 401

            session["user"] = dados_validados["email"]

        else:
            return redirect(url_for("google.login"))

    # Paginação
    pagina = int(request.args.get('pagina', 1))
    busca = request.args.get('busca', '').strip()
    por_pagina = 25
    offset = (pagina - 1) * por_pagina

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if busca:
        cursor.execute("SELECT COUNT(*) FROM clientes WHERE nome LIKE ?", (f'%{busca}%',))
        total_clientes = cursor.fetchone()[0]

        cursor.execute("SELECT * FROM clientes WHERE nome LIKE ? LIMIT ? OFFSET ?",
                       (f'%{busca}%', por_pagina, offset))
    else:
        cursor.execute("SELECT COUNT(*) FROM clientes")
        total_clientes = cursor.fetchone()[0]

        cursor.execute("SELECT * FROM clientes LIMIT ? OFFSET ?", (por_pagina, offset))

    clientes = cursor.fetchall()
    total_paginas = (total_clientes + por_pagina - 1) // por_pagina

    conn.close()

    return render_template('dashboard.html', clientes=clientes,
                           pagina=pagina, total_paginas=total_paginas,
                           busca=busca)

@app.route('/novo', methods=['GET', 'POST'])
def novo_cliente():
    if 'user' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        saldo = request.form['saldo']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO clientes (nome, email, saldo) VALUES (?, ?, ?)",
                       (nome, email, saldo))
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard', pagina=request.args.get('pagina', 1)))

    return render_template('form_cliente.html', acao='Criar', cliente=None)

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar_cliente(id):
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        saldo = request.form['saldo']
        cursor.execute("UPDATE clientes SET nome=?, email=?, saldo=? WHERE id=?",
                       (nome, email, saldo, id))
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard', pagina=request.args.get('pagina', 1)))

    cursor.execute("SELECT * FROM clientes WHERE id=?", (id,))
    cliente = cursor.fetchone()
    conn.close()
    return render_template('form_cliente.html', acao='Editar', cliente=cliente)

@app.route('/excluir/<int:id>')
def excluir_cliente(id):
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM clientes WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard', pagina=request.args.get('pagina', 1)))

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Você saiu da sua conta.', 'success')
    return redirect(url_for('login'))

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            email TEXT,
            saldo REAL
        )
    ''')

    cursor.execute("INSERT OR IGNORE INTO admin (id, username, password) VALUES (1, 'admin', '123')")
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
