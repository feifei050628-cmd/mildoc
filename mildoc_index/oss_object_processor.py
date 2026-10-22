from dash_vector_api import delete_doc_fragments, insert_doc_fragment
from oss_object_parser import object_parser
from enum import Enum
from dataclasses import dataclass
from loguru import logger


class OSSEventType(Enum):
    """OSS 事件类型"""
    OBJECT_CREATED = "ObjectCreated"  # 对象创建（上传）
    OBJECT_REMOVED = "ObjectRemoved"  # 对象删除
    OBJECT_UPDATED = "ObjectUpdated"  # 对象更新
    UNKNOWN = "Unknown"  # 未知事件类型
@dataclass
class OSSEvent:
    """OSS 事件数据结构"""
    event_type: OSSEventType  # 事件类型
    event_time: str  # 事件时间
    bucket_name: str  # Bucket 名称
    object_key: str  # 对象键（路径）


def process_oss_event(oss_event: OSSEvent) -> bool:
        """
        处理单个事件

        Args:
            oss_event (OSSEvent): 事件信息

        Returns:
            bool: 处理是否成功。返回 False 时，调用方应保留消息以触发重投。
        """
        try:
            # 提取事件信息
            event_type = oss_event.event_type
            timestamp = oss_event.event_time

            logger.info(f"[{timestamp}] 收到事件: {event_type}")
            logger.info(f"对象: {oss_event.bucket_name}/{oss_event.object_key}")

            # 根据事件类型进行处理
            if event_type == OSSEventType.OBJECT_CREATED:
                return _handle_object_created(oss_event)
            elif event_type == OSSEventType.OBJECT_REMOVED:
                return _handle_object_deleted(oss_event)
            elif event_type == OSSEventType.OBJECT_UPDATED:
                return _handle_object_updated(oss_event)
            else:
                logger.error(f"未处理的事件类型: {event_type}")
                # 不支持的事件类型重试也不会成功，视为已处理
                return True

        except Exception as e:
            logger.error(f"处理事件时出错: {e}")
            return False

def _handle_object_updated(oss_event: OSSEvent) -> bool:
    """
    处理对象更新事件

    Args:
        oss_event (OSSEvent): 事件信息
    """
    try:
        return _handle_object_created(oss_event)
    except Exception as e:
        logger.error(f"处理对象更新事件失败: {e}")
        return False

def _handle_object_created(oss_event: OSSEvent) -> bool:
    """
    处理对象创建事件

    Args:
        oss_event (OSSEvent): 事件信息
    """
    try:
        bucket_name = oss_event.bucket_name
        object_name = oss_event.object_key

        logger.info(f"处理新增对象: {bucket_name}/{object_name}")

        # 解析对象内容
        doc_fragments = object_parser(bucket_name, object_name)

        if not doc_fragments:
            # 文档本身无文本内容，属于数据问题而非处理失败，不触发重投
            logger.error(f"    未提取到文本内容，跳过")
            return True

        delete_doc_fragments(object_name)

        failed = 0
        for doc_fragment in doc_fragments:
            if not insert_doc_fragment(doc_fragment):
                failed += 1

        if failed:
            logger.error(f"写入向量失败 {failed}/{len(doc_fragments)} 个分片，等待重投")
            return False

        logger.info(f"索引完成，共写入 {len(doc_fragments)} 个分片")
        return True

    except Exception as e:
        logger.error(f"处理对象创建事件失败: {e}")
        return False

def _handle_object_deleted(oss_event: OSSEvent) -> bool:
    """
    处理对象删除事件

    Args:
        oss_event (OSSEvent): 事件信息
    """
    try:
        bucket_name = oss_event.bucket_name
        object_name = oss_event.object_key

        logger.info(f"处理删除对象: {bucket_name}/{object_name}")

        # 从DashVector中删除相关记录
        logger.info("从DashVector中查找并删除相关记录...")

        # 使用DashVectorAPI的删除方法
        if delete_doc_fragments(object_name):
            logger.info(f"成功删除文档片段: {object_name}")
            return True
        else:
            logger.error(f"删除文档片段失败: {object_name}")
            return False

    except Exception as e:
        logger.error(f"处理对象删除事件失败: {e}")
        return False


if __name__ == "__main__":
    #process_oss_event(OSSEvent(event_type=OSSEventType.OBJECT_CREATED, event_time="2026-03-04 10:00:00", bucket_name="mildoc-geekpost", object_key="pdf2.pdf"))
    #process_oss_event(OSSEvent(event_type=OSSEventType.OBJECT_REMOVED, event_time="2026-03-04 10:00:00", bucket_name="mildoc-geekpost", object_key="pdf2.pdf"))
    process_oss_event(OSSEvent(event_type=OSSEventType.OBJECT_UPDATED, event_time="2026-03-04 10:00:00", bucket_name="mildoc-geekpost", object_key="pdf2.pdf"))
    #process_oss_event(OSSEvent(event_type=OSSEventType.UNKNOWN, event_time="2026-03-04 10:00:00", bucket_name="mildoc-geekpost", object_key="pdf2.pdf"))
