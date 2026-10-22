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
    获取最近会话消息（按时间正序返回，便于直接组装上下文）

    修复说明：原实现仅查询 msgtype = 'text'，而 AI 回复落库时使用的 msgtype 是
    'text_from_ai'，导致历史中永远缺少 AI 的发言，多轮上下文只有用户单边内容。

    Args:
        open_kfid: 客服账号ID
        external_userid: 外部用户ID
        limit: 获取消息数量

    Returns:
        list: 按 send_time 升序排列的消息记录
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                # 先按时间倒序取最近 N 条，再在内存中反转成正序
                cursor.execute(
                    'SELECT origin, send_time, msgbody FROM conversation_messages '
                    'WHERE open_kfid = %s AND external_userid = %s '
                    'AND msgtype in (%s, %s) AND origin in (3, 5, 666) '
                    'ORDER BY send_time DESC LIMIT %s',
                    (open_kfid, external_userid, 'text', 'text_from_ai', limit))
                rows = cursor.fetchall()
                return list(reversed(rows)) if rows else []
    except Exception as e:
        logger.error(f"获取最近会话消息失败: {e}")
        return []


def build_history_lines(open_kfid: str, external_userid: str, limit: int = 10) -> list:
    """
    将最近会话组装成可直接注入 Prompt 的历史对话行

    Args:
        open_kfid: 客服账号ID
        external_userid: 外部用户ID
        limit: 取最近多少条

    Returns:
        list[str]: 形如 ["客户: xxx", "AI: yyy"] 的历史行
    """
    # origin: 3-客户 / 5-人工客服 / 666-AI
    role_map = {3: "客户", 5: "人工客服", 666: "AI"}

    lines = []
    for row in message_recently(open_kfid, external_userid, limit=limit):
        try:
            msgbody = row.get('msgbody')
            if isinstance(msgbody, str):
                msgbody = json.loads(msgbody)
            content = (msgbody or {}).get('content', '') if isinstance(msgbody, dict) else ''
            content = (content or '').strip()
            if not content:
                continue
            role = role_map.get(row.get('origin'), "客户")
            lines.append(f"{role}: {content}")
        except Exception as e:
            logger.error(f"解析历史会话消息失败: {e}")
            continue

    return lines


if __name__ == "__main__":
    print(message_exists(msgid="1234567890"))
    print(message_recently(open_kfid="1234567890", external_userid="1234567890", limit=10))
    print(build_history_lines(open_kfid="1234567890", external_userid="1234567890", limit=10))
