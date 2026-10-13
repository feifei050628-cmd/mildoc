import time
import signal
from typing import Dict
from wecom_api import wecom_api
from cursor_manager import get_cursor_and_token, save_cursor, get_latest_kfid
from conversation_manager import message_insert, message_exists
from kf_customer_event_handler import handle_customer_event
from kf_system_event_handler import handle_system_event
from customer_manager import exist_customer_info, save_customer_info, touch_customer_info
from loguru import logger
import os
from dotenv import load_dotenv

load_dotenv()


# 全局变量，用于控制退出
shutdown_requested = False

# 处理shutdown信号
def _handle_shutdown_signal(signum, frame):
    global shutdown_requested
    shutdown_requested = True
    logger.info(f"收到shutdown信号 {signum}，退出oss_event_handler...")

# 设置信号处理
def _setup_signal_handlers():
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)


_last_kf_tokens: dict[str, str] = {}

def kf_event_handler() -> None:
    """
    处理客服事件，拉取并处理消息（优化版本）
    """
    try:

        
        # 从持久化存储获取该客服账号的最后cursor和token
        open_kfid = get_latest_kfid()
        next_cursor, token = get_cursor_and_token(open_kfid)
        has_more = 1
        limit = 100

        if open_kfid in _last_kf_tokens and _last_kf_tokens[open_kfid] == token:
            logger.debug(f"token未变化，跳过拉取客服消息 - OpenKfId: {open_kfid}")
            return
        

        _last_kf_tokens[open_kfid] = token

        #来自企业微信的接口文档：
        #是否还有更多数据。0-否；1-是。
        #不能通过判断msg_list是否空来停止拉取，可能会出现has_more为1，而msg_list为空的情况
        while has_more == 1:

            logger.info(f"开始拉取客服消息 - OpenKfId: {open_kfid}, next_cursor: {next_cursor}, token: {token}, Limit: {limit}")
            
            # 拉取消息
            result = wecom_api.sync_kf_messages(token, open_kfid, next_cursor, limit)
            if not result:
                logger.error("拉取客服消息失败")
                return
            
            msg_list = result.get('msg_list', [])
            next_cursor = result.get('next_cursor', '')
            has_more = result.get('has_more', 0)
            
            logger.info(f"拉取到 {len(msg_list)} 条客服消息，next_cursor: {next_cursor}, has_more: {has_more}")
            
            
            for msg in msg_list:
                try:
                    msgid = msg.get('msgid', '')
                    open_kfid_in_msg = msg.get('open_kfid', '')
                    external_userid = msg.get('external_userid', '')
                    send_time = msg.get('send_time', 0)
                    origin = msg.get('origin', 0)  # 3-微信客户发送 4-系统推送事件 5-接待人员发送
                    servicer_userid = msg.get('servicer_userid', '')
                    msgtype = msg.get('msgtype', 'unknown')
                    msgbody = msg.get(msgtype, {})

                    # 检查消息是否已处理（双重检查：内存缓存 + 数据库）
                    if message_exists(msgid):
                        logger.info(f"消息已处理，跳过: {msgid}")
                        continue

                    # 先保存会话记录
                    message_insert(msgid, open_kfid_in_msg, external_userid, servicer_userid, send_time, origin, msgtype, msgbody)
                    
                    # 保存客户信息
                    upsert_external_user_info(external_userid)

                    # 处理新消息
                    process_message(msgid, open_kfid_in_msg, external_userid, send_time, origin, servicer_userid, msgtype, msgbody)

                except Exception as e:
                    logger.error(f"处理单条客服消息异常: {e}")
                    continue
            
            # 保存cursor到持久化存储
            if next_cursor:   
                save_cursor(open_kfid, next_cursor)
                logger.info(f"已保存新cursor - OpenKfId: {open_kfid}, next_cursor: {next_cursor}")
            
        logger.info(f"客服消息处理完成 - 总拉取: {len(msg_list)}")
        return
        
    except Exception as e:
        logger.error(f"处理客服事件异常: {e}")
        return


def upsert_external_user_info(external_userid: str) -> None:
    """已存在则 touch，否则拉取企微详情并写入客户表。"""
    if not external_userid:
        return
    
    exist_customer = exist_customer_info(external_userid)
    if exist_customer:
        touch_customer_info(external_userid)
    else:
        external_user_info = wecom_api.get_external_user_basic_info(external_userid)
        if external_user_info:
            save_customer_info(external_user_info['external_userid'], external_user_info['name'], external_user_info['avatar'])
            logger.info(f"保存新客户信息成功 - external_userid: {external_userid}, name: {external_user_info['name']}, avatar: {external_user_info['avatar']}")
        else:
            logger.error(f"获取客户信息失败 - external_userid: {external_userid}")


def process_message(msgid: str, open_kfid: str, external_userid: str, send_time: int, origin: int, servicer_userid: str, msgtype: str, msgbody: Dict) -> bool:
    """
    处理单条客服消息（优化版本）
    
    Args:
        msgid: 消息ID
        open_kfid: 客服账号ID
        external_userid: 客户ID
        send_time: 消息发送时间
        origin: 消息来源
        servicer_userid: 服务人员ID
        msgtype: 消息类型
        msgbody: 消息体
    Returns:
        处理是否成功
    """
    try:

        
        logger.info(f"处理客服消息 - msgid: {msgid}, 类型: {msgtype}, 来源: {origin}, 客户: {external_userid}")
        
        # 检查消息时效性（仅对客户发送的消息进行时效检查）
        if not msg_is_alive(send_time):
            logger.info(f"消息超过时效限制，不予处理 - msgid: {msgid}, 消息时间: {send_time}")
            return False

        if origin == 3:    # 处理微信客户发送的消息
            handle_customer_event(msgid, open_kfid, external_userid, send_time, origin, servicer_userid, msgtype, msgbody)
            return True
        
        if origin == 4:                    # 处理系统事件
            handle_system_event(msgbody)
            return True
        
        if origin == 5:                    # 处理接待人员发送的消息
            logger.info(f"接待人员 {servicer_userid} 发送消息: {msgbody}")
            return True
        
        logger.info(f"不支持的消息类型 - msgid: {msgid}, 类型: {msgtype}, 来源: {origin}, 客户: {external_userid}")
        return False
    except Exception as e:
        logger.error(f"处理单条客服消息异常: {e}")
        return False

def msg_is_alive(send_time: int) -> bool:
    """检查消息是否在10分钟内发送"""
    current_time = int(time.time())
    message_age_seconds = current_time - send_time
    message_age_minutes = message_age_seconds / 60
    return message_age_minutes <= 10


if __name__ == "__main__":
    _setup_signal_handlers()
    logger.info("开始处理客服消息...")

    while not shutdown_requested:
        try:
            kf_event_handler()
            if not shutdown_requested:
                time.sleep(1)
        except Exception as e:
            if not shutdown_requested:
                logger.error(f"处理客服消息异常: {e}")
                time.sleep(1)

    logger.info("已退出")