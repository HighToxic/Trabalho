import psycopg2
from faker import Faker
import random

# --- CONFIGURAÇÃO DO BANCO POSTGRESQL ---
# Cole aqui a "External Database URL" do Render para rodar localmente
DB_URL = "postgresql://safebank_db_user:QXfuyF2EMBY1Ot0Sd7qzUblIQBuQXk4T@dpg-d48cq39r0fns73fvp370-a.oregon-postgres.render.com/safebank_db" 

print("Conectando ao PostgreSQL...")
try:
    conn = psycopg2.connect(DB_URL)
    cursor = conn.cursor()
    print("Conectado com sucesso!")

    # --- 1. Criação das Tabelas (Sintaxe PostgreSQL) ---
    # SERIAL é o AUTO_INCREMENT do Postgres
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) NOT NULL,
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

    # --- 2. Inserção do Admin Padrão ---
    cursor.execute("SELECT * FROM admin WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO admin (username, password) VALUES (%s, %s)", ('admin', '123'))
        print("Usuário admin criado.")
    else:
        print("Usuário admin já existe.")

    # --- 3. Povoando com Faker ---
    fake = Faker('pt_BR')
    print("Gerando 500 clientes fictícios...")

    for _ in range(500):
        nome = fake.name()
        email = fake.email()
        saldo = round(random.uniform(500.00, 10000.00), 2)
        cursor.execute("INSERT INTO clientes (nome, email, saldo) VALUES (%s, %s, %s)", (nome, email, saldo))

    conn.commit()
    cursor.close()
    conn.close()

    print("SUCESSO! Banco de dados PostgreSQL povoado!")

except Exception as e:
    print(f"Erro ao conectar ou inserir no PostgreSQL: {e}")
