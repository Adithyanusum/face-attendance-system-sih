"""Database connection helper using mysql-connector-python."""
import mysql.connector
from mysql.connector import pooling
from config import Config

_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="attendance_pool",
            pool_size=10,
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            charset="utf8mb4",
            autocommit=False,
        )
    return _pool


def get_connection():
    """Return a connection from the connection pool."""
    return _get_pool().get_connection()


def execute_query(query, params=None, fetch=True):
    """Execute *query* and return rows (list of dicts) when *fetch* is True."""
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query, params or ())
        if fetch:
            result = cursor.fetchall()
        else:
            conn.commit()
            result = cursor.lastrowid
        cursor.close()
        return result
    finally:
        conn.close()
