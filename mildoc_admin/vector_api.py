import dashvector
from typing import List
import os
from loguru import logger
from dotenv import load_dotenv
from dataclasses import dataclass
load_dotenv()


## 配置DashVector
DASHVECTOR_API_KEY = os.getenv('DASHVECTOR_API_KEY')
DASHVECTOR_ENDPOINT = os.getenv('DASHVECTOR_ENDPOINT')
DASHVECTOR_COLLECTION = os.getenv('DASHVECTOR_COLLECTION')

# DashVector 单次 query 的 topk 上限为 1024
MAX_QUERY_TOPK = 1024


_dashvector_collection = None


def _get_dashvector_collection():
    global _dashvector_collection
    if _dashvector_collection is None:
        _dashvector_collection = dashvector.Client(
            api_key=DASHVECTOR_API_KEY,
            endpoint=DASHVECTOR_ENDPOINT
        ).get(name=DASHVECTOR_COLLECTION)
    return _dashvector_collection


def get_doc_fragments(doc_path: str) -> List[str]:
    """
    查询指定doc_path的所有文档片段（用于管理后台展示）

    说明：原实现 topk 写死 100，分片数超过 100 的文档在后台只能看到前 100 片。
    现已提升至 DashVector 的单次上限 1024；由于查询接口不提供分页游标，
    超过 1024 片的文档展示仍受此限制（删除场景不受影响，见 dash_vector_api）。

    Args:
        doc_path: 文档路径

    Returns:
        List[str]: 匹配的文档片段内容列表
    """
    try:
        # 构建过滤条件，使用单引号包裹字符串值
        filter_expr = f"doc_path = '{doc_path}'"

        ret = _get_dashvector_collection().query(
            topk=MAX_QUERY_TOPK,
            filter=filter_expr,
            output_fields=['content'],
            include_vector=False
        )

        if not ret:
            logger.error(f"查询文档失败: {ret.message}")
            return []

        doc_fragments = []
        if ret.output:
            for doc in ret.output:
                doc_fragments.append(doc.fields['content'])

        logger.info(f"查询到 {len(doc_fragments)} 个匹配 doc_path='{doc_path}' 的文档片段")
        return doc_fragments

    except Exception as e:
        logger.error(f"查询文档失败: {e}")
        raise e


def check_doc_fragment_exists(doc_path: str) -> bool:
    """
    检查指定doc_path的文档是否存在

    Args:
        doc_path: 文档路径

    Returns:
        bool: 是否存在
    """
    doc_fragments = get_doc_fragments(doc_path)
    return len(doc_fragments) > 0



if __name__ == "__main__":
    print(check_doc_fragment_exists(doc_path="pdf2.pdf"))
    print(get_doc_fragments(doc_path="pdf2.pdf"))
