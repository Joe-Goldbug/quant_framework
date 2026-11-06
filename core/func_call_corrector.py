"""
func_call_corrector.py
本地 AST 算子语法解析、自动纠正与骨架防摸鱼沙箱 (AEGIS v3.0 Hardness 版)
彻底解决：
1. 算子别名自动重写: ts_moving_average/ts_avg -> ts_mean, sub -> subtract, div -> divide, etc.
2. 参数别名容错: 将 d=5, lookback=10 纠正为位置参数 (e.g. ts_delta(x, 5))
3. 复杂高阶算子默认参数自动补齐 (e.g. jump_decay 补齐 sensitivity=0.5, force=0.1)
4. Group 算子非法引号剥离 (group_rank(x, "subindustry") -> group_rank(x, subindustry))
5. 双层防重门禁 (Exact MD5 + Skeleton Hash):
   - AST 拓扑骨架提取 (将所有数值常量替换为 NUM) 并求哈希
   - 单批 8 槽内若同一种骨架出现 > 2 条，直接熔断打回重做（物理杜绝简单参数微调）
   - 若与上一批未达标骨架 100% 重复，直接熔断打回
"""

import ast
import hashlib
import json
import os
import re
import sqlite3
import sys
from typing import Dict, List, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

class SkeletonTransformer(ast.NodeTransformer):
    """将 AST 中所有的数值常量替换为 'NUM' 占位符以抽取纯拓扑骨架"""
    def visit_Constant(self, node):
        if isinstance(node.value, (int, float)):
            return ast.Name(id='NUM', ctx=ast.Load())
        return node

