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

# 单条消息的最大处理重试次数。
# 处理失败时不删除消息，依赖 MNS 的 visibility timeout 自动重投（at-least-once）；
# 超过该次数才丢弃，避免毒丸消息无限循环占用消费者。
MAX_PROCESS_RETRY = int(os.getenv("MNS_MAX_PROCESS_RETRY", "3"))

_mildoc_mns_queue = None
# message_id -> 已重试次数
_retry_counters: Dict[str, int] = {}


def _get_mildoc_mns_queue():
    global _mildoc_mns_queue
    if _mildoc_mns_queue is None:
        mns_account = Account(MNS_ENDPOINT, MNS_ACCESS_KEY_ID, MNS_ACCESS_KEY_SECRET)
        _mildoc_mns_queue = mns_account.get_queue(MNS_QUEUE_NAME)
    return _mildoc_mns_queue


def oss_event_handler() -> None:
    """
    监听 MNS 队列，接收 OSS 事件通知。

    消息可靠性策略（修复「先删除后处理」导致的消息丢失）：
    - 处理成功  -> 删除消息（ack）
    - 处理失败  -> 不删除，等待 visibility timeout 后由 MNS 自动重投
    - 重试超限  -> 删除并记录错误日志，避免毒丸消息无限循环
    """

    try:
        mildoc_mns_queue = _get_mildoc_mns_queue()

        while True:
            msg = mildoc_mns_queue.receive_message_with_str_body(wait_seconds=10)

            message_id = getattr(msg, "message_id", "") or ""
            receipt_handle = msg.receipt_handle

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
                # 事件格式本身无法解析，重试也没有意义，直接确认并跳过
                logger.error("无法提取事件信息，跳过处理")
                mildoc_mns_queue.delete_message(receipt_handle)
                continue

            success = process_oss_event(oss_event)

            if success:
                mildoc_mns_queue.delete_message(receipt_handle)
                _retry_counters.pop(message_id, None)
                logger.info(f"事件处理成功，已确认消息: {message_id}")
                continue

            # 处理失败：保留消息等待重投
            retry_count = _retry_counters.get(message_id, 0) + 1
            _retry_counters[message_id] = retry_count

            if retry_count >= MAX_PROCESS_RETRY:
                logger.error(
                    f"事件处理失败，已重试 {retry_count} 次达到上限，放弃该消息"
                    f"（生产环境建议接入死信队列）: {message_id}, "
                    f"对象: {oss_event.bucket_name}/{oss_event.object_key}"
                )
                mildoc_mns_queue.delete_message(receipt_handle)
                _retry_counters.pop(message_id, None)
            else:
                logger.warning(
                    f"事件处理失败，保留消息等待重投（第 {retry_count}/{MAX_PROCESS_RETRY} 次）: "
                    f"{message_id}, 对象: {oss_event.bucket_name}/{oss_event.object_key}"
                )
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
