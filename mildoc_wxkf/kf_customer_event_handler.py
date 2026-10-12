from loguru import logger
from wecom_api import wecom_api
from typing import Dict
from generate_service import get_generate_service
from conversation_manager import message_insert
from uuid import uuid4
import time
import os
from dotenv import load_dotenv


load_dotenv()

WECOM_KF_MAX_REPLY_LENGTH = int(os.getenv('WECOM_KF_MAX_REPLY_LENGTH', '2000'))
WECOM_KF_DEFAULT_SERVICER = os.getenv('WECOM_KF_DEFAULT_SERVICER')


def handle_customer_event_mock(msgid: str, open_kfid: str, external_userid: str, send_time: int, origin: int, servicer_userid: str, msgtype: str, msgbody: Dict) -> bool:
    """
    处理客户发送的消息（模拟版本）
    
    Args:
        msgid: 消息ID
        open_kfid: 客服账号ID
    """
    logger.info(f"mock 处理客户发送的消息 - msgid: {msgid}, open_kfid: {open_kfid}, external_userid: {external_userid}, send_time: {send_time}, origin: {origin}, servicer_userid: {servicer_userid}, msgtype: {msgtype}, msgbody: {msgbody}")
    return True

def handle_customer_event(msgid: str, open_kfid: str, external_userid: str, send_time: int, origin: int, servicer_userid: str, msgtype: str, msgbody: Dict) -> bool:
    """
    处理客户发送的消息
    
    Returns:
        是否发送了回复
    """

    logger.info(f"处理客户发送的消息 - msgid: {msgid}, open_kfid: {open_kfid}, external_userid: {external_userid}, send_time: {send_time}, origin: {origin}, servicer_userid: {servicer_userid}, msgtype: {msgtype}, msgbody: {msgbody}")
    
    try:

        service_state = get_service_session_state(external_userid, open_kfid)

        if (service_state != 1 and service_state != 0):
            # 如果不是智能助手接待状态，则不处理
            logger.info(f"非智能助手接待状态，不处理消息 - open_kfid: {open_kfid}, 客户: {external_userid}")
            return False
        
        if msgtype == 'text':
            # 处理文本消息，使用智能回复生成回复内容
            content = msgbody.get('content', '')
            
            logger.info(f"收到客户文本消息: {content}")
            
            if '转人工' in content:
                # 转人工
                reply_content = "收到您的转人工请求，我会尽快转接人工服务。"
                send_kf_reply(external_userid, open_kfid, reply_content, msgid)

                if WECOM_KF_DEFAULT_SERVICER: # 如果配置了默认接待人员，则转接给默认接待人员    
                    uodate_service_session_state_to_servicer(external_userid, open_kfid, WECOM_KF_DEFAULT_SERVICER)
                else: # 否则转接给接待池
                    update_service_session_state_to_service_pool(external_userid, open_kfid)

                return True

            # 生成智能回复
            reply_content = get_generate_service().generate_response(content)
            send_kf_reply(external_userid, open_kfid, reply_content, msgid)
            return True

        if msgtype in ['image', 'voice', 'video', 'file']:
            # 处理多媒体消息，暂不处理，仅作简单回复收到消息
            replies = {
                'image': '''📷 收到您发送的图片，感谢分享！''',
                
                'voice': '''🎤 收到您的语音消息，感谢您的留言！''',
                
                'video': '''🎬 收到您发送的视频，感谢分享！''',
                
                'file': '''📎 收到您发送的文件，感谢分享！'''
            }
            reply_content = replies.get(msgtype, '收到您的消息，感谢分享！')
            send_kf_reply(external_userid, open_kfid, reply_content, msgid)
            return True
        
        if msgtype == 'location':
            # 处理位置消息，暂不处理，仅作简单回复收到消息
            name = msgbody.get('name', '')
            address = msgbody.get('address', '')
            reply_content = f"📍 收到您分享的位置：{name}\n地址：{address}\n感谢分享！"
            send_kf_reply(external_userid, open_kfid, reply_content, msgid)
            return True
        
        if msgtype == 'link':
            # 处理链接消息，暂不处理，仅作简单回复收到消息
            title = msgbody.get('title', '')
            reply_content = f"🔗 收到您分享的链接：{title}\n感谢分享！"
            send_kf_reply(external_userid, open_kfid, reply_content, msgid)
            return True
        
        if msgtype == 'business_card':
            # 处理名片消息，暂不处理，仅作简单回复收到消息
            reply_content = "👤 收到您的名片，感谢分享联系方式！\n\n如有业务合作需求，我们会及时与您联系。"
            send_kf_reply(external_userid, open_kfid, reply_content, msgid)
            return True
        
        if msgtype == 'miniprogram':
            # 处理小程序消息，暂不处理，仅作简单回复收到消息
            title = msgbody.get('title', '')
            reply_content = f"📱 收到您分享的小程序：{title}\n感谢分享！"
            send_kf_reply(external_userid, open_kfid, reply_content, msgid)
            return True
        
        if msgtype == 'channels_shop_product':
            # 处理视频号商品消息，暂不处理，仅作简单回复收到消息
            title = msgbody.get('title', '')
            price = msgbody.get('sales_price', '')
            reply_content = f"🛍️ 收到您关注的商品：{title}\n价格：{price}分\n感谢分享！"
            send_kf_reply(external_userid, open_kfid, reply_content, msgid)
            return True
        
        if msgtype == 'channels_shop_order':
            # 处理视频号订单消息，暂不处理，仅作简单回复收到消息
            order_id = msgbody.get('order_id', '')
            state = msgbody.get('state', '')
            reply_content = f"📦 收到您的订单信息：{order_id}\n状态：{state}\n感谢分享！"
            send_kf_reply(external_userid, open_kfid, reply_content, msgid)
            return True
        
        logger.error(f"不支持的消息类型 - msgid: {msgid}, 类型: {msgtype}, 来源: {origin}, 客户: {external_userid}")
        return False
        
    except Exception as e:
        logger.error(f"处理客户消息异常: {e}")
        return False


