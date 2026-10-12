import alibabacloud_oss_v2 as oss
import os
from dotenv import load_dotenv
from loguru import logger
import base64
from typing import List, Tuple
from dataclasses import dataclass
from io import BytesIO
import pytz
from datetime import timezone, datetime

load_dotenv()


OSS_REGION = os.getenv('OSS_REGION')
OSS_ENDPOINT = os.getenv('OSS_ENDPOINT')
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 512))


_oss_client = None


@dataclass
class DocInfo:
    doc_name: str # 文档名称
    doc_path: str # 文档路径（含名字）
    doc_type: str # 文档类型
    doc_md5: str # 文档 MD5
    doc_length: int # 文档字节数
    last_modified: datetime # 最后修改时间

@dataclass
class SubDocInfo: # 目录列表中的文档信息
    doc_name: str # 文档名称
    doc_path: str # 文档路径（含名字）
    doc_length: int # 文档字节数
    last_modified: datetime # 最后修改时间
    is_dir: bool # 是否是目录

def _get_oss_client():
    global _oss_client
    if _oss_client is None:
        logger.info(f"初始化OSS客户端: {OSS_REGION}, {OSS_ENDPOINT}")

        cfg = oss.config.load_default()
        cfg.credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()
        cfg.region = OSS_REGION
        cfg.endpoint = OSS_ENDPOINT
        _oss_client = oss.Client(config=cfg)
    return _oss_client

def convert_gmt_to_local(gmt_datetime: datetime, timezone_name='Asia/Shanghai'):
    """
    将GMT时间转换为本地时间
    
    Args:
        gmt_datetime: GMT时间对象（datetime）
        timezone_name: 目标时区名称，默认为'Asia/Shanghai'（中国标准时间）
    """
    return gmt_datetime.astimezone(pytz.timezone(timezone_name))

def get_oss_object_info(bucket_name: str, object_name: str) -> DocInfo:
    client = _get_oss_client()
    request = oss.HeadObjectRequest(bucket=bucket_name, key=object_name)

    head_result = client.head_object(request)

    if head_result.status_code != 200:
        logger.error(f"获取对象元信息失败，状态码: {head_result.status_code}")
        return None

    doc_info = DocInfo(
        doc_name=os.path.basename(object_name),
        doc_path=object_name,
        doc_type=head_result.content_type,
        doc_md5=base64.b64decode(head_result.content_md5).hex(),
        doc_length=head_result.content_length,
        last_modified=convert_gmt_to_local(head_result.last_modified)
    )

    return doc_info

def list_oss_object_info_by_dir(bucket_name: str, dir_path: str = '') -> List[SubDocInfo]:
    client = _get_oss_client()

    if dir_path and not dir_path.endswith('/'):
        dir_path += '/'

    paginator = client.list_objects_v2_paginator(bucket=bucket_name, prefix=dir_path)
    list_objects_request = oss.ListObjectsV2Request(bucket=bucket_name, prefix=dir_path, delimiter='/', max_keys=1000)

    sub_docs = []
    for page in paginator.iter_page(list_objects_request):
        if page.contents:
            for obj in page.contents:
                if obj.key.endswith('/'):
                    continue
                sub_docs.append(SubDocInfo(
                    doc_name=os.path.basename(obj.key),
                    doc_path=obj.key,
                    doc_length=obj.size,
                    last_modified=convert_gmt_to_local(obj.last_modified),
                    is_dir=False))

        if page.common_prefixes:
            for prefix in page.common_prefixes:
                sub_docs.append(SubDocInfo(
                    doc_name=os.path.basename(prefix.prefix.rstrip('/')),
                    doc_path=prefix.prefix,
                    doc_length=0,
                    last_modified=None,
                    is_dir=True))
    return sub_docs


def delete_oss_object(bucket_name: str, object_name: str) -> bool:
    client = _get_oss_client()
    request = oss.DeleteObjectRequest(bucket=bucket_name, key=object_name)

    response = client.delete_object(request)

    logger.info(f"删除对象: {object_name}, 状态码: {response.status_code}")

    return response.status_code == 204
def is_oss_object_exist(bucket_name: str, object_name: str) -> bool:
    client = _get_oss_client()
    return client.is_object_exist(bucket=bucket_name, key=object_name)


def upload_oss_object_from_bytes(bucket_name: str, object_name: str, bytes_io: BytesIO) -> bool:
    client = _get_oss_client()
    request = oss.PutObjectRequest(bucket=bucket_name, key=object_name, body=bytes_io)

    response = client.put_object(request)

    logger.info(f"上传对象: {object_name}, 状态码: {response.status_code}")

    return response.status_code == 200


def download_oss_object(bucket_name: str, object_name: str) -> Tuple[bytes, str, str, int]:
    """
    下载对象
    
    Args:
        bucket_name: 桶名称
        object_name: 对象名称
    
    Returns:
        Tuple[bytes, str, str, int]: 文件数据, 文件类型, 文件名称, 文件长度
    """
    client = _get_oss_client()
    request = oss.GetObjectRequest(bucket=bucket_name, key=object_name)

    response = client.get_object(request)

    if response.status_code != 200:
        logger.error(f"下载对象失败，状态码: {response.status_code}")
        return None, None, None, None

    file_type = response.content_type
    file_length = response.content_length

    with response.body as body:
        file_data = body.read()

    file_name = os.path.basename(object_name)
    
    return file_data, file_type, file_name, file_length


if __name__ == "__main__":
    oss_file_path = 'test/tmp/text.txt'
    OSS_BUCKET = os.getenv('OSS_BUCKET')
    sub_docs = list_oss_object_info_by_dir(OSS_BUCKET, '')
    for sub_doc in sub_docs:
        print(sub_doc)

    print(upload_oss_object_from_bytes(OSS_BUCKET, oss_file_path , BytesIO("你好，world！".encode("utf-8"))))

    print(is_oss_object_exist(OSS_BUCKET, oss_file_path))
    print(get_oss_object_info(OSS_BUCKET, oss_file_path))
    data, type, name, length = download_oss_object(OSS_BUCKET, oss_file_path)
    print(type, name, length)
    print(str(data, encoding="utf-8"))
    print(delete_oss_object(OSS_BUCKET, oss_file_path))
