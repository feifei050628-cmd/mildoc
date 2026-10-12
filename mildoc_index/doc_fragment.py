from dataclasses import dataclass

@dataclass
class DocFragment:
    doc_name: str # 文档名称
    doc_path: str # 文档路径（含名字）
    doc_type: str # 文档类型
    doc_md5: str # 文档 MD5
    doc_length: int # 文档字节数
    content: str # 文档分段内容