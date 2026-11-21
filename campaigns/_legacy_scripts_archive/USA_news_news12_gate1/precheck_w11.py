# -*- coding: utf-8 -*-
"""W11b 处方攻坚预检 v3 (2026-10-25, AEGIS 种子因子定向优化模式).
(改名避让: 已有 phase13_wave11a_fundamental 批发射过, 本计划称 W11b)

种子: mLYNEWjW (w10h 合流核心, 全战役最佳近 miss)
  trade_when(less(days_from_last_change(vec_count(VHEX)), 2),
    reverse(rank(divide(subtract(EOC, TON), add(vec_count(VHEX), 1)))), 0)
  Sh 1.59 / Fit 0.41 / TO 114.59% / Ret 7.52% / 2Y 2.03 / Sub 1.39 / Mgn 1.31bps
  CLUSTER 1.54 / CW pass / L/S 312/307; ra fail = LOW_FITNESS + HIGH_TURNOVER;
  警告 = CLUSTER_TEST + MATCHES_THEMES.

=== v3 设计依据: 红队终审(NO-GO) + 双研究 agent 情报 + 红队复审后的重构 ===
[删除] ts_rank250 壳线 (v2 槽4/6/8): 2rjx3ow8 实读证伪 —— 本基座上壳把
  Sh 1.59->1.46, CLUSTER 1.54->1.32, TO 112.4%; 且 ts_rank(-x) != 1-ts_rank(x)
  (零稀疏序列并列破裂, 红队数值实锤 max 偏差 1.0) —— 恒等变换对非线性算子无效.
[删除] RATIO_R 省 reverse 恒等式 (复审必修 M2-1): rank(-x)=1-rank(x) 与 reverse
  复合差常数 1, 无门时被中性化除去, 但 trade_when 门把常数 1 调制成门 flag g,
  中性化后残留 g-mean(g) (std≈0.497) 一阶大于信号 (std≈0.29) —— 门控基座上
  一律用显式 reverse + RATIO_F.
[新增依据1] 平台 checks 豁免规律 (352/352 行零例外实读):
  |Sharpe| >= 1.0 且 Turnover <= 70%  =>  LOW_SHARPE/LOW_FITNESS/LOW_2Y_SHARPE
  全部从 fail 降级为 warning; 且 fail=[] 的 26 行全部无 MATCHES_THEMES (26/26) ——
  "无 fail" 与 "无 MATCHES_THEMES" 互补.
  ==> 战略: 先以低 TO (<=70%) + 中 Sh (>=1.0) 拿掉 fail, 再逐项清警告.
[新增依据2] b9/b10/b11 补充批 (研报口径外 24 槽, INDUSTRY/d6, 与 W1 同设置):
  ts_backfill(CTO/(count+1), 2) 无门  -> Sh 1.43 / TO 84.1% (QPYxb9vp)
  ts_backfill(CTO/(count+1), 3) 无门  -> Sh 1.20 / TO 68.8% (MP0E7qxL, TO 已过门!)
  bf5 无门 -> Sh 0.99 / TO 54%;  bf2 x ts_decay_linear(2) -> Sh 1.37 / TO 72.0%
  双压力分子 (EOC-TON)+(EOC-VWAP) bf2 无门 -> Sh 1.27 / Ret 7.68% / TO 86.1% (WjLZbE7N)
  ==> bf 短窗是降 TO 便宜路径; 双压力分子是 Ret 放大器; 二者与 mLYNEWjW 硬门
      (trade_when(dflc<2, X, 0)) 的组合从未测过 —— W11b 槽1/2/3 的首测配对.
[新增依据3] 门不是 TO 杠杆 (w10i 实证: dflc<5 门 TO 115.0% vs 母本 114.6%);
  dflc<1 收紧的真实先证: Sh 1.65->1.62, CLUSTER +0.01 (近中性, 非 +0.04);
  b9 双门版 (dflc<1 OR dflc>5) Sh 1.56-1.57, CLUSTER 族顶 1.56 (3qjKl3Ag).
[新增依据4] CLUSTER_TEST = 簇层面 Sharpe (簇内信号等权合成对簇收益的预测力);
  社区"提升系统性十法"前两位 = 拉长回看期(池化)与 winsorize 降噪 —— 与槽5/6/8 对应.
[新增依据5] 字段安全: news_eod_open 曾被 b10 使用但已从平台 875 字段池下线
  (API 全量实读 False) -> 整批 CANCELLED 连坐风险, W11b 弃用, 双压力第二锚点
  改用 news_eod_vwap (字典+平台双确认).
[新算子 smoke test] ts_decay_exp_window / winsorize 在本地 352 行零完成实证
  (仅 API 声明 + DB 发射记录) —— 发射前先跑 2 条探针批 (decay d10 + winsorize std3
  变体), 通过后才发主批, 规避 gate1_C/gate2_F 式整批连坐.
[Fit 口径] Fit = Sh*sqrt(Ret/max(TO,~0.11)); 族内最低 TO 17.3% > 下限, 故下限
  值 (0.11 vs 0.125 社区争议) 在本族从未激活, 不影响判读.

工程恒等式 (v3 全面废止省 reverse 变形, 全部显式 reverse + RATIO_F):
  门控基座上"常数差"被门 flag 调制, 中性化不保证除去 (见 M2-1); 唯一安全方向
  处理 = 与母本逐字一致的 reverse(rank(RATIO_F)) 骨架.

三批配对设计 (settings 批级; b9/b10/b11 已确认 INDUSTRY/d6, 配对干净):
  W1 INDUSTRY/decay=6  : 8 条处方 (主批; 与 b9/b10/b11 无门版构成门效应配对)
  W2 MARKET/decay=6    : 同 7 条 + 母本对照 (中性化下沉抬 Margin, 用户点题③)
  W3 INDUSTRY/decay=20 : 同 8 条 (decay x bf/门交互零测试; w10a 的 d25 负先证
                          来自无门单压力基座, 门+bf 基座未测, 负先证不可外推)
"""
import json
import os
import sqlite3
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, r"D:\brain-mcp")
os.environ["BRAIN_MCP_CONFIG"] = r"D:\brain-mcp\user_config.json"

