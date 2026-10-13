from loguru import logger
from typing import Tuple
from connection_manager import get_connection

def get_latest_kfid() -> str:
    """
    获取最近变更的kfid（有消息通知会更新 update_at 字段）

    Returns:
        kfid 字符串，不存在时为空字符串。
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT `open_kfid` FROM wxkf_cursors order by updated_at desc limit 1'
                )
                result = cursor.fetchone()
                if result:
                    return result['open_kfid']
                else:
                    return ""
                    
    except Exception as e:
        logger.error(f"获取微信客服 ID 失败: {e}")
        return ""


def get_cursor_and_token(open_kfid: str) -> Tuple[str, str]:
    """
    获取指定客服账号的微信客服同步游标
    
    Args:
        open_kfid: 客服账号ID
        
    Returns:
        kf_cursor字符串，kf_token字符串，如果不存在则返回空字符串
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT `kf_cursor`, `kf_token` FROM wxkf_cursors WHERE open_kfid = %s',(open_kfid,)
                )
                result = cursor.fetchone()
                if result:
                    return result['kf_cursor'], result['kf_token']
                else:
                    return ("", "")
                    
    except Exception as e:
        logger.error(f"获取微信客服{open_kfid}的同步游标和token失败: {e}")
        return ("", "")

def save_cursor(open_kfid: str, kf_cursor: str) -> bool:
    """
    保存指定客服账号的微信客服同步游标
    
    Args:
        open_kfid: 客服账号ID
        kf_cursor: 新的kf_cursor值
        
    Returns:
        是否成功保存
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO wxkf_cursors (`open_kfid`, `kf_cursor`) VALUES (%s, %s) ON DUPLICATE KEY UPDATE `kf_cursor` = %s
                ''', (open_kfid, kf_cursor, kf_cursor))
                conn.commit()
                return True
    except Exception as e:
        logger.error(f"保存微信客服同步游标失败: {e}")
        return False

def save_token(open_kfid: str, kf_token: str) -> bool:
    """
    保存指定客服账号的微信客服同步token
    
    Args:
        open_kfid: 客服账号ID
        kf_token: 新的kf_token值
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO wxkf_cursors (`open_kfid`, `kf_token`) VALUES (%s, %s) ON DUPLICATE KEY UPDATE `kf_token` = %s
                ''', (open_kfid, kf_token, kf_token))
                conn.commit()
                return True
    except Exception as e:
        logger.error(f"保存微信客服同步token失败: {e}")
        return False

if __name__ == "__main__":
    print(get_cursor_and_token(open_kfid="1234567890"))
    print(save_cursor(open_kfid="1234567890", kf_cursor="1234567890dd"))
    print(save_token(open_kfid="1234567890", kf_token="1234567890dd"))
    print(get_cursor_and_token(open_kfid="1234567890"))