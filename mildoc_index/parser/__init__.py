from .document_parser import DocumentParser
from .office_parser import OfficeParser
from .pdf_parser import PDFParser
from .markdown_parser import MarkdownParser
from .text_parser import TextParser

# 注意：MinerUParser 不在此处导出。
# mineru 依赖较重（会拉起 torch / vlm 相关模块），若在包初始化时导入，
# 会导致索引服务启动变慢，且一旦 mineru 环境异常会连带整个解析器链不可用。
# 因此改为按需导入：from parser.mineru_parser import MinerUParser
# 由 oss_object_parser 在确认配置了 MINERU_SERVER_URL 后再动态加载。

__all__ = ['DocumentParser', 'OfficeParser', 'PDFParser', 'MarkdownParser', 'TextParser']