from quant_framework.core.func_call_corrector import ASTSandboxCorrector  # noqa: E402
from quant_framework.core.dimension_rules import DimensionAuditor  # noqa: E402

REGION, UNIVERSE, DELAY = "USA", "TOP1000", 1
CATEGORY = "news"

EOC, TON, VWAP = "news_eod_close", "news_ton_last", "news_eod_vwap"
VHEX = "high_price_excursion_stddev"
# 注: news_eod_open 曾被 b10 批使用过, 但平台当前字段池 (875 全量实读) 已无此字段
# (疑被下线) -> 整批 CANCELLED 连坐风险, W11 弃用; 双压力第二锚点改用 news_eod_vwap.

# ---- 基座构件 (mLYNEWjW 逐字) ----
GATE2 = f"days_from_last_change(vec_count({VHEX})), 2"
GATE1 = f"days_from_last_change(vec_count({VHEX})), 1"
# 正向分子比 (母本方向): CTO/(count+1), CTO = EOC - TON
RATIO_F = f"divide(subtract({EOC}, {TON}), add(vec_count({VHEX}), 1))"
# 反向分子比 (恒等变换方向, 省 reverse; 仅配线性算子)
RATIO_R = f"divide(subtract({TON}, {EOC}), add(vec_count({VHEX}), 1))"
# 双压力分子 (EOC-TON)+(EOC-VWAP), 以 VWAP 归一 (b10 实证 Ret 放大器)
DUAL_F = f"divide(add(subtract({EOC}, {TON}), subtract({EOC}, {VWAP})), {VWAP})"
# 净压力池化分子 (b9 内核的池化形式, 量纲为美元)
NET = f"subtract({EOC}, {TON})"
NETABS = f"abs({NET})"