class ASTSandboxCorrector:
    OPERATOR_ALIASES = {
        "ts_moving_average": "ts_mean",
        "ts_avg": "ts_mean",
        "decay_linear": "ts_decay_linear",
        "ts_decay_exponential": "ts_decay_exp_window",
        "ts_decay_exp": "ts_decay_exp_window",
        "sub": "subtract",
        "div": "divide",
        "neg": "reverse",
        "std": "ts_std_dev",
        "ts_std": "ts_std_dev",
        "corr": "ts_corr"
    }

    PARAM_ALIASES = {"d", "d1", "day", "days", "lookback", "window", "time"}

    def __init__(self, db_path: str = None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__), "..", "alphas_record.db")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取开启 WAL 模式与高容忍 Timeout 的 SQLite 连接"""
        try:
            from quant_framework.core.concurrency_utils import get_sqlite_wal_connection
            return get_sqlite_wal_connection(self.db_path)
        except Exception:
            try:
                from core.concurrency_utils import get_sqlite_wal_connection
                return get_sqlite_wal_connection(self.db_path)
            except Exception:
                conn = sqlite3.connect(self.db_path, timeout=15.0)
                try:
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("PRAGMA busy_timeout=15000;")
                except Exception:
                    pass
                return conn

    def _init_db(self):
        """初始化指纹与骨架数据库"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alpha_fingerprints (
                md5_hash TEXT PRIMARY KEY,
                skeleton_hash TEXT,
                skeleton_str TEXT,
                expression TEXT,
                region TEXT,
                universe TEXT,
                delay INTEGER,
                neutralization TEXT,
                batch_id TEXT,
                sim_status TEXT DEFAULT 'COMPLETED',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_skeleton ON alpha_fingerprints(skeleton_hash)')
        try:
            cursor.execute("ALTER TABLE alpha_fingerprints ADD COLUMN batch_id TEXT")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE alpha_fingerprints ADD COLUMN sim_status TEXT DEFAULT 'COMPLETED'")
        except Exception:
            pass
        conn.commit()
        conn.close()

    @classmethod
    def correct_expression(cls, expr: str) -> str:
        """本地 AST 语法分析与智能修复"""
        cleaned = expr.strip()

        # 1. 正则预处理 Group 算子中多余的引号: group_*(x, "subindustry") -> group_*(x, subindustry)
        cleaned = re.sub(r'(group_[a-zA-Z_]+\s*\([^,]+,\s*)["\']([a-zA-Z_]+)["\'](\s*\))', r'\1\2\3', cleaned)

        # 2. 算子别名快速替换
        for alias, target in cls.OPERATOR_ALIASES.items():
            pattern = rf'\b{alias}\s*\('
            cleaned = re.sub(pattern, f"{target}(", cleaned)

        # 3. 参数别名正则纠正 (如 d=5, lookback=10 -> 5, 10)
        for p in cls.PARAM_ALIASES:
            cleaned = re.sub(rf'(,\s*){p}\s*=\s*([0-9.]+)', r'\1\2', cleaned)

        # 4. 高阶算子参数默认值补全 (jump_decay 需 sensitivity 和 force)
        if "jump_decay(" in cleaned and "sensitivity" not in cleaned and "force" not in cleaned:
            cleaned = re.sub(r'jump_decay\s*\(([^,]+),\s*([0-9.]+)\s*\)', r'jump_decay(\1, \2, sensitivity=0.5, force=0.1)', cleaned)

        return cleaned

    @classmethod
    def get_canonical_skeleton(cls, expr: str) -> str:
        """
        通过 AST 节点转换抽取标准拓扑骨架 (消除数字参数差异)
        """
        corrected = cls.correct_expression(expr)
        try:
            tree = ast.parse(corrected, mode='eval')
            transformed = SkeletonTransformer().visit(tree)
            skeleton = ast.unparse(transformed)
            # 统一去除空格
            return re.sub(r'\s+', '', skeleton)
        except Exception:
            # 降级备选方案：正则替换所有纯数字为 NUM
            return re.sub(r'\b\d+(\.\d+)?\b', 'NUM', re.sub(r'\s+', '', corrected))

    @classmethod
    def compute_skeleton_hash(cls, skeleton_str: str) -> str:
        """计算骨架 SHA256/MD5 指纹"""
        return hashlib.md5(skeleton_str.encode('utf-8')).hexdigest()

    def compute_fingerprint(self, expr: str, region: str, universe: str, delay: int, neutralization: str = "NONE") -> str:
        """计算 Exact 组合指纹"""
        norm_expr = re.sub(r'\s+', '', expr.lower())
        payload = {
            "expression": norm_expr,
            "region": region,
            "universe": universe,
            "delay": delay,
            "neutralization": neutralization
        }
        return hashlib.md5(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()

    def remove_records(self, expressions: list, region: str, universe: str, delay: int, neutralization: str = "NONE"):
        """从指纹库中回滚未成功回测的表达式 (防止未完成/已取消任务污染指纹库导致假性去重拦截)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        hashes = [self.compute_fingerprint(self.correct_expression(e), region, universe, delay, neutralization) for e in expressions]
        cursor.executemany("DELETE FROM alpha_fingerprints WHERE md5_hash = ?", [(h,) for h in hashes])
        conn.commit()
        conn.close()

    def record_batch(self, expressions: list, region: str, universe: str, delay: int, neutralization: str = "NONE", batch_id: str = None):
        """将已完成成功回测的表达式显式写入数据库"""
        conn = self._get_connection()
        cursor = conn.cursor()
        corrected_exprs = [self.correct_expression(x) for x in expressions]
        skeletons = [self.get_canonical_skeleton(x) for x in corrected_exprs]
        skeleton_hashes = [self.compute_skeleton_hash(s) for s in skeletons]

        new_records = []
        for expr, skel, skel_hash in zip(corrected_exprs, skeletons, skeleton_hashes):
            h = self.compute_fingerprint(expr, region, universe, delay, neutralization)
            new_records.append((h, skel_hash, skel, expr, region, universe, delay, neutralization, batch_id, "COMPLETED"))

        cursor.executemany('''
            INSERT OR REPLACE INTO alpha_fingerprints (md5_hash, skeleton_hash, skeleton_str, expression, region, universe, delay, neutralization, batch_id, sim_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', new_records)
        conn.commit()
        conn.close()

    def check_and_record_batch(self, expressions: list, region: str, universe: str, delay: int, neutralization: str = "NONE", batch_id: str = None, record: bool = True, max_hist_count: int = 8, is_exploit_or_step2: bool = False) -> list:
        """
        双层防重门禁 (Exact MD5 + Skeleton Hash 熔断)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        corrected_exprs = [self.correct_expression(x) for x in expressions]
        skeletons = [self.get_canonical_skeleton(x) for x in corrected_exprs]
        skeleton_hashes = [self.compute_skeleton_hash(s) for s in skeletons]

        # 1. 批次内部骨架多样性门禁：支持弹性容量缩放 (8槽限2条，20槽限4条；精修/exploit阶段放宽至60%对齐SwarmAuditor)
        ratio_cap = 0.60 if is_exploit_or_step2 else 0.20
        max_allowed_per_skel = max(2, int(len(expressions) * ratio_cap))
        skeleton_freq: Dict[str, List[int]] = {}
        for idx, s_str in enumerate(skeletons):
            skeleton_freq.setdefault(s_str, []).append(idx + 1)

        overpopulated_skeletons = {k: v for k, v in skeleton_freq.items() if len(v) > max_allowed_per_skel}
        if overpopulated_skeletons:
            conn.close()
            details = []
            for skel, slots in overpopulated_skeletons.items():
                details.append(f"  - 骨架 [{skel}] 占据了卡槽 {slots} (共 {len(slots)} 条 > {max_allowed_per_skel} 条上限)")
            raise ValueError(
                f"【AST Skeleton 摸鱼微调熔断】检测到单批变体中同质化骨架堆叠！\n"
                f"系统硬性规定：单批中相同算子骨架最多只允许 {max_allowed_per_skel} 条（参数敏感性验证），严禁网格调参！\n"
                f"违规骨架详情:\n" + "\n".join(details) + "\n请引入不同的数学拓扑（如指数半衰期平滑 vs 行业中性化 vs 动量差分）！"
            )

        # 2. 数据库历史去重 (Exact MD5) 与 跨批次历史骨架累积查重 (Gate 3 终极加固)
        duplicates = []
        new_records = []
        for expr, skel, skel_hash in zip(corrected_exprs, skeletons, skeleton_hashes):
            # 2.1 跨批次骨架频次核查：若该拓扑骨架在相同中性化下历史回测中已测试 >= max_hist_count (>= 8) 次，直接熔断
            # 若提供了 batch_id，排除当前批次自身的旧记录 (支持幂等重跑与断点恢复)
            # 若处于 step >= 2 的母本精修阶段，豁免骨架熔断以支持参数精调
            if not is_exploit_or_step2:
                if batch_id:
                    cursor.execute(
                        "SELECT COUNT(*) FROM alpha_fingerprints WHERE skeleton_hash = ? AND region = ? AND universe = ? AND (neutralization = ? OR neutralization IS NULL) AND (batch_id != ? OR batch_id IS NULL)", 
                        (skel_hash, region, universe, neutralization, batch_id)
                    )
                else:
                    cursor.execute(
                        "SELECT COUNT(*) FROM alpha_fingerprints WHERE skeleton_hash = ? AND region = ? AND universe = ? AND (neutralization = ? OR neutralization IS NULL)", 
                        (skel_hash, region, universe, neutralization)
                    )
                hist_count = cursor.fetchone()[0]
                if hist_count >= max_hist_count:
                    conn.close()
                    raise ValueError(
                        f"【跨批次骨架耗尽熔断】该算子+字段骨架在中性化 [{neutralization}] 下已累计微调测试 {hist_count} 次 (>= {max_hist_count} 次上限)！\n"
                        f"违规骨架: [{skel}]\n"
                        f"系统硬性禁止继续修改数字窗口调参！必须更换底层数据集字段、更换中性化维度或改变算子拓扑结构！"
                    )

            # 2.2 精确 MD5 组合查重
            h = self.compute_fingerprint(expr, region, universe, delay, neutralization)
            if batch_id:
                cursor.execute("SELECT expression FROM alpha_fingerprints WHERE md5_hash = ? AND (batch_id != ? OR batch_id IS NULL)", (h, batch_id))
            else:
                cursor.execute("SELECT expression FROM alpha_fingerprints WHERE md5_hash = ?", (h,))
            row = cursor.fetchone()
            if row:
                duplicates.append({"expr": expr, "hash": h, "matched": row[0]})
            else:
                new_records.append((h, skel_hash, skel, expr, region, universe, delay, neutralization, batch_id, "COMPLETED"))

        if len(duplicates) > 2:
            conn.close()
            dup_details = "\n".join([f"- {d['expr']} (曾测过: {d['matched']})" for d in duplicates])
            raise ValueError(
                f"[AST Sandbox 拦截] 本批次检测到 {len(duplicates)} 条已测过的历史组合！\n"
                f"严禁进行简单参数微调。必须引入新的数学逻辑或正交字段！\n"
                f"重复项:\n{dup_details}"
            )

        # 3. 写入新记录 (若 record=True)
        if record:
            cursor.executemany('''
                INSERT OR REPLACE INTO alpha_fingerprints (md5_hash, skeleton_hash, skeleton_str, expression, region, universe, delay, neutralization, batch_id, sim_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', new_records)
            conn.commit()
        conn.close()

        return corrected_exprs

if __name__ == "__main__":
    corrector = ASTSandboxCorrector(":memory:")
    
    # 测试骨架抽取
    e1 = "group_rank(ts_decay_linear(sentiment, 10), subindustry)"
    e2 = "group_rank(ts_decay_linear(sentiment, 20), subindustry)"
    s1 = corrector.get_canonical_skeleton(e1)
    s2 = corrector.get_canonical_skeleton(e2)
    print("Skeleton 1:", s1)
    print("Skeleton 2:", s2)
    assert s1 == s2, "骨架应当完全一致！"
    print("✅ 骨架提取测试通过！")

    # 测试批次内部微调熔断 (> 2 条相同骨架)
    bad_batch = [
        "group_rank(ts_decay_linear(sentiment, 5), subindustry)",
        "group_rank(ts_decay_linear(sentiment, 10), subindustry)",
        "group_rank(ts_decay_linear(sentiment, 15), subindustry)", # 第 3 条相同骨架！
        "group_rank(ts_decay_exp_window(sentiment, 5, factor=0.5), subindustry)",
        "group_rank(ts_decay_exp_window(sentiment, 10, factor=0.5), subindustry)",
        "group_rank(winsorize(sentiment, std=3), subindustry)",
        "group_rank(ts_delta(sentiment, 3), subindustry)",
        "group_rank(s_log_1p(sentiment), subindustry)"
    ]
    try:
        corrector.check_and_record_batch(bad_batch, "USA", "TOP1000", 1)
        print("❌ 应该被拦截却放过了！")
    except ValueError as ex:
        print("✅ 成功拦截摸鱼批次:", str(ex)[:80], "...")
