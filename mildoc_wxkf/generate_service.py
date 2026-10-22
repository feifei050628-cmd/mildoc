
from loguru import logger
from dash_vector import DashVector
from openai import OpenAI
import os
from prompt import PROMPT_TEMPLATE
from dotenv import load_dotenv

load_dotenv()



DASHSCOPE_BASE_URL = os.getenv('DASHSCOPE_BASE_URL')
DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY')
DASHSCOPE_LLM_MODEL = os.getenv('DASHSCOPE_LLM_MODEL')

class GenerateService:


    def __init__(self):
        """初始化RAG服务"""
        self.dashvector = DashVector()
        self.dashllm = OpenAI(
            api_key=DASHSCOPE_API_KEY,
            base_url=DASHSCOPE_BASE_URL
        )


    def generate_response(self, query: str, history: list = None) -> str:
        """
        生成回答

        Args:
            query: 用户问题
            history: 历史对话行（形如 ["客户: xxx", "AI: yyy"]），用于多轮上下文
        """
        try:
            documents = self.dashvector.query_doc_fragment(query, top_n=10, rerank=True, rerank_top_n=3)
            logger.info(f"初始检索到 {len(documents)} 个候选文档")
            document_context = "\n\n".join(documents)

            if not history:
                history = []
            logger.info(f"注入历史对话 {len(history)} 条")
            # 将历史对话转换为上下文格式
            history_context = "\n\n".join(history)

            # 使用统一的提示模板生成回答
            prompt = PROMPT_TEMPLATE.format(context=document_context, history=history_context, question=query)

            answer = self.dashllm.responses.create(
                model=DASHSCOPE_LLM_MODEL,
                input=prompt,
                extra_body={"enable_thinking": False}
            )

            return answer.output_text

        except Exception as e:
            logger.error(f"生成回答失败: {e}")
            return "抱歉，我暂时无法理解您的问题，请稍后再试或联系人工客服。"


_generate_service = None

def get_generate_service() -> GenerateService:
    global _generate_service
    if _generate_service is None:
        _generate_service = GenerateService()
    return _generate_service


if __name__ == "__main__":
    rag_service = get_generate_service()
    result = rag_service.generate_response("老人与海是一个什么故事？")
    logger.info(result)
