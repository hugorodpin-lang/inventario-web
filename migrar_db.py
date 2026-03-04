"""
Script de migración para agregar la columna stock_apartado a la tabla producto
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'instance', 'inventario.db')

def migrate():
    """Agrega la columna stock_apartado si no existe"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Verificar si la columna existe
    cursor.execute("PRAGMA table_info(producto)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'stock_apartado' not in columns:
        print("Agregando columna stock_apartado...")
        cursor.execute("ALTER TABLE producto ADD COLUMN stock_apartado INTEGER DEFAULT 0")
        conn.commit()
        print("¡Migración completada!")
    else:
        print("La columna stock_apartado ya existe.")
    
    conn.close()

if __name__ == '__main__':
    migrate()

