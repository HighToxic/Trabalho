from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3

app = Flask(__name__)
# Chave secreta é essencial para a sessão funcionar
app.secret_key = 'segredo-vulneravel' 

# Rota de login (GET e POST)
@app.route('/', methods=['GET', 'POST'])
def login():
    erro = None
    
    # Define o modo padrão na sessão se não existir
    if 'security_mode' not in session:
        session['security_mode'] = 'seguro'

    if request.method == 'POST':
        username = request.form['usuario']
        password = request.form['senha']

        conn = sqlite3.connect('database.db')
        # Importante: row_factory para acessar colunas por nome
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()

        # Pega o modo de segurança da sessão
        mode = session.get('security_mode', 'seguro')
        
        user = None

        if mode == 'inseguro':
            # --- MODO INSEGURO (VULNERÁVEL) ---
            try:
                # AVISO: Vulnerabilidade de SQL Injection intencional
                query = "SELECT * FROM admin WHERE username='%s' AND password='%s'" % (username, password)
                print(f"[MODO INSEGURO] Executando: {query}") # Log para debug
                
                # Alguns drivers/versões do sqlite podem bloquear isso
                # Se der erro, pode ser necessário usar cursor.executescript(query)
                cursor.execute(query) 
                user = cursor.fetchone()

            except Exception as e:
                print(f"Erro no modo inseguro: {e}")
                erro = "Erro ao processar login (modo inseguro)."

        else:
            # --- MODO SEGURO (PROTEGIDO) ---
            try:
                # Consulta parametrizada previne SQL Injection
                query = "SELECT * FROM admin WHERE username=? AND password=?"
                print(f"[MODO SEGURO] Executando: {query}") # Log para debug
                
                cursor.execute(query, (username, password))
                user = cursor.fetchone()

            except Exception as e:
                print(f"Erro no modo seguro: {e}")
                erro = "Erro ao processar login (modo seguro)."

        conn.close()

        if user:
            session['user'] = user['username'] # Salva o usuário na sessão
            return redirect(url_for('dashboard'))
        else:
            if not erro: # Só define erro se não houver erro de sistema
                erro = 'Usuário ou senha inválidos!'

    # Passa o erro E o modo atual para o template
    return render_template('login.html', erro=erro)

# Rota para o botão "Alternar Modo"
@app.route('/toggle_mode', methods=['POST'])
def toggle_mode():
    # Pega o modo atual e inverte
    if session.get('security_mode') == 'seguro':
        session['security_mode'] = 'inseguro'
        # flash() envia uma mensagem para o próximo request
        flash('Modo Inseguro (Vulnerável a SQL Injection) ATIVADO!', 'warning')
    else:
        session['security_mode'] = 'seguro'
        flash('Modo de Segurança ATIVADO. Aplicação protegida.', 'success')

    # Redireciona de volta para a página de login
    return redirect(url_for('login'))


@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login'))

    pagina = int(request.args.get('pagina', 1))
    busca = request.args.get('busca', '').strip()  # pega o termo de busca da URL
    por_pagina = 25
    offset = (pagina - 1) * por_pagina

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row # Para acessar colunas por nome
    cursor = conn.cursor()

    if busca:
        # Conta total clientes filtrados pelo nome
        cursor.execute("SELECT COUNT(*) FROM clientes WHERE nome LIKE ?", (f'%{busca}%',))
        total_clientes = cursor.fetchone()[0]

        # Pega clientes filtrados para a página atual
        cursor.execute("SELECT * FROM clientes WHERE nome LIKE ? LIMIT ? OFFSET ?", (f'%{busca}%', por_pagina, offset))
    else:
        # Conta total clientes sem filtro
        cursor.execute("SELECT COUNT(*) FROM clientes")
        total_clientes = cursor.fetchone()[0]

        # Pega clientes sem filtro para a página atual
        cursor.execute("SELECT * FROM clientes LIMIT ? OFFSET ?", (por_pagina, offset))

    clientes = cursor.fetchall()
    total_paginas = (total_clientes + por_pagina - 1) // por_pagina

    conn.close()

    return render_template('dashboard.html', clientes=clientes, pagina=pagina, total_paginas=total_paginas, busca=busca)

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
        return redirect(url_for('dashboard', pagina=request.args.get('pagina', 1)))

    return render_template('form_cliente.html', acao='Criar', cliente=None)

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar_cliente(id):
    if 'user' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row # Para acessar colunas por nome
    cursor = conn.cursor()

    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        saldo = request.form['saldo']
        cursor.execute("UPDATE clientes SET nome=?, email=?, saldo=? WHERE id=?", (nome, email, saldo, id))
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

# --- NOVA ROTA DE LOGOUT ADICIONADA AQUI ---
@app.route('/logout')
def logout():
    # Remove o 'user' da sessão, efetivamente deslogando ele
    session.pop('user', None)
    # Envia uma mensagem de feedback para a tela de login
    flash('Você saiu da sua conta.', 'success')
    # Redireciona o usuário para a rota de login
    return redirect(url_for('login'))

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
    # Insere o admin apenas se ele não existir
    cursor.execute("INSERT OR IGNORE INTO admin (id, username, password) VALUES (1, 'admin', '123')")
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    app.run(debug=True)

