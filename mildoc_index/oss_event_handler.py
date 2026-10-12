import json
import time
import signal
from typing import Dict, Optional
import os
from dotenv import load_dotenv
from loguru import logger
from mns.account import Account
from oss_object_processor import process_oss_event, OSSEvent, OSSEventType
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

## 配置阿里云消息队列
MNS_ACCESS_KEY_ID = os.getenv("MNS_ACCESS_KEY_ID")
MNS_ACCESS_KEY_SECRET = os.getenv("MNS_ACCESS_KEY_SECRET")
MNS_ENDPOINT = os.getenv("MNS_ENDPOINT") 
MNS_QUEUE_NAME = os.getenv("MNS_QUEUE_NAME")

_mildoc_mns_queue = None


def _get_mildoc_mns_queue():
    global _mildoc_mns_queue
    if _mildoc_mns_queue is None:
        mns_account = Account(MNS_ENDPOINT, MNS_ACCESS_KEY_ID, MNS_ACCESS_KEY_SECRET)
        _mildoc_mns_queue = mns_account.get_queue(MNS_QUEUE_NAME)
    return _mildoc_mns_queue


      
def oss_event_handler() -> None:
    """
    监听 MNS 队列，接收 OSS 事件通知。
    """
    
    try:
        mildoc_mns_queue = _get_mildoc_mns_queue()

        while True:
            msg = mildoc_mns_queue.receive_message_with_str_body(wait_seconds=10)
            mildoc_mns_queue.delete_message(msg.receipt_handle) # 直接删除，放弃消息，不做善后处理

            message_body = msg.message_body
            if isinstance(message_body, str):
                event_data = json.loads(message_body)
            else:
                event_data = message_body
            
            logger.info(f"event_data: {event_data}")
            if not event_data:
                logger.error("event_data is None")
                continue
            
            oss_event = _extract_event_info(event_data)
            if not oss_event:
                logger.error("无法提取事件信息，跳过处理")
                continue
            process_oss_event(oss_event)
    except Exception as e:
        if not "MessageNotExist" in str(e):
            logger.error(f"处理 OSS 事件失败: {e}")
    
def _extract_event_info(event_data: Dict) -> Optional[OSSEvent]:
    """解析 OSS 事件数据"""
    try:
        # OSS 事件通知格式
        events = event_data.get("events", [])
        if not events:
            return None
        
        event = events[0]
        event_name = event.get("eventName", "")
        event_time = event.get("eventTime", "")
        
        # 获取对象信息
        oss_obj = event.get("oss", {}).get("object", {})
        bucket = event.get("oss", {}).get("bucket", {})
        

        if OSSEventType.OBJECT_CREATED.value in event_name:
            event_type = OSSEventType.OBJECT_CREATED
        elif OSSEventType.OBJECT_REMOVED.value in event_name:
            event_type = OSSEventType.OBJECT_REMOVED
        elif OSSEventType.OBJECT_UPDATED.value in event_name:
            event_type = OSSEventType.OBJECT_UPDATED
        else:
            event_type = OSSEventType.UNKNOWN
            
        return OSSEvent(
            event_type=event_type,
            event_time=event_time,
            bucket_name=bucket.get("name", ""),
            object_key=oss_obj.get("key", ""),
        )
    except Exception as e:
        logger.error(f"解析事件数据失败: {e}")
        return None



if __name__ == "__main__":
    _setup_signal_handlers()
    logger.info("开始监听MNS队列的事件...")

    while not shutdown_requested:
        try:
            oss_event_handler()
            if not shutdown_requested:
                time.sleep(1)
        except Exception as e:
            if not shutdown_requested:
                logger.error(f"处理 OSS 事件失败: {e}")
                time.sleep(1)

    logger.info("已退出")