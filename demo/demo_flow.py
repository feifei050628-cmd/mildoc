# -*- coding: utf-8 -*-
"""
MilDoc 端到端演示脚本

用途：在已部署的 MilDoc 环境上跑一遍完整链路，产出可用于 README / 简历 / 演示录屏的真实输出。

两种模式：
  1) 默认（只读）：查看向量库统计 + 执行一次真实问答，不改动任何数据
  2) --upload：额外上传一份测试文档到 OSS，演示「上传 → 事件 → 索引」链路，结束后自动清理

用法：
    cd mildoc_wxkf
    uv run demo_flow.py                       # 只读演示
    uv run demo_flow.py --upload              # 含上传的完整链路演示
    uv run demo_flow.py --query "你的问题"     # 指定问题

注意：本脚本不打印任何密钥；涉及敏感配置的字段只输出是否设置。
"""

import os
import sys
import time

# 自动定位项目根（含 pyproject.toml 的目录），使脚本放在任意位置都能运行
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = _HERE
while _ROOT != os.sep and not os.path.exists(os.path.join(_ROOT, "pyproject.toml")):
    _ROOT = os.path.dirname(_ROOT)
for _p in (_ROOT, os.path.join(_ROOT, "mildoc_wxkf"),
           os.path.join(_ROOT, "mildoc_index"), os.path.join(_ROOT, "mildoc_admin")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dotenv import load_dotenv

load_dotenv(os.path.join(_ROOT, ".env"))

import dashvector
from loguru import logger

# 关闭脚本内日志，改用自定义输出，保证演示输出干净
logger.remove()


def line(title: str = "", char: str = "─", width: int = 68):
    if title:
        print(f"\n{char * 6} {title} {char * max(0, width - len(title) - 8)}")
    else:
        print(char * width)


def collection():
    return dashvector.Client(
        api_key=os.getenv("DASHVECTOR_API_KEY"),
        endpoint=os.getenv("DASHVECTOR_ENDPOINT"),
    ).get(name=os.getenv("DASHVECTOR_COLLECTION"))


def step1_overview():
    """1. 展示知识库当前状态"""
    line("STEP 1  知识库状态")
    c = collection()
    stats = c.stats().output
    total = getattr(stats, "total_doc_count", None) or (
        stats.get("total_doc_count") if isinstance(stats, dict) else "N/A")
    compl = getattr(stats, "index_completeness", None) or (
        stats.get("index_completeness") if isinstance(stats, dict) else "N/A")
    print(f"  向量集合      : {os.getenv('DASHVECTOR_COLLECTION')}")
    print(f"  已索引分片数  : {total}")
    print(f"  索引完整度    : {compl}")
    print(f"  向量维度      : {os.getenv('DASHVECTOR_DIM')} 维"
          f" / 度量 {os.getenv('DASHVECTOR_METRIC')}"
          f" / 类型 {os.getenv('DASHVECTOR_DTYPE')}")

    # 列出已索引的文档（按 doc_path 去重）
    r = c.query(topk=100, output_fields=["doc_path", "doc_name", "doc_type"],
                include_vector=False)
    docs = {}
    for d in (r.output or []):
        f = d.fields
        docs.setdefault(f.get("doc_path"), f.get("doc_type"))
    if docs:
        print("  已索引文档    :")
        for p, t in list(docs.items())[:10]:
            print(f"      - {p}  ({t})")
    return c


def step2_ingest_demo():
    """2. 演示「上传 → OSS 事件 → 自动索引」链路"""
    line("STEP 2  文档入库链路（事件驱动）")
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "mildoc_admin"))
    from smq_api import send_oss_update_event  # noqa: E402

    bucket = os.getenv("OSS_BUCKET")
    object_key = f"_demo_/mildoc-demo-doc-{int(time.time())}.md"
    content = (
        "# MilDoc 演示文档\n\n"
        "MilDoc 的文档索引服务通过监听 OSS 对象事件自动完成入库。\n\n"
        "## 索引流程\n\n"
        "文档上传到 OSS 后触发 ObjectCreated 事件，事件推送到消息队列，"
        "索引服务消费消息后完成解析、分片与向量化。\n\n"
        "## 一致性策略\n\n"
        "文档更新时，先按 doc_path 清理旧向量再写入新向量，保证重复上传不产生重复索引。\n"
    ).encode("utf-8")

    print(f"  [1/4] 上传测试文档到 OSS: {bucket}/{object_key}")
    try:
        import alibabacloud_oss_v2 as oss
        cfg = oss.config.load_default()
        cfg.credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()
        cfg.region = os.getenv("OSS_REGION")
        cfg.endpoint = os.getenv("OSS_ENDPOINT")
        client = oss.Client(config=cfg)
        client.put_object(oss.PutObjectRequest(bucket=bucket, key=object_key, body=content))
        print(f"        上传成功，大小 {len(content)} 字节")
    except Exception as e:
        print(f"        上传失败（跳过后续）: {e}")
        return None

    print("  [2/4] 补发 ObjectUpdated 事件到消息队列")
    send_oss_update_event(bucket, object_key)
    print("        事件已发送，等待索引服务消费...")

    def _count():
        s = collection().stats().output
        return getattr(s, "total_doc_count", 0)

    before = _count()
    print(f"  [3/4] 轮询向量库，当前分片数 {before}")
    for i in range(30):
        time.sleep(2)
        now = _count()
        if now > before:
            print(f"        索引完成，分片数 {before} → {now}（耗时约 {(i + 1) * 2} 秒）")
            break
    else:
        print("        等待超时，请检查索引服务是否在运行")

    print("  [4/4] 清理测试文档")
    try:
        import alibabacloud_oss_v2 as oss
        cfg = oss.config.load_default()
        cfg.credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()
        cfg.region = os.getenv("OSS_REGION")
        cfg.endpoint = os.getenv("OSS_ENDPOINT")
        oss.Client(config=cfg).delete_object(
            oss.DeleteObjectRequest(bucket=bucket, key=object_key))
        print("        已删除测试文档及其向量")
    except Exception as e:
        print(f"        清理失败（请手动删除 {object_key}）: {e}")
    return object_key


