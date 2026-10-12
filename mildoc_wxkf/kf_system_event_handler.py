from loguru import logger
from typing import Dict
from wecom_api import wecom_api
from prompt import WELCOME_MESSAGE


def handle_system_event_mock(event_data: Dict) -> None:
    """处理系统事件（模拟版本）"""
    logger.info(f"mock 处理系统事件 - 事件数据: {event_data}")
    return

def handle_system_event(event_data: Dict) -> None:
    """处理系统事件"""
    try:
        event_type = event_data.get('event_type', '')

        logger.info(f"处理系统事件: {event_type}, 事件数据: {event_data}")

        
        if event_type == 'enter_session':
            # 用户进入会话事件
            handle_enter_session_event(event_data)
        elif event_type == 'msg_send_fail':
            # 消息发送失败事件
            handle_send_fail_event(event_data)
        elif event_type == 'servicer_status_change':
            # 接待人员状态变更事件
            handle_servicer_status_change_event(event_data)
        elif event_type == 'session_status_change':
            # 会话状态变更事件
            handle_session_change_event(event_data)
        elif event_type == 'user_recall_msg':
            # 用户撤回消息事件
            handle_user_recall_event(event_data)
        elif event_type == 'servicer_recall_msg':
            # 接待人员撤回消息事件
            handle_servicer_recall_event(event_data)
        else:
            logger.info(f"不支持的事件类型: {event_type}，事件数据: {event_data}")
        
    except Exception as e:
        logger.error(f"处理系统事件异常: {e}")

def handle_enter_session_event(event_data: Dict) -> None:
    """处理用户进入会话事件"""
    try:
        external_userid = event_data.get('external_userid', '')
        open_kfid = event_data.get('open_kfid', '')
        scene = event_data.get('scene', '')
        welcome_code = event_data.get('welcome_code', '')
        
        logger.info(f"用户 {external_userid} 进入会话 - 场景: {scene} - 欢迎码: {welcome_code} - open_kfid: {open_kfid}")
        
        if not welcome_code: # 如果欢迎码为空，则不发送欢迎消息
            return
        # 发送欢迎消息
        wecom_api.send_event_response_message(welcome_code, WELCOME_MESSAGE)
        
    except Exception as e:
        logger.error(f"处理进入会话事件异常: {e}")

def handle_send_fail_event(event_data: Dict) -> None:
    """处理消息发送失败事件，暂不处理，仅做日志记录"""
    try:
        external_userid = event_data.get('external_userid', '')
        fail_msgid = event_data.get('fail_msgid', '')
        fail_type = event_data.get('fail_type', 0)
        
        fail_reasons = {
            0: "未知原因",
            1: "客服账号已删除",
            2: "应用已关闭",
            4: "会话已过期，超过48小时",
            5: "会话已关闭",
            6: "超过5条限制",
            7: "未绑定视频号",
            8: "主体未验证",
            9: "未绑定视频号且主体未验证",
            10: "用户拒收"
        }
        
        reason = fail_reasons.get(fail_type, "未知原因")
        logger.warning(f"消息发送失败 - 用户: {external_userid}, 消息ID: {fail_msgid}, 原因: {reason}")
        
    except Exception as e:
        logger.error(f"处理发送失败事件异常: {e}")

def handle_servicer_status_change_event(event_data: Dict) -> None:
    """处理接待人员状态变更事件，暂不处理，仅做日志记录"""
    try:
        servicer_userid = event_data.get('servicer_userid', '')
        status = event_data.get('status', 0)
        open_kfid = event_data.get('open_kfid', '')
        
        logger.info(f"接待人员 {servicer_userid} 状态变更: {status}, open_kfid: {open_kfid}")
        
    except Exception as e:
        logger.error(f"处理接待人员状态变更事件异常: {e}")

def handle_session_change_event(event_data: Dict) -> None:
    """处理会话状态变更，回复欢迎语或者结束语"""
    try:
        external_userid = event_data.get('external_userid', '')
        change_type = event_data.get('change_type', 0)
        msg_code = event_data.get('msg_code', '')
        
        if not all([external_userid, change_type, msg_code]):
            logger.error(f"会话状态变更事件缺少必要参数 - 用户: {external_userid}, 变更类型: {change_type}, 消息码: {msg_code}")
            return

        session_change_response_messages = {
            1: "您好！我是您的专属客服，很高兴为您服务！有什么可以帮助您的吗？", # 从接待池接入会话
            2: "您好！您的问题已转接给专家客服，请耐心等待。", # 转接会话
            3: "感谢您的咨询！如有其他问题，欢迎随时联系我们。祝您生活愉快！", # 结束会话
            4: "您好！有什么可以帮您？" # 重新接入已结束/已转接会话
        }
        
        response_message = session_change_response_messages.get(change_type, "您好！有什么可以帮您？")
        logger.info(f"会话状态变更 - 用户: {external_userid}, 变更类型: {change_type}, 响应消息: {response_message}")
        
        # 发送相应的回复语或结束语
        wecom_api.send_event_response_message(msg_code, response_message)
        
    except Exception as e:
        logger.error(f"处理会话状态变更事件异常: {e}")

def handle_user_recall_event(event_data: Dict) -> None:
    """处理用户撤回消息事件，暂不处理，仅做日志记录"""
    try:
        external_userid = event_data.get('external_userid', '')
        recall_msgid = event_data.get('recall_msgid', '')
        
        logger.info(f"客户 {external_userid} 撤回消息: {recall_msgid}")
        
    except Exception as e:
        logger.error(f"处理用户撤回消息事件异常: {e}")

def handle_servicer_recall_event(event_data: Dict) -> None:
    """处理接待人员撤回消息事件，暂不处理，仅做日志记录"""
    try:
        external_userid = event_data.get('external_userid', '')
        servicer_userid = event_data.get('servicer_userid', '')
        recall_msgid = event_data.get('recall_msgid', '')
        
        logger.info(f"接待人员 {servicer_userid} 撤回消息: {recall_msgid}, 客户: {external_userid}")
        
    except Exception as e:
        logger.error(f"处理接待人员撤回消息事件异常: {e}")
