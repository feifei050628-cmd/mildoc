from loguru import logger
from connection_manager import get_connection


def exist_customer_info(external_userid: str) -> bool:
    """
    检查指定客户的信息是否存在
    
    Args:
        external_userid: 客户ID

    Returns:
        bool: 客户信息是否存在
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    'SELECT 1 FROM customer_info WHERE external_userid = %s',(external_userid,)
                )
                result = cursor.fetchone()
                if result:
                    return True
                else:
                    return False
    except Exception as e:
        logger.error(f"获取客户信息失败: {e}")
        return False

def save_customer_info(external_userid: str, name: str, avatar: str) -> bool:
    """
    保存客户信息
    
    Args:
        external_userid: 客户ID
        name: 客户名称
        avatar: 客户头像

    Returns:
        bool: 是否成功保存
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                    INSERT INTO customer_info (`external_userid`, `name`, `avatar`) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE `name` = %s, `avatar` = %s
                ''', (external_userid, name, avatar, name, avatar))
                conn.commit()
                return True
    except Exception as e:
        logger.error(f"保存客户信息失败: {e}")
        return False

def touch_customer_info(external_userid: str) -> bool:
    """
    更新客户信息最后更新时间
    Args:
        external_userid: 客户ID
    Returns:
        bool: 是否成功更新最后更新时间
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute('UPDATE customer_info SET `updated_at` = NOW() WHERE `external_userid` = %s', (external_userid,))
                conn.commit()
                return True
    except Exception as e:
        logger.error(f"更新客户信息最后更新时间失败: {e}")
        return False


if __name__ == "__main__":
    touch_customer_info(external_userid="1234567890")