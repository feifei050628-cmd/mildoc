import alibabacloud_oss_v2 as oss
import os
from dotenv import load_dotenv
from loguru import logger
from doc_fragment import DocFragment
import hashlib, base64
from typing import Tuple, Optional, List
from parser import PDFParser, OfficeParser, MarkdownParser, TextParser
from langchain_text_splitters import RecursiveCharacterTextSplitter
from parser import DocumentParser

load_dotenv()

OSS_REGION = os.getenv('OSS_REGION')
OSS_ENDPOINT = os.getenv('OSS_ENDPOINT')
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 512))


_oss_client = None


# 全局解析器（按优先级排序）
_parsers = [
    PDFParser(),             # PyPDF2作为PDF解析器
    OfficeParser(),          # markitdown解析Office文档（Word、Excel、PowerPoint）
    MarkdownParser(),        # Markdown解析器，
    TextParser(),            # 纯文本解析器作为最后的备选
]


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

def _get_oss_object(bucket_name: str, object_name: str) -> Tuple[DocFragment, bytes]:
    client = _get_oss_client()
    request = oss.GetObjectRequest(bucket=bucket_name, key=object_name)

    response = client.get_object(request)

    doc_fragment = DocFragment(
        doc_name=os.path.basename(object_name),
        doc_path=object_name,
        doc_type=response.content_type,
        doc_md5=base64.b64decode(response.content_md5).hex(),
        doc_length=response.content_length,
        content=None
    )

    if doc_fragment.doc_length > MAX_FILE_SIZE * 1024 * 1024:
        logger.error(f"文件过大 ({doc_fragment.doc_length / 1024 / 1024:.2f} MB > 512 MB)，跳过解析")
        return None, None

    doc_data = response.body.read()

    return doc_fragment, doc_data

    
    
def _get_parser(content_type: str) -> Optional[DocumentParser]:
    """
    根据内容类型获取合适的解析器
    
    Args:
        content_type (str): 内容类型
        
    Returns:
        Optional[DocumentParser]: 解析器实例，如果没有找到则返回None
    """

    global _parsers
    
    for parser in _parsers:
        if parser.supports(content_type):
            return parser
    return None
    
    
def _split_text_by_langchain(text: str) -> List[str]:
    """
    使用LangChain分割文本
    """

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=2048, chunk_overlap=128)
    return text_splitter.split_text(text)

def object_parser(bucket_name: str, object_name: str) -> List[DocFragment]:
    """
    解析对象
    """
    logger.info(f"解析对象: {bucket_name}/{object_name}")
    
    doc_fragment, doc_data = _get_oss_object(bucket_name, object_name)
    if not doc_fragment or not doc_data:
        return None

    parser = _get_parser(doc_fragment.doc_type)
    if not parser:
        logger.error(f"未找到适合 {doc_fragment.doc_type} 的解析器，尝试使用文本解析器")
        parser = TextParser()
    text_content = parser.parse(doc_data)

    if not text_content:
        return []

    contents = _split_text_by_langchain(text_content)
    return [DocFragment(
        doc_name=doc_fragment.doc_name,
        doc_path=doc_fragment.doc_path,
        doc_type=doc_fragment.doc_type,
        doc_md5=doc_fragment.doc_md5,
        doc_length=doc_fragment.doc_length,
        content=content
    ) for content in contents]


if __name__ == "__main__":
    result = object_parser("mildoc-geekpost", "pdf2.pdf")
    for doc_fragment in result:
        print(doc_fragment.doc_name)
        print(doc_fragment.doc_path)
        print(doc_fragment.doc_type)
        print(doc_fragment.doc_md5)
        print(doc_fragment.doc_length)
        print(len(doc_fragment.content))
        print("-"*100)

