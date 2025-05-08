from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3

app = Flask(__name__)
app.secret_key = 'segredo-vulneravel'  # Para sessão funcionar

# Rota de login (GET e POST)
@app.route('/', methods=['GET', 'POST'])
def login():
    erro = None
    if request.method == 'POST':
        username = request.form['usuario']
        password = request.form['senha']

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM admin WHERE username='%s' AND password='%s'" % (username, password))  # SQL Injection
        # cursor.execute("SELECT * FROM admin WHERE username=? AND password=?", (username, password))

        user = cursor.fetchone()
        conn.close()

        if user:
            session['user'] = username
            return redirect(url_for('dashboard'))
        else:
            erro = 'Usuário ou senha inválidos!'

    return render_template('login.html', erro=erro)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clientes")
    clientes = cursor.fetchall()
    conn.close()

    return render_template('dashboard.html', clientes=clientes)

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
        cursor.execute("INSERT INTO clientes (nome, email, saldo) VALUES (?, ?, ?)", (nome, email, saldo))
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))

    return render_template('form_cliente.html', acao='Criar', cliente=None)

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar_cliente(id):
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        saldo = request.form['saldo']
        cursor.execute("UPDATE clientes SET nome=?, email=?, saldo=? WHERE id=?", (nome, email, saldo, id))
        conn.commit()
        conn.close()
        return redirect(url_for('dashboard'))

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
    return redirect(url_for('dashboard'))

# Função para inicializar o banco de dados
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
