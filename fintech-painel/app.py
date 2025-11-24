import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
from psycopg2.extras import RealDictCursor

# --- IMPORTS DO SSO DO CÓDIGO ANTIGO ---
import jwt
import datetime
from google.oauth2 import id_token
from google.auth.transport import requests

from flask_dance.contrib.google import make_google_blueprint, google


# ===========================
#  LOG GLOBAL DEDO-DURO
# ===========================
import logging

logging.basicConfig(
    filename="safebank.log",
    level=logging.INFO,
    format="%(asctime)s | IP: %(ip)s | USER: %(user)s | EVENTO: %(msg)s"
)

# Função que registra qualquer evento
def registrar_evento(msg, user=None):
    try:
        logging.info(
            "",
            extra={
                "ip": request.remote_addr if request else "SEM IP",
                "user": user if user else session.get("user", "ANÔNIMO"),
                "msg": msg
            }
        )
    except:
        pass  # evita crash caso o request não exista
# ===================================================


app = Flask(__name__)
app.secret_key = "segredo-padrao-para-dev"

# --- Chave secreta para gerar o JWT do admin ---
SECRET_KEY = "supersecreto123"


# --- Função para gerar token JWT do admin ---
def gerar_token_admin(admin):
    payload = {
        "sub": str(admin["id"]),
        "username": admin["username"],
        "role": "admin",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")

    # LOG: geração de token
    registrar_evento(f"TOKEN JWT GERADO PARA ADMIN {admin['username']}")

    return token


# --- Função para validar o token do Google ---
def verificar_token_google(token, CLIENT_ID):
    try:
        info = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            CLIENT_ID
        )
        return info
    except Exception:
        registrar_evento("LOGIN GOOGLE — TOKEN INVÁLIDO")
        return None


# --- CONFIGURAÇÃO DO POSTGRESQL ---
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        registrar_evento("BANCO CONECTADO")
        return conn
    except Exception as e:
        registrar_evento(f"ERRO AO CONECTAR AO BANCO: {e}")
        return None



# ===========================
#      LOGIN PRINCIPAL
# ===========================
@app.route("/", methods=["GET", "POST"])
def login():
    erro = None

    if "security_mode" not in session:
        session["security_mode"] = "seguro"

    # LOG: acesso à página de login
    registrar_evento("ACESSOU A PÁGINA DE LOGIN")

    if request.method == "POST":
        username = request.form["usuario"]
        password = request.form["senha"]

        # LOG: tentativa de login (independente de resultado)
        registrar_evento(f"TENTATIVA DE LOGIN: {username}", user=username)

        conn = get_db_connection()
        if not conn:
            return "Erro ao conectar ao banco.", 500
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        mode = session.get("security_mode", "seguro")
        user = None

        if mode == "inseguro":
            try:
                query = f"SELECT * FROM admin WHERE username='{username}' AND password='{password}'"
                cursor.execute(query)
                user = cursor.fetchone()

                registrar_evento("EXECUTOU QUERY MODO INSEGURO (VULNERÁVEL)")

            except Exception as e:
                registrar_evento(f"ERRO SQL (modo inseguro): {e}")
                erro = "Erro ao processar login (modo inseguro)."

        else:
            try:
                query = "SELECT * FROM admin WHERE username=%s AND password=%s"
                cursor.execute(query, (username, password))
                user = cursor.fetchone()

                registrar_evento("EXECUTOU QUERY MODO SEGURO")

            except Exception as e:
                registrar_evento(f"ERRO SQL (modo seguro): {e}")
                erro = "Erro ao processar login (modo seguro)."

        cursor.close()
        conn.close()

        if user:
            session["user"] = user["username"]

            # LOG: login bem sucedido
            registrar_evento("LOGIN OK", user=username)

            token_admin = gerar_token_admin(user)
            return redirect(url_for("dashboard"))

        else:
            # LOG: login falhou
            registrar_evento("LOGIN FALHOU — usuário ou senha inválidos", user=username)

            if not erro:
                erro = "Usuário ou senha inválidos!"

    return render_template("login.html", erro=erro)

# ===========================
#  GOOGLE SSO (blueprint)
# ===========================
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

