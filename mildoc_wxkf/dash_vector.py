import dashvector
from typing import List
import os
from loguru import logger
from dotenv import load_dotenv
from dashscope import TextEmbedding, TextReRank

load_dotenv()

DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY')
DASHVECTOR_DIM = int(os.getenv('DASHVECTOR_DIM'))
DASHVECTOR_DTYPE = os.getenv('DASHVECTOR_DTYPE')
DASHSCOPE_EMBEDDING_MODEL = os.getenv('DASHSCOPE_EMBEDDING_MODEL')
DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY')
DASHSCOPE_RERANK_MODEL = os.getenv('DASHSCOPE_RERANK_MODEL')
DASHVECTOR_API_KEY = os.getenv('DASHVECTOR_API_KEY')
DASHVECTOR_ENDPOINT = os.getenv('DASHVECTOR_ENDPOINT')
DASHVECTOR_COLLECTION = os.getenv('DASHVECTOR_COLLECTION')



class DashVector:

    def __init__(self):

        self.client = dashvector.Client(
            api_key=DASHVECTOR_API_KEY,
            endpoint=DASHVECTOR_ENDPOINT
        )

        self._collection = self.client.get(name=DASHVECTOR_COLLECTION)

    # 调用DashScope通用文本向量模型，将文本embedding为向量
    def embedding(self, text: str):
        logger.info(f"get embedding: {text}")
        rsp = TextEmbedding.call(
            model=DASHSCOPE_EMBEDDING_MODEL,
            input=text,
            dimension=DASHVECTOR_DIM,
            encoding_format=DASHVECTOR_DTYPE,
            api_key=DASHSCOPE_API_KEY
        )
        return rsp.output['embeddings'][0]['embedding']

    def rerank(self, query: str, documents: List[str], rerank_top_n: int = 10) -> List[str]:
        logger.info(f"get rerank: {query}, {len(documents)} documents, rerank_top_n: {rerank_top_n}")
        rsp = TextReRank.call(
            model=DASHSCOPE_RERANK_MODEL,
            query=query,
            documents=documents,
            top_n=rerank_top_n,
            return_documents=True,
            api_key=DASHSCOPE_API_KEY
        )
        return [doc['document']['text'] for doc in rsp.output['results']]


    def query_doc_fragment(self, query: str, top_n: int = 10, rerank: bool = False, rerank_top_n: int = 10) -> List[str]:
        """
        查询文档片段
        
        Args:
            query: 查询语句
            
        Returns:
            List[Dict[str, Any]]: 查询结果
        """

        content_vector = self.embedding(query)
        match_result = self._collection.query(
            vector=content_vector,
            topk=top_n,
            output_fields=['content'], 
            include_vector=True
        )

        match_doc_fragments = [doc.fields['content'] for doc in match_result.output]

        if not match_doc_fragments:
            return []

        ## 如果不需要重排序，直接返回匹配的文档片段
        if not rerank:
            return match_doc_fragments

        ## 如果需要重排序，调用重排序接口
        return self.rerank(query, match_doc_fragments, rerank_top_n)


if __name__ == "__main__":
    dashvector = DashVector()
    result = dashvector.query_doc_fragment('老人与海是一个什么故事？', top_n=10, rerank=True)
    for res in result:
        logger.info(res[:100])