def step3_qa_demo(question: str):
    """3. 演示检索 - 重排 - 生成链路"""
    line("STEP 3  智能问答链路（召回 → 精排 → 生成）")
    from dash_vector import DashVector
    from generate_service import get_generate_service

    dv = DashVector()

    print(f"  用户提问      : {question}")

    t0 = time.time()
    vector_hits = dv.query_doc_fragment(question, top_n=10, rerank=False)
    t1 = time.time()
    print(f"  [1/3] 向量召回  : Top-10，命中 {len(vector_hits)} 个片段"
          f"（{(t1 - t0) * 1000:.0f} ms）")

    reranked = dv.query_doc_fragment(question, top_n=10, rerank=True, rerank_top_n=3)
    t2 = time.time()
    print(f"  [2/3] Rerank 精排: Top-10 → Top-3（{(t2 - t1) * 1000:.0f} ms）")
    for i, ctx in enumerate(reranked, 1):
        preview = ctx.replace("\n", " ")[:60]
        print(f"         [{i}] {preview}...")

    answer = get_generate_service().generate_response(question)
    t3 = time.time()
    print(f"  [3/3] LLM 生成   : （{(t3 - t2) * 1000:.0f} ms）")
    print(f"\n  端到端总耗时  : {(t3 - t0):.2f} 秒")
    line("AI 回答")
    print(answer)
    return answer


def step4_runtime():
    """4. 展示运行时状态"""
    line("STEP 4  运行时配置")
    keys = ["OSS_BUCKET", "MNS_QUEUE_NAME", "DASHVECTOR_COLLECTION",
            "DASHSCOPE_EMBEDDING_MODEL", "DASHSCOPE_RERANK_MODEL", "DASHSCOPE_LLM_MODEL"]
    for k in keys:
        v = os.getenv(k)
        print(f"  {k:<28}: {'已配置' if v else '未配置'}")


def main():
    print("\n" + "=" * 68)
    print("  MilDoc 企业级 RAG 知识库 · 端到端演示")
    print("=" * 68)

    step1_overview()

    if "--upload" in sys.argv:
        step2_ingest_demo()

    q = "西游记的作者是谁？"
    for i, a in enumerate(sys.argv):
        if a == "--query" and i + 1 < len(sys.argv):
            q = sys.argv[i + 1]

    step3_qa_demo(q)
    step4_runtime()

    print("\n" + "=" * 68)
    print("  演示结束")
    print("=" * 68 + "\n")


if __name__ == "__main__":
    main()