# ===========================
#  ROTA PARA ALTERNAR MODO
# ===========================
@app.route("/toggle_mode", methods=["POST"])
def toggle_mode():
    # alterna o modo e registra evento
    if session.get("security_mode") == "seguro":
        session["security_mode"] = "inseguro"
        flash("Modo Inseguro (Vulnerável a SQL Injection) ATIVADO!", "warning")
    else:
        session["security_mode"] = "seguro"
        flash("Modo Seguro ATIVADO.", "success")

    # LOG: alteração de modo de segurança
    registrar_evento(f"ALTEROU MODO DE SEGURANÇA PARA: {session.get('security_mode')}", user=session.get("user"))

    return redirect(url_for("login"))


# ===========================
#  DASHBOARD (inclui SSO)
# ===========================
@app.route("/dashboard")
def dashboard():

    # LOG: acesso à rota dashboard (antes de verificar autenticação)
    registrar_evento("ACESSOU ROTA /dashboard")

    if "user" not in session:

        # se já tiver autorizado via Google, tenta validar token
        if google.authorized:
            token_google = google.token.get("id_token")

            CLIENT_ID = "481920209905-osru2ddlvvf017p6f40jj02al0cbu3eo.apps.googleusercontent.com"
            dados_validados = verificar_token_google(token_google, CLIENT_ID)

            # LOG: mostrar que chegou tentativa via google
            registrar_evento("TENTATIVA DE LOGIN VIA GOOGLE")

            # logs com dados validados (evite logar dados sensíveis completos)
            if dados_validados is None:
                # LOG: token inválido
                registrar_evento("LOGIN VIA GOOGLE FALHOU — TOKEN INVÁLIDO")
                return "Token inválido! Login recusado.", 401

            # login via google ok -> registra evento e seta session
            session["user"] = dados_validados.get("email")
            registrar_evento("LOGIN VIA GOOGLE OK", user=session.get("user"))

        else:
            # não autenticado -> redireciona para o fluxo do Google
            registrar_evento("REDIRECIONANDO PARA GOOGLE LOGIN")
            return redirect(url_for("google.login"))

    # parâmetros de paginação / busca
    pagina = int(request.args.get("pagina", 1))
    busca = request.args.get("busca", "").strip()
    por_pagina = 25
    offset = (pagina - 1) * por_pagina

    # LOG: parâmetros de visualização do dashboard
    registrar_evento(f"DASHBOARD: pagina={pagina} busca='{busca}'", user=session.get("user"))

    conn = get_db_connection()
    if not conn:
        registrar_evento("DASHBOARD: erro de conexão com o DB", user=session.get("user"))
        return "Erro de banco", 500
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    try:
        if busca:
            # LOG: busca efetuada
            registrar_evento(f"BUSCA NO DASHBOARD: '{busca}'", user=session.get("user"))

            cursor.execute("SELECT COUNT(*) FROM clientes WHERE nome ILIKE %s", (f"%{busca}%",))
            total_clientes = cursor.fetchone()["count"]

            cursor.execute(
                "SELECT * FROM clientes WHERE nome ILIKE %s ORDER BY id LIMIT %s OFFSET %s",
                (f"%{busca}%", por_pagina, offset),
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM clientes")
            total_clientes = cursor.fetchone()["count"]

            cursor.execute(
                "SELECT * FROM clientes ORDER BY id LIMIT %s OFFSET %s",
                (por_pagina, offset),
            )

        clientes = cursor.fetchall()
        total_paginas = (total_clientes + por_pagina - 1) // por_pagina

        # LOG: dashboard retornou resultados
        registrar_evento(f"DASHBOARD: retornou {len(clientes)} clientes (total {total_clientes})", user=session.get("user"))

    except Exception as e:
        # LOG: erro durante consulta no dashboard
        registrar_evento(f"ERRO NO DASHBOARD: {e}", user=session.get("user"))
        clientes = []
        total_paginas = 1

    cursor.close()
    conn.close()

    return render_template(
        "dashboard.html",
        clientes=clientes,
        pagina=pagina,
        total_paginas=total_paginas,
        busca=busca,
    )


# ===========================
#  CRUD CLIENTES
# ===========================
@app.route("/novo", methods=["GET", "POST"])
def novo_cliente():
    if "user" not in session:
        registrar_evento("ACESSO NÃO AUTORIZADO A /novo (sem sessão)")
        return redirect(url_for("login"))

    if request.method == "POST":
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO clientes (nome, email, saldo) VALUES (%s, %s, %s)",
                (request.form["nome"], request.form["email"], request.form["saldo"]),
            )
            conn.commit()

            # LOG: cliente criado
            registrar_evento(f"CRIADO CLIENTE: {request.form['nome']} (email={request.form['email']})", user=session.get("user"))

        except Exception as e:
            conn.rollback()
            registrar_evento(f"ERRO AO CRIAR CLIENTE: {e}", user=session.get("user"))
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for("dashboard"))

    # LOG: acesso ao form de novo cliente (GET)
    registrar_evento("ACESSOU FORMULARIO DE NOVO CLIENTE", user=session.get("user"))
    return render_template("form_cliente.html", acao="Criar", cliente=None)


