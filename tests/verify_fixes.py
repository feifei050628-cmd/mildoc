# -*- coding: utf-8 -*-
"""修复验证脚本（只读 + 自造数据自清理，不影响真实业务数据）"""
import os
import sys
import json

_HERE = os.path.dirname(os.path.abspath(__file__))          # mildoc_index
_ROOT = os.path.dirname(_HERE)                               # 项目根
for _p in (_HERE, os.path.join(_ROOT, "mildoc_wxkf"), os.path.join(_ROOT, "mildoc_admin")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))

from loguru import logger
logger.remove()

ok = lambda m: print(f"  [PASS] {m}")
bad = lambda m: print(f"  [FAIL] {m}")


def test_history():
    print("\n=== 测试1：多轮历史能取到 AI 回复 ===")
    from connection_manager import get_connection
    from conversation_manager import build_history_lines, message_recently

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT open_kfid, external_userid FROM conversation_messages "
                "WHERE origin=666 ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
    if not row:
        print("  [SKIP] 无会话数据")
        return
    kfid, uid = row["open_kfid"], row["external_userid"]
    print(f"  样本用户: {uid[:24]}...")

    rows = message_recently(kfid, uid, limit=10)
    origins = sorted({r["origin"] for r in rows})
    if 666 in origins:
        ok(f"历史记录已包含 AI 回复，origin 分布={origins}")
    else:
        bad(f"历史记录仍缺少 AI 回复，origin 分布={origins}")

    lines = build_history_lines(kfid, uid, limit=10)
    if lines:
        ok(f"组装出 {len(lines)} 条历史行")
        for ln in lines[:4]:
            print(f"        {ln[:70]}")
    else:
        bad("历史行为空")


def test_parsers():
    print("\n=== 测试2：解析器链（未配置 MinerU 时行为不变）===")
    import importlib
    import oss_object_parser as p
    importlib.reload(p)
    names = [type(x).__name__ for x in p._parsers]
    print(f"  解析器链: {names}")
    if "MinerUParser" not in names:
        ok("未配置 MINERU_SERVER_URL，MinerU 未注册（与原行为一致）")
    else:
        ok("已注册 MinerU")

    # 回退逻辑：首选解析器返回空时，应继续尝试下一个
    class FakeBroken:
        def supports(self, ct): return True
        def parse(self, data): return ""
    class FakeGood:
        def supports(self, ct): return True
        def parse(self, data): return "hello world"
    saved = p._parsers
    p._parsers = [FakeBroken(), FakeGood()]
    try:
        r = p._parse_with_fallback(b"x", "text/plain")
        if r == "hello world":
            ok("首选解析器返回空时自动回退到下一个")
        else:
            bad(f"回退失败，结果={r!r}")
    finally:
        p._parsers = saved


def test_bulk_delete():
    print("\n=== 测试3：超过 100 分片能完整删除 ===")
    import dashvector
    from dashvector import Doc
    from doc_fragment import DocFragment
    import dash_vector_api as dv

    c = dv._get_dashvector_collection()
    test_path = "_test_bulk_delete_"
    # 先清理可能残留的历史测试数据
    dv.delete_doc_fragments(test_path)

    # 插入 150 个分片（超过原 topk=100 上限）
    N = 150
    vec = [0.01] * int(os.getenv("DASHVECTOR_DIM", "768"))
    docs = [Doc(id=f"{test_path}_{i}", vector=vec,
                fields={"doc_name": "bulk", "doc_path": test_path,
                        "doc_type": "text/plain", "doc_md5": "x",
                        "doc_length": 10, "content": f"chunk {i}"})
            for i in range(N)]
    for i in range(0, N, 25):
        c.upsert(docs[i:i + 25])

    got = len(dv._query_doc_fragment_ids_once(test_path))
    print(f"  已插入 {N} 个分片，单次查询返回 {got} 条（topk 上限 1024）")

    result = dv.delete_doc_fragments(test_path)
    left = len(dv._query_doc_fragment_ids_once(test_path))
    if result and left == 0:
        ok(f"循环删除生效，{N} 个分片全部清除，残留={left}")
    else:
        bad(f"删除不干净，残留={left} 个分片（旧实现会残留 {N - 100} 个）")


def test_event_flow():
    print("\n=== 测试4：事件处理返回值语义 ===")
    from oss_object_processor import process_oss_event, OSSEvent, OSSEventType
    # 未知事件类型应视为已处理（重试无意义），返回 True
    r = process_oss_event(OSSEvent(OSSEventType.UNKNOWN, "t", "b", "k"))
    if r is True:
        ok("未知事件类型返回 True（不触发无效重试）")
    else:
        bad(f"未知事件返回 {r}")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("=" * 60)
    print("  MilDoc 修复验证")
    print("=" * 60)
    test_history()
    test_parsers()
    test_bulk_delete()
    test_event_flow()
    print("\n" + "=" * 60)
    print("  验证结束")
    print("=" * 60)