# ================================================================ 8 条处方
SLOTS = [
    {"id": 1, "type": "BF2_FRESHGATE",
     "lesion": "H1 HIGH_TURNOVER",
     "expression": f"trade_when(less({GATE2}), reverse(rank(ts_backfill({RATIO_F}, 2))), 0)",
     "optimize_reason": (
        "【短回填 x 新鲜门 · H1 主攻 · 配对 QPYxb9vp】ts_backfill(x,2): 把事件日后的"
        " NaN 用最近 2 日的非空值填充 = 事件信号保持 2 个交易日, 仓位跨日延续 -> "
        "TO 从 114.6% 结构性地降. b11 实读 (无门版, 同设置 INDUSTRY/d6): bf2 -> "
        "Sh 1.43 / TO 84.1% / Ret 6.66% / 2Y 1.41 (QPYxb9vp); bf3 -> Sh 1.20 / "
        "TO 68.8% (MP0E7qxL, TO 已过 70% 门); bf5 -> Sh 0.99 / TO 54%. 门不是 TO 杠杆"
        " (w10i: dflc<5 门 TO 115.0% vs 母本 114.6%), 故本槽预期 TO~84% + 门过滤噪声日"
        "后 Sh 较无门版 (1.43) 不降反升; 若门在 bf 基座上产生未知的 TO 压缩交互, "
        "TO 可能逼近 70%. 这是全战役 TO-Sh 前沿上距双门最近的结构 (Sh 差 0.15, "
        "TO 差 14pp), 与 W3 的 decay=20 构成复合档. 判据: TO<=70% 且 Sh>=1.45 = "
        "双门同过; Sh>=1.58 = 标度律推翻.")},
    {"id": 2, "type": "BF3_FRESHGATE",
     "lesion": "H1 HIGH_TURNOVER",
     "expression": f"trade_when(less({GATE2}), reverse(rank(ts_backfill({RATIO_F}, 3))), 0)",
     "optimize_reason": (
        "【短回填3 x 新鲜门 · TO 已过门基座 · 配对 MP0E7qxL】bf3 无门版实读 TO 68.84%"
        " (<70% 硬门已过) 但 Sh 仅 1.20, 2Y 1.16, fail=[] 全警告 (豁免规律: |Sh|>=1 "
        "且 TO<=70% => fail 降 warning). 本槽在其上加 mLYNEWjW 硬门 (dflc<2): 门在"
        "无 bf 基座不改变 TO, 但在 bf3 基座上可能切除'陈旧填充日' (事件后第 3 日仍"
        "持仓但已非新鲜) 的残留仓位 -> 若 TO 微升而 Sh 跳升, 说明 bf3 的 Sh 损失源于"
        "陈旧值而非填充本身. 与槽1 (bf2) 构成回填窗口响应曲线 (2 vs 3), 与豁免规律"
        "合起来给出'门 x bf'交互的完整拓扑. 判据: Sh>=1.35 且 TO<=72% = 门修复了 "
        "bf3 的 Sh 损失; Sh<=1.25 = 填充机制与门控互斥, bf3 线关闭.")},
    {"id": 3, "type": "DFLC1_BF2",
     "lesion": "H1+H3 (TO+CLUSTER)",
     "expression": f"trade_when(less({GATE1}), reverse(rank(ts_backfill({RATIO_F}, 2))), 0)",
     "optimize_reason": (
        "【新鲜门收紧 x bf2 · 门x回填因子设计第四角】门强度 (dflc<1 vs <2) 与回填 "
        "(bf0/2/3) 的 2xK 因子设计中, 本槽 = (门1, bf2) 角; 与槽1 (门2,bf2) 构成"
        "门强度配对 (唯一变量 = 门), 与槽7 (门2,bf0) 构成回填配对. 三重意义: ①bf2 降 "
        "TO (QPYxb9vp 无门实读 TO 84.1%) 叠加更纯的新鲜事件门 (dflc<1) —— 门不是 TO "
        "杠杆 (w10i), 故预期 TO 仍 ~84%, 但事件当日纯度升 -> CLUSTER 族顶 1.56 "
        "(3qjKl3Ag, dflc<1 双门版) 的结构方向; ②稀疏化 (门1 有仓日更少) 与 bf2 持续化 "
        "(填充 2 日) 存在直接张力: 若组合后 TO 反升, 说明门的稀疏化被 bf 的填充抵消, "
        "两个杠杆互斥; ③零新增字段/算子风险 (全为已验证构件). 判据: CLUSTER>=1.56 = "
        "追平族顶; TO<=70% = 门xbf 出现未知压缩交互 (高价值读数); Sh>=1.5 = 双杠杆兼容.")},
    {"id": 4, "type": "EXPDECAY20_F09",
     "lesion": "H1 HIGH_TURNOVER",
     "expression": f"trade_when(less({GATE2}), reverse(rank(ts_decay_exp_window({RATIO_F}, 20, factor=0.9))), 0)",
     "optimize_reason": (
        "【指数衰减平滑 · 用户点题① · 持续性杠杆】官方公式 (GET /operators 实读): "
        "TS_Decay_Exp_Window(x,d,factor=f)=Σx[t-k]f^k/Σf^k, 0<f<1, f 越大衰减越慢, "
        "官方明言 'may help reduce turnover'; ESS=(Σw)²/Σw²: f=0.9,d=20 ≈ 15 天. "
        "经济学 (Hong-Stein 逐步扩散/PEAD): 新闻冲击的价格效应按做市商库存平复速度"
        "多日衰减, 未平复的累积位移度量持续数日的流动性压力; 指数几何权重是'压力"
        "半衰期'的自然参数化, 比等权 ts_mean (平坦权重混音多日事件, w10i: Sh 0.12) "
        "和线性 ts_decay_linear (长尾但首日权重过低, d=60: Sh 1.11@TO 78.5%; d=20: "
        "1.14@79.7%) 更贴近冲击衰减形状. 方向处理 (红队 M2-1 必修): 必须保留显式 "
        "reverse —— rank(-x)=1-rank(x) 与 reverse 复合虽差常数 1, 但该常数在 "
        "trade_when 门控内被门 flag 调制成 g, 中性化后残留 g-mean(g) (std≈0.497) "
        "一阶大于信号 (std≈0.29), '省 reverse'恒等式在门控基座上失效 (无门时成立). "
        "判据: TO<=85% 且 Sh>=1.35 = 指数族最优 (介于线性 1.11 与母本 1.59 之间); "
        "TO>=100% = 权重剖面无效, 与线性同命.")},
    {"id": 5, "type": "WINSORIZE_BF2",
     "lesion": "H1+H3 (TO+CLUSTER)",
     "expression": f"trade_when(less({GATE2}), reverse(rank(ts_backfill(divide(winsorize(subtract({EOC}, {TON}), std=2), add(vec_count({VHEX}), 1)), 2))), 0)",
     "optimize_reason": (
        "【分子级 winsorize x bf2 · 簇去尾 x 降 TO 双杠杆】winsorize 保序 -> 嵌 rank "
        "内是恒等无操作 (analyst10 实证), 故嵌在分子 CTO 上: divide(winsorize(CTO,std=2), "
        "count+1) 借变分母除法重排横截面次序才非无操作. 官方: winsorize 是横截面算子, "
        "std=2/3/4/5 削 ~4.5%/0.27%/0.01%/0.0001% 极值; 平台实证 (smoke test 报错): "
        "winsorize 只接受 1 个位置输入, std 必须命名参数 (winsorize(x, std=2)) —— 位置"
        "传参会整批 ERROR+CANCELLED 连坐. CLUSTER_TEST = 簇层面 Sharpe "
        "(簇内信号等权合成对簇收益的预测力; 新闻事件驱动是其经典反例, 320/320 全警告): "
        "CTO 极值 (闪崩/针状报价) 是个股特异事件的最大来源, 簇平均压不掉单只极端位移,"
        " 削尾直接抬簇合成信号信噪比 —— 社区'提升系统性十法'之一. 再叠 bf2 降 TO. "
        "判据: CLUSTER>=1.55 (较母本 1.54 升) 且 Sh>=1.35 = 去尾路线成立; "
        "CLUSTER<=1.50 = winsorize 在本基座无效 (与既往有害记录一致), 簇路线收窄.")},
    {"id": 6, "type": "ANOMALY_D3",
     "lesion": "H3 CLUSTER_TEST",
     "expression": f"trade_when(less({GATE2}), reverse(rank(subtract({RATIO_F}, ts_mean({RATIO_F}, 20)))), 0)",
     "optimize_reason": (
        "【异常冲击分离 · 簇同向性主攻】今日单位事件位移减去其近 20 日均值 = 异常"
        "成分. 机制: 系统性坏消息日 = 全簇成员异常位移同向为负 -> 簇等权合成信号强; "
        "常态日 = 异常成分近似 idiosyncratic 噪声 -> 簇均值≈0, 不在簇层乱下注. 这正面"
        "攻击 CLUSTER_TEST 的'系统性 vs 特异'判据 —— 不是制造同向而是筛掉非同向的"
        "噪声赌注. 与槽5 (winsorize 去尾) 是簇路线的两条正交路径 (尾部压制 vs 基线"
        "剔除); 族顶 CLUSTER 1.56 (3qjKl3Ag) 提示 +0.02 即可破墙. ops=16 恰好卡平台"
        "上限 (RATIO_F 出现两次: 外层 + ts_mean 内); 全为已知老算子, 无未知算子连坐"
        "风险. 判据: CLUSTER>=1.58 = 警告墙破口 (全战役 339 行首次); Sh>=1.5 = 异常"
        "分离不杀整体; 双降 = 该线关闭.")},
    {"id": 7, "type": "DUAL_NATIVE",
     "lesion": "H2 LOW_FITNESS (基座标定)",
     "expression": f"reverse(rank({DUAL_F}))",
     "optimize_reason": (
        "【双压力分子原生标定 · Fit 攻击基座】分子 (EOC-TON)+(EOC-VWAP) = 收盘价相对"
        "'新闻时刻'与'当日成交均价'两个锚点的偏离之和, 以 VWAP 归一化. 经济学: 单锚点"
        "位移含锚点噪声 (新闻时点报价的微观结构误差), 双锚点是对同一'全天价格轨迹崩塌'"
        "的两次测量, 平均后信噪比更高; VWAP 归一化使幅度跨股可比且自带成交量认证. "
        "本槽为无门无 bf 原生版 (3 字段, ops=6): b10/b11 的全部双压力读数都带 bf2/bf3, "
        "原生版缺失 —— 与 WjLZbE7N (bf2 无门: Sh 1.27/Ret 7.68%/TO 86.1%) 配对可精确"
        "分离'bf 对双压力分子'的处理效应 (若原生版 Sh 显著高于 1.27, 说明 bf 在双压力上"
        "的损伤大于单压力; 反之 bf 对双压力是优化). 战略价值: 若原生版 Ret>=8% 且 "
        "Sh>=1.5, 它就是 Fit 攻击的新基座 (Fit=Sh*sqrt(Ret/TO), Ret 8% 时 TO<=20% 即可"
        "过 Fit) —— W12 的所有压 TO 处方都应换到该基座上重测. 判据: Sh>=1.5 且 Ret>=8% "
        "= 优质基座确认; Sh<=1.3 = 双压力上限已被 bf2 版穷尽, 弃该分子.")},
    {"id": 8, "type": "POOLED_NETRATIO",
     "lesion": "H1+H2 (TO+Fit)",
     "expression": f"trade_when(less({GATE2}), reverse(rank(divide(ts_sum({NET}, 20), ts_sum({NETABS}, 20)))), 0)",
     "optimize_reason": (
        "【净压力比率池化 · 输入侧重参数化攻 TO-Sh 前沿】过去 20 日累积净位移 / 累积"
        "总位移 (gross) ∈ [-1,1]: 单事件名 = ±1 (与种子行为一致), 多事件交替名 ≈0 "
        "(方向不一致不赌), 同向多名趋 ±1 (保留方向与一致性). 经济学 (做市商库存平复, "
        "Ho-Stoll/Brunnermeier-Pedersen): 累积未平复压力是可持续数日的慢变量, 其"
        "池化估计把日频特异噪声平均掉 —— 输入侧降频改变估计量信噪比 (信号+估计量同变),"
        " 区别于输出侧平滑 (ts_mean/ts_rank 壳: 只衰减信号, 估计量不变 -> Sh 全塌). "
        "族内先证: omoX8edl (同类池化 N=60) TO 56.7% / Ret 7.11% / Sh 0.57 —— 慢估计"
        "量物理上可达低 TO+高 Ret, 唯一缺口是 IC; 且对稀疏事件完全免疫 (count=1 不"
        "爆炸, 无低覆盖重尾问题). 与 w10a 失败池化 (N=60 远超反转半衰期 + 重尾分母) "
        "的区别: 本槽 N=20 对齐半衰期 + 比率量纲有界. 判据: TO<=45% 且 Sh>=1.2 = "
        "池化方向成立, 触发 N 扫参 (10/20/40); TO<=22% 且 Sh>=1.45 = Fit 双门同过在望.")},
]

