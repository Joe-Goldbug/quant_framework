# -*- coding: utf-8 -*-
"""修复 phase13_wave11c_pooled_ic.py 中 optimize_reason 内部的 ASCII 引号.

问题: optimize_reason 的中文引号被存为 ASCII '"', 与 Python 字符串定界符冲突,
      导致 SyntaxError. 修复: 仅对"以 '"' 开头的含中文文本行", 保留首尾定界符,
      把内部引号交替替换为中文「」.
"""
import re
import sys

FP = 'phase13_wave11c_pooled_ic.py'
lines = open(FP, encoding='utf-8').read().split('\n')

CJK = lambda s: any('\u4e00' <= c <= '\u9fff' for c in s)
fixed = 0
for i, line in enumerate(lines):
    s = line.strip()
    if not s.startswith('"'):
        continue
    if s.startswith('"""'):
        continue
    if '":' in s[:20]:          # 键值对行, 非 optimize_reason 续行
        continue
    if not CJK(s):
        continue
    first, last = line.find('"'), line.rfind('"')
    if first == last:
        continue
    inner = line[first + 1:last]
    if '"' not in inner:
        continue
    out, open_q = [], True
    for c in inner:
        if c == '"':
            out.append('\u300c' if open_q else '\u300d')
            open_q = not open_q
        else:
            out.append(c)
    lines[i] = line[:first + 1] + ''.join(out) + line[last:]
    fixed += 1
    print('L%d: %s' % (i + 1, lines[i].strip()[:90]))

open(FP, 'w', encoding='utf-8').write('\n'.join(lines))
print('\nfixed lines =', fixed)

# 校验
import ast
try:
    ast.parse(open(FP, encoding='utf-8').read())
    print('SYNTAX OK')
except SyntaxError as e:
    print('STILL BROKEN: L%d %s' % (e.lineno, e.msg))
    sys.exit(1)
