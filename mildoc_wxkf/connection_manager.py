from dbutils.pooled_db import PooledDB
import pymysql
import os
from dotenv import load_dotenv
load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_DATABASE = os.getenv('DB_DATABASE')

pool = PooledDB(
    creator=pymysql,
    maxconnections=6,
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_DATABASE,
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

def get_connection():
    return pool.connection()
