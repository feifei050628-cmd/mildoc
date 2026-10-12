import dashvector
from dashvector import Doc
from dataclasses import asdict
from typing import List
import os
from dashscope import TextEmbedding
from loguru import logger
from dotenv import load_dotenv
from doc_fragment import DocFragment

load_dotenv()

## 配置DashScope通用文本向量模型
DASHVECTOR_DIM = int(os.getenv('DASHVECTOR_DIM'))
DASHVECTOR_DTYPE = os.getenv('DASHVECTOR_DTYPE')
DASHSCOPE_EMBEDDING_MODEL = os.getenv('DASHSCOPE_EMBEDDING_MODEL')
DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY')


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

# 调用DashScope通用文本向量模型，将文本embedding为向量
def _get_embedding(text: str):
    if not text:
        return None
    try:
        rsp = TextEmbedding.call(
            model=DASHSCOPE_EMBEDDING_MODEL,
            input=text,
            dimension=DASHVECTOR_DIM,
            encoding_format=DASHVECTOR_DTYPE,
            api_key=DASHSCOPE_API_KEY
        )

        if rsp.status_code != 200:
            logger.error(f"获取文本向量失败: {rsp.message}")
            return None
        return rsp.output['embeddings'][0]['embedding']
    except Exception as e:
        logger.error(f"获取文本向量失败: {e}")
        return None

def _get_doc_fragment_ids(doc_path: str) -> List[str]:
    """
    查询指定doc_path的所有文档ID，用于后续删除操作
    
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
            output_fields=['id'],  # 只返回id字段
            include_vector=False  # 不需要向量数据
        )
        
        if not ret:
            logger.error(f"查询文档失败: {ret.message}")
            return []
        
        # 提取所有文档ID
        # ret.output 是 List[Doc] 类型，Doc对象有 id 属性
        doc_ids = []
        if ret.output:
            for doc in ret.output:
                doc_ids.append(doc.id)
        
        logger.info(f"查询到 {len(doc_ids)} 个匹配 doc_path='{doc_path}' 的文档片段")
        return doc_ids
        
    except Exception as e:
        logger.error(f"查询文档失败: {e}")
        raise e

def insert_doc_fragment(doc_fragment: DocFragment) -> bool:
    """
    插入文档到DashVector集合
    
    Args:
        doc_fragment: DocFragment对象
        
    Returns:
        bool: 插入操作是否成功
    """
    try:

        # 构建fields字典（包含所有文档字段）
        fields = asdict(doc_fragment)
        
        content_vector = _get_embedding(doc_fragment.content)
        if not content_vector:
            logger.error(f"获取文本向量失败")
            return False

        # 使用Doc对象插入数据
        _get_dashvector_collection().insert(
            Doc(
                vector=content_vector,
                fields=fields
            )
        )
        
        
        return True
        
    except Exception as e:
        logger.error(f"插入文档失败: {e}")
        return False


def check_doc_fragment_exists(doc_path: str) -> bool:
    """
    检查指定doc_path的文档是否存在
    
    Args:
        doc_path: 文档路径
        
    Returns:
        bool: 是否存在
    """
    doc_fragment_ids = _get_doc_fragment_ids(doc_path)
    return len(doc_fragment_ids) > 0

def delete_doc_fragments(doc_path: str) -> bool:
    """
    批量删除指定ID列表的文档
    
    Args:
        doc_path: 文档路径
        
    Returns:
        bool: 删除操作是否成功
    """
    try:
        doc_fragment_ids = _get_doc_fragment_ids(doc_path)
        if not doc_fragment_ids:
            logger.warning(f"文档路径 '{doc_path}' 不存在，跳过删除操作")
            return True

        resp = _get_dashvector_collection().delete(ids=doc_fragment_ids)

        if not resp:
            logger.error(f"删除文档失败: {resp.message}")
            return False
            
        return True
    except Exception as e:
        logger.error(f"批量删除失败: {e}")
        return False


if __name__ == "__main__":
    doc_fragment1 = DocFragment(doc_name="test1", doc_path="test1", doc_type="test1", doc_md5="test1", doc_length=50, content="test1")
    doc_fragment2 = DocFragment(doc_name="test2", doc_path="test2", doc_type="test2", doc_md5="test2", doc_length=100, content="test2")
    print(insert_doc_fragment(doc_fragment1))
    print(insert_doc_fragment(doc_fragment2))
    print(delete_doc_fragments(doc_path="test1"))
    print(delete_doc_fragments(doc_path="test2"))