# W2 (MARKET) 槽8 = 母本对照 (指纹含 neutralization, MARKET 下不重复)
SEED_CONTROL = {"id": 8, "type": "SEED_CONTROL_MARKET", "lesion": "H4 Margin",
                "expression": f"trade_when(less({GATE2}), reverse(rank({RATIO_F})), 0)",
                "optimize_reason": (
                   "【母本对照 @MARKET · 用户点题③】mLYNEWjW 原式在 MARKET 中性化下的"
                   "读数. '中性化下沉'假说: INDUSTRY->MARKET 减少风险剔除, 保留更多原始"
                   "信号方向与幅度 -> Ret/Margin 上升; 代价通常是 Sh 下降 (news21 三点谱"
                   "实证 NONE/MARKET/STATISTICAL 的 Sh-Ret 互斥). 本槽给出该交换在"
                   "CW 已解基座上的精确汇率: 若 Sh 保持 >=1.58 且 Ret 升 >=15%, MARKET "
                   "是免费 Margin 改进; 若 Sh 跌破 1.58, 互斥律在第八个结构上再次应验.")}

FIELDS_FILE = os.path.join(ROOT, "quant_framework", "campaigns", "USA_news_news12_gate1", "news12_fields_full.json")
with open(FIELDS_FILE, encoding="utf-8") as f:
    raw = json.load(f)
