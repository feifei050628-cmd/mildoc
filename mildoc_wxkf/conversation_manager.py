import time
import json
from loguru import logger
from connection_manager import get_connection
from typing import Dict


def message_exists(msgid: str) -> bool:
    """
    检查消息是否存在
    
    Args:
        msgid: 消息ID
        
    Returns:
        是否存在
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT 1 FROM conversation_messages WHERE msgid = %s',(msgid,)
                )
                return cursor.fetchone() is not None
                
    except Exception as e:
        logger.error(f"检查会话消息是否存在失败: {e}")
        return True

def message_insert(msgid: str, open_kfid: str, external_userid: str, servicer_userid: str,
                    send_time: int, origin: int, msgtype: str, msgbody: Dict) -> bool:
    """
    插入会话消息
    
    Args:
        msgid: 消息ID
        open_kfid: 客服账号ID
        external_userid: 外部用户ID
        servicer_userid: 服务人员ID
        send_time: 消息发送时间
        origin: 消息来源
        msgtype: 消息类型
        msgbody: 原始消息体
        
    Returns:
        是否成功插入
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO conversation_messages (msgid, open_kfid, external_userid, servicer_userid, send_time, origin, msgtype, msgbody)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (msgid, open_kfid, external_userid, servicer_userid, send_time, origin, msgtype, json.dumps(msgbody)))
                conn.commit()
                return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"会话消息插入失败: {e}")
        return False

def message_recently(open_kfid: str, external_userid: str, limit: int = 10) -> list:
    """
    获取最近会话消息
    
    Args:
        open_kfid: 客服账号ID
        external_userid: 外部用户ID
        limit: 获取消息数量
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT origin, send_time, msgbody FROM conversation_messages WHERE open_kfid = %s AND external_userid = %s AND msgtype = %s AND origin in (3, 5, 666) ORDER BY send_time DESC LIMIT %s',(open_kfid, external_userid, 'text', limit))
                return cursor.fetchall()
    except Exception as e:
        logger.error(f"获取最近会话消息失败: {e}")
        return []



if __name__ == "__main__":
    print(message_exists(msgid="1234567890"))
    # print(message_insert(msgid="1234567890" + str(time.time()), open_kfid="1234567890", external_userid="1234567890", servicer_userid="1234567890", send_time=1234567890, origin=3, msgtype="text", msgbody={"text": "test"}))
    # print(message_insert(msgid="1234567890" + str(time.time()), open_kfid="1234567890", external_userid="1234567890", servicer_userid="1234567890", send_time=1234567890, origin=5, msgtype="text", msgbody={"text": "test"}))
    # print(message_insert(msgid="1234567890" + str(time.time()), open_kfid="1234567890", external_userid="1234567890", servicer_userid="1234567890", send_time=1234567890, origin=666, msgtype="text", msgbody={"text": "test"}))
    print(message_recently(open_kfid="1234567890", external_userid="1234567890", limit=10))