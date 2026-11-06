"""
quant_framework/core/field_resolver.py
跨区域/多市场字段画像解析与容灾冷启动模块 (DatasetFieldResolver)

核心功能:
1. 多格式自适应解析:
   - 兼容 List 格式 (Brain API 原始返回: [ {"id": "...", "type": "MATRIX", "coverage": 0.85, ...}, ... ])
   - 兼容 Dict 格式 (画像库结构: {"fields": {"f1": {...}}} 或 {"f1": {...}})
2. 跨区域同源继承 (Cross-Region Inheritance):
   - 当请求 GLB/EUR/ASI 等市场且本地缺少该区域字段画像时，
     自动智能检索 USA / GLOBAL 同名基础数据集 (如 fundamental23, fundamental17, news12)，
     财务/量价底层特征天然同源，实现 0 延迟冷启动，彻底规避在线 API 查询超时风险。
3. 外部字段动态注入:
   - 支持通过 --fields-file 指定外部字段画像 JSON
   - 支持通过 --fields 传入逗号分隔的字段字符串列表
4. 自动落盘持久化:
   - 首次解析或继承成功后，自动落盘缓存至 knowledge_base/fields/{region}/{dataset_id}.json，终生避免重复查询。
"""

import os
import json
import random
from typing import Dict, List, Optional, Any