fields = raw["results"] if isinstance(raw, dict) and "results" in raw else raw
known = [x["id"] for x in fields]
known_set = set(known)

corrector = ASTSandboxCorrector()
conn = sqlite3.connect(corrector.db_path)
cur = conn.cursor()

# ---- 新算子存在性 (已由 /operators API 实读确认) ----
NEW_OPS = {"ts_decay_exp_window": "ts_decay_exp_window(x, d, factor=f) = Σx[t-k]f^k/Σf^k; 0<f<1; 官方: may help reduce turnover",
           "winsorize": "winsorize(x, std=4) 横截面削极值; std=2/3/4/5 削 ~4.5%/0.27%/0.01%/0.0001%",
           "ts_backfill": "ts_backfill(x, d) 用过去 d 日内最近非空值填充"}

# ---- 本地全历史精确匹配扫描 (M4 修复: v2 只做关键词计数, 漏抓字节级重复) ----
print("== 本地全历史精确匹配扫描 (M4) ==", flush=True)
import glob
hist = {}   # norm_expr -> (alpha_id, batch)
for fp in sorted(glob.glob(os.path.join(BASE, "batch_*_result.json"))):
    try:
        d = json.load(open(fp, encoding="utf-8"))
    except Exception:
        continue
    for r in d.get("alpha_results", []):
        code = r.get("code")
        if not code:
            continue
        norm = corrector.correct_expression(code)
        hist[norm] = (r.get("alpha_id"), os.path.basename(fp))
