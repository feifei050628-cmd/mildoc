import sys
import os
import pymysql
from dbutils.pooled_db import PooledDB
from loguru import logger
from dataclasses import dataclass
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

DB_HOST = os.getenv('DB_HOST')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_DATABASE = os.getenv('DB_DATABASE')

@dataclass
class CustomerInfo:
    external_userid: str
    name: str
    avatar: str
    updated_at: datetime

@dataclass
class ConversationMessage:
    id: int
    msgid: str
    open_kfid: str
    external_userid: str
    servicer_userid: str
    send_time: int
    origin: int
    msgtype: str
    msgbody: dict

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

def list_messages(start_id:int = -1, limit:int = 10, external_userid:str = None) -> tuple[list[ConversationMessage], int]:
    """
    获取会话消息列表
    
    Args:
        start_id: 开始ID, -1表示从最新消息开始
        limit: 获取消息数量
        external_userid: 外部用户ID

    Returns:
        messages: 会话消息列表
        min_id: 最小ID
    """
    if limit <= 0:
        return [], start_id

    where_clause = "1=1"

    if start_id >= 0:
        where_clause += f" AND id < {start_id}"

    if external_userid:
        where_clause += f" AND external_userid = '{external_userid}'"

    messages = []
    min_id = sys.maxsize

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f'SELECT id, msgid, open_kfid, external_userid, servicer_userid, send_time, origin, msgtype, msgbody FROM conversation_messages WHERE {where_clause} ORDER BY id DESC LIMIT {limit}')
                
                for message in cursor.fetchall():
                    messages.append(ConversationMessage(**message))
                    if message['id'] < min_id:
                        min_id = message['id']
                return messages, min_id
    except Exception as e:
        logger.error(f"获取会话消息列表失败: {e}")
        return [], start_id


def list_customer_info_recently(limit: int = 100) -> list[CustomerInfo]:
    """
    获取最近更新的客户信息
    Args:
        limit: 获取客户数量

    Returns:
        list[CustomerInfo]: 客户信息列表
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('SELECT `external_userid`, `name`, `avatar`, `updated_at` FROM customer_info ORDER BY `updated_at` DESC LIMIT %s', (limit,))
                results = cursor.fetchall()
                return [CustomerInfo(external_userid=result['external_userid'], name=result['name'], avatar=result['avatar'], updated_at=result['updated_at']) for result in results]
    except Exception as e:
        logger.error(f"获取最近更新的客户信息失败: {e}")
        return []


if __name__ == "__main__":
    from pprint import pprint
    customer_info_list = list_customer_info_recently(limit=10)
    pprint(customer_info_list)