class DatasetFieldResolver:
    """数据集字段画像解析器与跨市场容灾引擎"""

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.kb_root = os.path.join(self.base_dir, "knowledge_base", "fields")
        self.default_kb_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "fields"))

    def resolve_fields(
        self,
        region: str,
        category: str,
        dataset_id: str,
        fields_file: Optional[str] = None,
        raw_fields_arg: Optional[str] = None,
        allow_cross_region: bool = True
    ) -> Dict[str, Dict[str, Any]]:
        """
        全流程解析字段画像字典:
        返回格式: { "field_id": { "type": "MATRIX/VECTOR", "description": "...", "coverage": float, ... } }
        """
        region = region.upper()
        dataset_id = dataset_id.lower()

        # 1. 优先级最高: 命令行直接显式指定的字段清单 (--fields "f1,f2,f3")
        if raw_fields_arg:
            field_list = [f.strip() for f in raw_fields_arg.split(",") if f.strip()]
            if field_list:
                print(f"📌 [FieldResolver] 从命令行参数 --fields 显式载入 {len(field_list)} 个字段")
                return {fn: {"type": "MATRIX", "description": "命令行直接指定字段", "coverage": 1.0} for fn in field_list}

        # 2. 优先级二: 显式指定的外部字段文件 (--fields-file <path>)
        if fields_file and os.path.exists(fields_file):
            print(f"📁 [FieldResolver] 从指定文件载入字段画像: {fields_file}")
            parsed = self._parse_file(fields_file)
            if parsed:
                return parsed

        # 3. 优先级三: 本地知识库目标区域精确与别名匹配 (knowledge_base/fields/{region}/{dataset_id}.json)
        cand_ds_names = [dataset_id]
        if dataset_id.startswith("oth") and not dataset_id.startswith("other"):
            cand_ds_names.append(f"other{dataset_id[3:]}")
        elif dataset_id.startswith("other"):
            cand_ds_names.append(f"oth{dataset_id[5:]}")
        if dataset_id.startswith("fnd"):
            cand_ds_names.append(f"fundamental{dataset_id[3:]}")
        elif dataset_id.startswith("fundamental"):
            cand_ds_names.append(f"fnd{dataset_id[11:]}")
        if dataset_id.startswith("nws"):
            cand_ds_names.append(f"news{dataset_id[3:]}")
        elif dataset_id.startswith("news"):
            cand_ds_names.append(f"nws{dataset_id[4:]}")

        search_roots = [self.kb_root]
        if self.default_kb_root != self.kb_root:
            search_roots.append(self.default_kb_root)

        for c_ds in cand_ds_names:
            for s_root in search_roots:
                target_path = os.path.join(s_root, region, f"{c_ds}.json")
                if os.path.exists(target_path):
                    parsed = self._parse_file(target_path)
                    if parsed:
                        print(f"✅ [FieldResolver] 匹配本地字段知识库: {region}/{c_ds} (共 {len(parsed)} 字段)")
                        return parsed

        # 4. 优先级四: 跨区域同源继承 (Cross-Region Inheritance)
        # 例如: GLB/EUR/ASI 请求 fundamental23，由于财务指标在各市场本质同构，可从已缓存的 USA 继承
        if allow_cross_region:
            candidate_regions = ["USA", "GLB", "GLOBAL"]
            for cand in candidate_regions:
                if cand == region:
                    continue
                for c_ds in cand_ds_names:
                    for s_root in search_roots:
                        cand_path = os.path.join(s_root, cand, f"{c_ds}.json")
                        if os.path.exists(cand_path):
                            parsed = self._parse_file(cand_path)
                            if parsed:
                                print(f"🌐 [FieldResolver] 目标区域 '{region}' 缺少字段画像，已触发跨区域同源继承 (从 {cand}/{c_ds} 载入 {len(parsed)} 个特征)！")
                                # 自动为当前区域落盘缓存，避免二次查找
                                self._save_cache(region, dataset_id, parsed)
                                return parsed

        # 5. 优先级五: 全局搜索任意子目录下同名 dataset_id.json
        for c_ds in cand_ds_names:
            for s_root in search_roots:
                if os.path.exists(s_root):
                    for root, _, files in os.walk(s_root):
                        if f"{c_ds}.json" in files:
                            found_path = os.path.join(root, f"{c_ds}.json")
                            parsed = self._parse_file(found_path)
                            if parsed:
                                print(f"🔍 [FieldResolver] 在全局字段库中定位到同名画像: {found_path} (共 {len(parsed)} 字段)")
                                self._save_cache(region, dataset_id, parsed)
                                return parsed

        # 6. 物理熔断: 严禁生成伪造字段或将假字段写入缓存污染知识库
        raise FileNotFoundError(
            f"❌ [FieldResolver 物理熔断] 无法在知识库或任何已知区域中找到 {region}/{dataset_id} 字段画像！\n"
            f"   依据 01_field_explorer.md 契约，严禁在未建立真实数据画像时通过生成伪造字段推进流程！\n"
            f"   请先运行 01_field_explorer 探针脚本生成真实字段画像 JSON 后再启动挖掘。"
        )

    def _parse_file(self, file_path: str) -> Dict[str, Dict[str, Any]]:
        """自适应解析 List 格式与 Dict 格式的字段定义"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"❌ [FieldResolver] 读取文件失败 {file_path}: {e}")
            return {}

        result: Dict[str, Dict[str, Any]] = {}

        # 格式 A: Brain 原始 API 数组 [ {"id": "accounts_cash_and_equivalents", "type": "MATRIX", ...}, ... ]
        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                fid = item.get("id") or item.get("name")
                if not fid:
                    continue
                entry = dict(item)
                entry.setdefault("type", item.get("type", "MATRIX"))
                entry.setdefault("description", item.get("role_note", item.get("description", "无描述")))
                try:
                    entry["coverage"] = float(item.get("coverage", item.get("dateCoverage", 1.0)))
                except (ValueError, TypeError):
                    entry["coverage"] = 1.0
                entry["user_count"] = item.get("userCount", item.get("user_count", 0))
                entry["alpha_count"] = item.get("alphaCount", item.get("alpha_count", 0))
                cat_val = item.get("category", {}).get("name", "Unknown") if isinstance(item.get("category"), dict) else str(item.get("category", ""))
                entry.setdefault("category", cat_val)
                entry.setdefault("skewness", "medium")
                entry.setdefault("domain", item.get("domain", "unbounded"))
                entry.setdefault("is_sparse", item.get("is_sparse", False))
                result[fid] = entry
            return result

        # 格式 B: 字典格式
        if isinstance(data, dict):
            # 嵌套 fields: { "fields": { "f1": {...} } }
            if "fields" in data and isinstance(data["fields"], dict):
                raw_dict = data["fields"]
            else:
                raw_dict = data

            for k, v in raw_dict.items():
                if k in ("dataset_id", "region", "universe", "delay", "total_fields", "universal_laws", "dataset_verdict"):
                    continue
                if isinstance(v, dict):
                    entry = dict(v)
                    entry.setdefault("type", "MATRIX")
                    entry.setdefault("description", v.get("role_note", v.get("description", "无描述")))
                    try:
                        entry["coverage"] = float(v.get("coverage", 1.0))
                    except (ValueError, TypeError):
                        entry["coverage"] = 1.0
                    entry.setdefault("alpha_count", v.get("alphaCount", v.get("alpha_count", 0)))
                    entry.setdefault("user_count", v.get("userCount", v.get("user_count", 0)))
                    entry.setdefault("domain", v.get("domain", "unbounded"))
                    entry.setdefault("is_sparse", v.get("is_sparse", False))
                    entry.setdefault("update_frequency", v.get("update_frequency", "daily"))
                    entry.setdefault("semantic_role", v.get("semantic_role", "Signal_Flow"))
                    entry.setdefault("skewness", v.get("skewness", "medium"))
                    result[k] = entry
                else:
                    result[k] = {
                        "type": "MATRIX",
                        "description": str(v),
                        "coverage": 1.0,
                        "skewness": "medium",
                        "domain": "unbounded",
                        "is_sparse": False,
                        "alpha_count": 0,
                        "user_count": 0
                    }
            return result

        return {}

    def _save_cache(self, region: str, dataset_id: str, fields_dict: Dict[str, Dict[str, Any]]):
        """将解析的画像自动落盘缓存"""
        try:
            target_dir = os.path.join(self.kb_root, region)
            os.makedirs(target_dir, exist_ok=True)
            target_path = os.path.join(target_dir, f"{dataset_id}.json")
            if not os.path.exists(target_path):
                # 以统一的规范画像格式落盘
                payload = {
                    "dataset_id": dataset_id,
                    "region": region,
                    "total_fields": len(fields_dict),
                    "fields": fields_dict
                }
                with open(target_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
                print(f"💾 [FieldResolver] 字段画像已自动落盘缓存至: {target_path}")
        except Exception as e:
            print(f"⚠️  [FieldResolver] 自动缓存写入异常: {e}")

