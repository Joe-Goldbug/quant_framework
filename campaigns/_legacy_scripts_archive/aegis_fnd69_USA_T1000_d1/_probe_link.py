# -*- coding: utf-8 -*-
"""BRAIN 链路只读探针：authenticate + 读取本机 IS alpha 列表 + 拉取 fundamental69 字段清单。
只读 GET，不发起任何仿真、不调用任何提交接口。
"""
import asyncio
import json
import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

import main as bm  # noqa: E402


async def main():
    out = {}
    try:
        auth = await bm.authenticate()
        out["authenticate"] = auth
    except Exception as e:
        out["authenticate"] = {"exception": repr(e)}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    # 只读：本机 alpha 列表（用于雷同/相关性排查）
    try:
        lst = await bm.get_user_alphas(limit=20, offset=0)
        out["user_alphas_head"] = lst
    except Exception as e:
        out["user_alphas_error"] = repr(e)

    # 只读：fundamental69 字段清单
    try:
        df = await bm.get_datafields(region="USA", delay=1, universe="TOP1000",
                                     dataset_id="fundamental69", search="", limit=200)
        out["fundamental69_fields"] = df
    except Exception as e:
        out["datafields_error"] = repr(e)

    p = os.path.join(HERE, "_probe_link.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("[ok] wrote", p)
    print(json.dumps({k: (str(v)[:400]) for k, v in out.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