@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar_cliente(id):
    if "user" not in session:
        registrar_evento("ACESSO NÃO AUTORIZADO A /editar (sem sessão)")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    if request.method == "POST":
        try:
            cursor.execute(
                "UPDATE clientes SET nome=%s, email=%s, saldo=%s WHERE id=%s",
                (
                    request.form["nome"],
                    request.form["email"],
                    request.form["saldo"],
                    id,
                ),
            )
            conn.commit()

            # LOG: edição de cliente
            registrar_evento(f"EDITADO CLIENTE ID={id} -> {request.form['nome']}", user=session.get("user"))

        except Exception as e:
            conn.rollback()
            registrar_evento(f"ERRO AO EDITAR CLIENTE ID={id}: {e}", user=session.get("user"))
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for("dashboard", pagina=request.args.get("pagina", 1)))

    # GET: busca cliente e mostra form
    cursor.execute("SELECT * FROM clientes WHERE id=%s", (id,))
    cliente = cursor.fetchone()
    cursor.close()
    conn.close()

    # LOG: acesso ao form de edição
    registrar_evento(f"ACESSOU FORMULARIO DE EDICAO CLIENTE ID={id}", user=session.get("user"))
    return render_template("form_cliente.html", acao="Editar", cliente=cliente)


@app.route("/excluir/<int:id>")
def excluir_cliente(id):
    if "user" not in session:
        registrar_evento("ACESSO NÃO AUTORIZADO A /excluir (sem sessão)")
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM clientes WHERE id=%s", (id,))
        conn.commit()

        # LOG: cliente excluído
        registrar_evento(f"EXCLUIDO CLIENTE ID={id}", user=session.get("user"))

    except Exception as e:
        conn.rollback()
        registrar_evento(f"ERRO AO EXCLUIR CLIENTE ID={id}: {e}", user=session.get("user"))
    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("dashboard"))


# ===========================
#  LOGOUT
# ===========================
@app.route("/logout")
def logout():
    # LOG: usuário fez logout (session cleared depois)
    registrar_evento("LOGOUT", user=session.get("user"))
    session.clear()
    flash("Você saiu da sua conta.", "success")
    return redirect(url_for("login"))


# ===========================
#  INIT DB (CRIA TABELAS P/ DEV)
# ===========================
def init_db():
    conn = get_db_connection()
    if not conn:
        registrar_evento("INIT_DB: falha ao conectar", user=session.get("user"))
        return

    cursor = conn.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admin (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clientes (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                saldo DECIMAL(10,2) NOT NULL
            )
        """)

        cursor.execute("""
            INSERT INTO admin (username, password) 
            VALUES ('admin', '123') 
            ON CONFLICT DO NOTHING
        """)

        conn.commit()
        # LOG: init_db ok
        registrar_evento("INIT_DB: Tabelas criadas/inicializadas")

    except Exception as e:
        conn.rollback()
        registrar_evento(f"INIT_DB: ERRO: {e}")

    finally:
        cursor.close()
        conn.close()


# ===========================
#  EXECUÇÃO PRINCIPAL
# ===========================
if __name__ == "__main__":
    # opcional: inicializa DB ao rodar localmente
    init_db()
    registrar_evento("APLICACAO INICIALIZADA (main)", user=session.get("user"))
    app.run(debug=True)