print(f"  历史表达式装载 {len(hist)} 条 (归一化后)", flush=True)

# ---- 表达式级 novelty 扫描 (指纹库之外兜底) ----
print("\n== 表达式级 novelty 扫描 (DB) ==", flush=True)
scan_specs = [
    ("ts_decay_exp_window 使用史", ["ts_decay_exp_window"]),
    ("winsorize 使用史", ["winsorize"]),
    ("母本 RATIO+ts_decay 共现", ["ts_decay_exp_window", "high_price_excursion_stddev"]),
    ("母本 RATIO+winsorize 共现", ["winsorize", "high_price_excursion_stddev"]),
]
for label, keys in scan_specs:
    conds = " AND ".join(["expression LIKE ?"] * len(keys))
    params = [f"%{k}%" for k in keys]
    cur.execute(f"SELECT expression FROM alpha_fingerprints WHERE {conds}", params)
    rows = cur.fetchall()
    print(f"  [{label}] DB 命中 {len(rows)} 条", flush=True)
    for r in rows[:3]:
        print(f"    - {r[0][:110]}", flush=True)

ops_whitelist = {"reverse", "divide", "add", "subtract", "multiply", "rank", "group_rank", "group_zscore",
                 "group_mean", "ts_backfill", "ts_mean", "ts_sum", "ts_std_dev", "ts_rank", "ts_zscore",
                 "ts_delta", "ts_decay_linear", "ts_decay_exp_window", "ts_median", "trade_when",
                 "greater", "less", "vec_avg", "vec_sum", "vec_count", "vec_max", "vec_min",
                 "vec_stddev", "days_from_last_change", "winsorize", "abs", "power", "sqrt",
                 "industry", "subindustry", "sector", "market", "factor", "std"}

