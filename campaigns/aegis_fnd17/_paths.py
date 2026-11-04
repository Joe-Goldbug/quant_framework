# -*- coding: utf-8 -*-
"""AEGIS 战役路径解析器（去硬编码，抗目录整理）

背景：2026-10-28 17:05 工作区 housekeeping 把 `aegis_coldstart/` 整体搬进 `_legacy/`，
原先所有脚本里写死的 `D:\\...\\.agents\\aegis_coldstart\\campaign_fnd17` 全部失效。
本模块改为**按结构特征向上查找 .agents 根**（含 quant_framework/core 与 knowledge_base/fields），
并把战役目录锚定到**脚本自身所在目录**，从而无论战役被挪到 campaigns/ 还是 _legacy/ 都能跑。
"""
import os
import sys

# ---------------------------------------------------------------- .agents 根
def _find_agents_root(start=None):
    """向上查找含 quant_framework/core 的目录；找不到则回退到本文件的第 3 层祖先。"""
    cur = os.path.abspath(start or __file__)
    probe = cur if os.path.isdir(cur) else os.path.dirname(cur)
    for _ in range(8):
        if os.path.isdir(os.path.join(probe, "quant_framework", "core")):
            return probe
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    return os.path.abspath(os.path.join(os.path.dirname(cur), "..", ".."))


ROOT = _find_agents_root()
HERE = os.path.dirname(os.path.abspath(__file__))
CAMPAIGN = HERE


def _ensure_on_path():
    for p in (ROOT, HERE):
        if p not in sys.path:
            sys.path.insert(0, p)


_ensure_on_path()

# ---------------------------------------------------------------- 常用落点
FIELDS_KB = os.path.join(ROOT, "knowledge_base", "fields", "USA", "fundamental17.json")
ALPHAS_DB = os.path.join(ROOT, "quant_framework", "alphas_record.db")
DOSSIER = os.path.join(CAMPAIGN, "fnd17_field_dossier.json")
LAG_PAIRS = os.path.join(CAMPAIGN, "fnd17_lag_pairs.json")
SLICES = os.path.join(CAMPAIGN, "slices")
CATALOG_MD = os.path.join(CAMPAIGN, "fnd17_catalog.md")


def resolve(*parts):
    """战役内相对路径。"""
    return os.path.join(CAMPAIGN, *parts)


if __name__ == "__main__":
    print("ROOT   =", ROOT)
    print("HERE   =", HERE)
    print("KB     =", FIELDS_KB, os.path.exists(FIELDS_KB))
    print("DB     =", ALPHAS_DB, os.path.exists(ALPHAS_DB))
    print("DOSSIER=", DOSSIER, os.path.exists(DOSSIER))
