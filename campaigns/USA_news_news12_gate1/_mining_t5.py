#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T5: 算子使用史统计 + novelty 空间"""
import json, os, re, collections

BASE = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\quant_framework\campaigns\USA_news_news12_gate1"
with open(os.path.join(BASE, '_mining_all_rows.json'), 'r', encoding='utf-8') as f:
    data = json.load(f)
rows = [r for r in data['rows'] if r['sharpe'] is not None]

# 提取所有调用名：name(  —— 字段名是叶子不带括号，所以 name( 必为算子/函数
call_re = re.compile(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(')
op_counter = collections.Counter()
op_rows = collections.defaultdict(list)
for r in rows:
    names = set(m.group(1) for m in call_re.finditer(r['code']))
    for n in names:
        op_counter[n] += 1
        op_rows[n].append(r['alpha_id'])

print('===== T5: 算子使用统计（n=%d 行，按行去重计数）=====' % len(rows))
for name, cnt in op_counter.most_common():
    print(f'  {name:32s} {cnt}')

# 白名单：BRAIN 常用安全算子（用户点名 + 标准集，剔除框架 FORBIDDEN: signed_power/hump/group_neutralize）
WHITELIST = [
    # 横截面
    'rank', 'reverse', 'zscore', 'normalize', 'quantile', 'scale', 'winsorize', 'truncate',
    # 时间序列
    'ts_mean', 'ts_median', 'ts_std_dev', 'ts_sum', 'ts_product', 'ts_rank', 'ts_min', 'ts_max',
    'ts_arg_min', 'ts_arg_max', 'ts_delay', 'ts_delta', 'ts_decay_linear', 'ts_decay_exp_window',
    'ts_backfill', 'ts_zscore', 'ts_scale', 'ts_av_diff', 'ts_returns', 'ts_covariance',
    'ts_correlation', 'ts_regression', 'ts_theilsen', 'ts_kurtosis', 'ts_skewness',
    'ts_moment', 'ts_entropy', 'ts_percentage', 'ts_step', 'ts_count_nans', 'ts_ir',
    'ts_min_max_diff', 'ts_max_diff', 'ts_std_dev_diff',
    # 分组
    'group_rank', 'group_zscore', 'group_sum', 'group_mean', 'group_max', 'group_min',
    'group_count', 'group_std_dev', 'group_backfill', 'group_neutralize_xs',
    # 条件/逻辑
    'trade_when', 'if_else', 'filter', 'is_nan', 'less', 'greater', 'or', 'and', 'not',
    # 算术
    'add', 'subtract', 'multiply', 'divide', 'power', 'log', 'sqrt', 'sign', 'abs',
    'exp', 'sigmoid', 'tanh', 'inverse', 'floor', 'ceil', 'round',
    # 向量
    'vec_avg', 'vec_sum', 'vec_count', 'vec_max', 'vec_min', 'vec_ir', 'vec_range',
    'vec_norm', 'vec_choose', 'vec_stddev', 'vec_prod', 'vec_skewness', 'vec_kurtosis',
    # 事件/其他
    'days_from_last_change', 'hump_decay', 'ts_backfill_wls',
]
FORBIDDEN = {'signed_power', 'hump', 'group_neutralize'}

used = set(op_counter.keys())
print('\n--- 白名单算子在本次战役的使用情况 ---')
never = []
for op in WHITELIST:
    if op in FORBIDDEN:
        continue
    cnt = op_counter.get(op, 0)
    if cnt == 0:
        never.append(op)
print('从未使用的白名单算子（novelty 空间，%d 个）:' % len(never))
for op in never:
    print(f'  {op}')

print('\n--- 出现过但不在我列的标准白名单内的名字（检查是否有意外算子） ---')
extra = sorted(used - set(WHITELIST))
for n in extra:
    print(f'  {n}: {op_counter[n]} 行')

print('\n--- FORBIDDEN 算子检查 ---')
for f_ in FORBIDDEN:
    print(f'  {f_}: {op_counter.get(f_,0)} 行 {"!!!" if op_counter.get(f_,0) else "(clean)"}')