print("\n== 逐槽预检 (W1: INDUSTRY/d6) ==", flush=True)
n_dup = 0
for it in SLOTS + [SEED_CONTROL]:
    fixed = corrector.correct_expression(it["expression"])
    it["expression"] = fixed
    # W1/W3 指纹 (INDUSTRY) — decay 不在指纹内
    h1 = corrector.compute_fingerprint(fixed, REGION, UNIVERSE, DELAY, "INDUSTRY")
    cur.execute("SELECT expression FROM alpha_fingerprints WHERE md5_hash = ?", (h1,))
    row1 = cur.fetchone()
    # W2 指纹 (MARKET) — 仅母本对照槽需要
    h2 = corrector.compute_fingerprint(fixed, REGION, UNIVERSE, DELAY, "MARKET")
    cur.execute("SELECT expression FROM alpha_fingerprints WHERE md5_hash = ?", (h2,))
    row2 = cur.fetchone()
    audit = DimensionAuditor.audit_expression(fixed, known, category=CATEGORY)
    tokens = set(audit["tokens_found"])
    used = tokens & known_set
    unknown = {t for t in tokens if t not in known_set and t not in ops_whitelist and not t.isdigit()}
    # M4: 本地全历史精确匹配 (SEED_CONTROL 豁免: 母本对照的用途就是同表达式换 neutralization 重跑,
    # 指纹含 neutralization => @MARKET 与 @INDUSTRY 不同, 合法)
    exact = None if it["type"].startswith("SEED_CONTROL") else hist.get(fixed)
    dup1 = "DUP@IND" if row1 else ""
    dup2 = "DUP@MKT" if row2 else ""
    exact_tag = f"EXACT_DUP:{exact[0]}" if exact else ""
    print(f"slot{it['id']} [{it['type']}] ops={audit['operator_count']} fields={len(used)} "
          f"len={len(it['expression'])} valid={audit['is_valid']} {dup1}{dup2} {exact_tag} unknown={unknown or '-'}", flush=True)
    print(f"     {it['expression']}", flush=True)
    if unknown:
        raise SystemExit(f"slot{it['id']} 未知标识符: {unknown}")
    if not audit["is_valid"]:
        raise SystemExit(f"slot{it['id']} 审计失败: {audit['issues']}")
    if not (2 <= len(used) <= 3):
        raise SystemExit(f"slot{it['id']} 字段数 {len(used)} 越界 (需 2-3)")
    if audit["operator_count"] > 16:
        raise SystemExit(f"slot{it['id']} ops {audit['operator_count']} > 16 (平台硬限)")
    if len(it["expression"]) > 857:
        raise SystemExit(f"slot{it['id']} 超长")
    if len(it["optimize_reason"]) < 120:
        raise SystemExit(f"slot{it['id']} optimize_reason 过短")
    if exact:
        raise SystemExit(f"slot{it['id']} 本地历史精确匹配重复: {exact}")
    if row1:
        n_dup += 1
