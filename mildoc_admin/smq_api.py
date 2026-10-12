import json
import os
from dotenv import load_dotenv
from mns.account import Account
from mns.queue import Message
from loguru import logger
from datetime import datetime
load_dotenv()


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



def send_oss_update_event(bucket_name: str, object_key: str) -> bool:
    logger.info(f"发送 OSS 更新事件: {bucket_name}/{object_key}")
    try:
        event_data = {
            "events": [
                {
                    "eventName": "ObjectUpdated",
                    "eventTime": datetime.now().isoformat(),
                    "oss": {
                        "bucket": {"name": bucket_name},
                        "object": {"key": object_key}
                    }
                }
            ]
        }
        message_body = json.dumps(event_data)
        message = Message(message_body)
        mildoc_mns_queue = _get_mildoc_mns_queue()
        mildoc_mns_queue.send_message(message)
        return True
    except Exception as e:
        logger.error(f"发送 OSS 事件失败: {e}")
        return False

if __name__ == "__main__":
    q = _get_mildoc_mns_queue()
    print("send msg")
    q.send_message(Message("hello"))
    print("send msg done!")

    print("receive msg")
    msg = q.receive_message_with_str_body()
    print(msg.message_body)

    print("delete msg")
    q.delete_message(msg.receipt_handle)
    print("delete msg done!")