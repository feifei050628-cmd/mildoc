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


def _build_parsers() -> List[DocumentParser]:
    """
    按优先级构建解析器链。

    MinerU 依赖独立部署的 GPU 服务（MINERU_SERVER_URL），仅在该地址已配置时才注册，
    未配置时行为与原来完全一致。启用后作为 PDF 的首选解析器，
    服务不可用时会自动回退到 PyPDF2（见 _parse_with_fallback）。
    """
    parsers: List[DocumentParser] = [
        PDFParser(),             # PyPDF2作为PDF解析器
        OfficeParser(),          # markitdown解析Office文档（Word、Excel、PowerPoint）
        MarkdownParser(),        # Markdown解析器，
        TextParser(),            # 纯文本解析器作为最后的备选
    ]

    if os.getenv('MINERU_SERVER_URL'):
        try:
            # 按需导入，避免在未启用 MinerU 时加载其重型依赖
            from parser.mineru_parser import MinerUParser
            parsers.insert(0, MinerUParser())   # 高精度解析器优先
            logger.info("已启用 MinerU 解析器（PDF 优先使用）")
        except Exception as e:
            logger.warning(f"MinerU 解析器启用失败，继续使用内置解析器: {e}")

    return parsers


# 全局解析器（按优先级排序）
_parsers: List[DocumentParser] = _build_parsers()


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
        logger.error(f"文件过大 ({doc_fragment.doc_length / 1024 / 1024:.2f} MB > {MAX_FILE_SIZE} MB)，跳过解析")
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


def _parse_with_fallback(doc_data: bytes, content_type: str) -> str:
    """
    按优先级依次尝试解析器，直到取得非空文本。

    说明：高精度解析器（如 MinerU）依赖外部服务，服务不可用时会返回空串；
    原实现一旦首选解析器失败就直接放弃，现改为自动回退到下一个可用解析器，
    避免外部服务抖动导致整个文档索引失败。
    """
    candidates = [p for p in _parsers if p.supports(content_type)]
    if not candidates:
        logger.error(f"未找到适合 {content_type} 的解析器，尝试使用文本解析器")
        candidates = [TextParser()]

    for parser in candidates:
        try:
            text_content = parser.parse(doc_data)
        except Exception as e:
            logger.warning(f"{type(parser).__name__} 解析异常，尝试下一个: {e}")
            continue

        if text_content and text_content.strip():
            logger.info(f"使用 {type(parser).__name__} 解析成功，提取 {len(text_content)} 字符")
            return text_content

        logger.warning(f"{type(parser).__name__} 未提取到文本，尝试下一个解析器")

    logger.error(f"所有解析器均未能从 {content_type} 中提取文本")
    return ""


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

    text_content = _parse_with_fallback(doc_data, doc_fragment.doc_type)

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