def send_kf_reply(external_userid: str, open_kfid: str, content: str, reply_to_msgid: str) -> bool:
    """发送客服回复"""
    try:
        # 检查回复内容长度
        if len(content) > WECOM_KF_MAX_REPLY_LENGTH:
            content = content[:WECOM_KF_MAX_REPLY_LENGTH] + "...(内容过长已截断)"
        
        result = wecom_api.send_kf_text_message(external_userid, open_kfid, content)
        if result:
            logger.info(f"发送客服回复成功 - 用户: {external_userid}")
            save_reply_message_to_conversation(external_userid, open_kfid, content, reply_to_msgid)
            return True
        else:
            logger.error(f"发送客服回复失败 - 用户: {external_userid}")
            return False
    except Exception as e:
        logger.error(f"发送客服回复异常: {e}")
        return False

def get_service_session_state(external_userid: str, open_kfid: str) -> int:
    """获取服务会话状态"""
    try:
        result = wecom_api.get_service_session_state(external_userid, open_kfid)
        if result:
            logger.info(f"获取服务会话状态成功 - 用户: {external_userid}")
            logger.info(f"服务会话状态: {result}")
            return result.get('service_state', -1)
        else:
            logger.error(f"获取服务会话状态失败 - 用户: {external_userid}")
            return -1
    except Exception as e:
        logger.error(f"获取服务会话状态异常: {e}")
        return -1

def update_service_session_state_to_service_pool(external_userid: str, open_kfid: str) -> bool:
    """更新服务会话状态"""
    try:
        result = wecom_api.update_service_session_state(external_userid, open_kfid, 2) # 2: 转接会话进入接待池，后续由人工接待
        if result:
            logger.info(f"更新服务会话状态成功 - 用户: {external_userid}")
            return True
        else:
            logger.error(f"更新服务会话状态失败 - 用户: {external_userid}")
            return False
    except Exception as e:
        logger.error(f"更新服务会话状态异常: {e}")
        return False

def uodate_service_session_state_to_servicer(external_userid: str, open_kfid: str, servicer_userid: str) -> bool:
    """更新服务会话状态为接待人员"""
    try:
        result = wecom_api.update_service_session_state(external_userid, open_kfid, 3, servicer_userid)
        if result:
            logger.info(f"更新服务会话状态成功 - 用户: {external_userid}")
            return True
    except Exception as e:
        logger.error(f"更新服务会话状态异常: {e}")
        return False

def save_reply_message_to_conversation(external_userid: str, open_kfid: str, content: str, reply_to_msgid: str) -> bool:
    """保存回复消息到会话记录"""
    try:
        msgid = str(uuid4())
        send_time = int(time.time()) # 当前时间戳
        origin = 666 # 666: ai回复
        servicer_userid = 'geekpost-ai' # ai回复
        msgtype = 'text_from_ai' # 文本消息
        msgbody = {
            'content': content,
            'reply_to_msgid': reply_to_msgid
        }
        result = message_insert(msgid, open_kfid, external_userid, servicer_userid, send_time, origin, msgtype, msgbody)
        if result:
            logger.info(f"保存回复消息到会话记录成功 - 用户: {external_userid}")
            return True
        else:
            logger.error(f"保存回复消息到会话记录失败 - 用户: {external_userid}")
            return False
    except Exception as e:
        logger.error(f"保存回复消息到会话记录异常: {e}")
        return False