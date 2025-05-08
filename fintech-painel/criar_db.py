import sqlite3
from faker import Faker
import random

# Inicializa o gerador de dados
fake = Faker('pt_BR')

# Conecta/cria o banco
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Cria a tabela clientes
cursor.execute('''
    CREATE TABLE IF NOT EXISTS clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        email TEXT NOT NULL,
        saldo REAL NOT NULL
    )
''')

# Insere 20 clientes fictícios
for _ in range(20):
    nome = fake.name()
    email = fake.email()
    saldo = round(random.uniform(500.00, 10000.00), 2)
    cursor.execute("INSERT INTO clientes (nome, email, saldo) VALUES (?, ?, ?)", (nome, email, saldo))

conn.commit()
conn.close()

print("Banco de dados criado com sucesso com 20 clientes fictícios!")
