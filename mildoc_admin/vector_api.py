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
    查询指定doc_path的所有文档片段
    
    Args:
        doc_path: 文档路径
        
    Returns:
        List[str]: 匹配的文档片段ID列表
    """
    try:
        # 构建过滤条件，使用单引号包裹字符串值
        filter_expr = f"doc_path = '{doc_path}'"
        
        # 查询所有匹配的文档，只返回id字段
        ret = _get_dashvector_collection().query(
            topk=100,  # 设置一个较大的值以确保获取所有匹配的文档
            filter=filter_expr,
            output_fields=['content'],  
            include_vector=False  # 不需要向量数据
        )
        
        if not ret:
            logger.error(f"查询文档失败: {ret.message}")
            return []
        
        # 提取所有文档ID
        # ret.output 是 List[Doc] 类型，Doc对象有 id 属性
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