print(f"\nW1/W3 查重完成: {n_dup}/8 历史重复 (<=2 合法; phase 系脚本直提不写指纹, 预期 0)", flush=True)

# ---- 恒等变换验证 ----
print("\n== 恒等变换数值验证 (线性 + 平均秩) ==", flush=True)
import random
random.seed(7)
xs = [random.uniform(-3, 3) for _ in range(500)]
def rank_asc(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    for pos, i in enumerate(order):
        r[i] = pos / (len(xs) - 1)
    return r
r_pos = rank_asc(xs)
r_neg = rank_asc([-x for x in xs])
maxdiff = max(abs(a - (1 - b)) for a, b in zip(r_pos, r_neg))
print(f"  max|rank(x) - (1-rank(-x))| = {maxdiff:.2e} (应 ~0)", flush=True)
assert maxdiff < 1e-12
# 线性算子恒等: decay(-x) = -decay(x)
def exp_decay(xs, d, f):
    w = [f ** k for k in range(d)]
    sw = sum(w)
    out = []
    for t in range(len(xs)):
        acc = sum(xs[t - k] * w[k] for k in range(min(d, t + 1)))
        out.append(acc / sw)
    return out
d1 = exp_decay(xs, 20, 0.9)
d2 = exp_decay([-x for x in xs], 20, 0.9)
md2 = max(abs(a - (-b)) for a, b in zip(d1, d2))
print(f"  max|decay(x) + decay(-x)| = {md2:.2e} (线性恒等, 应 ~0)", flush=True)
assert md2 < 1e-12

# ---- 母本与处方差异矩阵 ----
print("\n== 母本 vs 处方 差异矩阵 ==", flush=True)
seed_expr = f"trade_when(less({GATE2}), reverse(rank({RATIO_F})), 0)"
for it in SLOTS:
    diff = []
    if "ts_backfill" in it["expression"]:
        bf_n = "3" if f"add(vec_count(high_price_excursion_stddev), 1)), 3)" in it["expression"] else "2"
        diff.append(f"+短回填({bf_n})")
    if "winsorize" in it["expression"]:
        diff.append("+分子级winsorize(std=2)")
    if "ts_decay_exp_window" in it["expression"]:
        diff.append("+指数衰减(f=0.9)")
    if "ts_mean" in it["expression"]:
        diff.append("+异常分离(-ts_mean20)")
    if "ts_sum" in it["expression"]:
        diff.append("+净压力池化(20)")
    if "news_eod_vwap" in it["expression"]:
        diff.append("+双压力分子(VWAP锚)")
    if f"less({GATE1})" in it["expression"]:
        diff.append("门 dflc<2-><1")
    print(f"  slot{it['id']} [{it['type']}] 病灶={it['lesion']}: {', '.join(diff) or '??'}", flush=True)

conn.close()
print("\n预检全部通过 (v3): 8 条处方可发射 (W1 INDUSTRY/d6; W2 MARKET/d6 槽8=母本对照; W3 INDUSTRY/d20)", flush=True)
