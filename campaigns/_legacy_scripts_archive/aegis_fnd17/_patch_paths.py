# -*- coding: utf-8 -*-
"""一次性脚本：把战役脚本里的硬编码 .agents 路径改为 _paths 解析器。"""
import io

BASE = r"D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents\campaigns\aegis_fnd17"
OLD = r'D:\python\Lib\site-packages\cnhkmcp\untracked\APP\.agents'

EDITS = {
    "stage3_preflight.py": [
        ('ROOT = r"' + OLD + '"\nsys.path.insert(0, ROOT)',
         'import _paths\nROOT = _paths.ROOT\nsys.path.insert(0, ROOT)'),
    ],
    "stage3_assemble.py": [
        ('sys.path.insert(0, HERE)\nsys.path.insert(0, r"' + OLD + '")',
         'import _paths\nsys.path.insert(0, HERE)\nsys.path.insert(0, _paths.ROOT)'),
    ],
    "stage3_run_batch.py": [
        ('ROOT = r"' + OLD + '"\nCAMPAIGN = os.path.join(ROOT, "aegis_coldstart", "campaign_fnd17")\n'
         'sys.path.insert(0, r"D:\\brain-mcp")\nsys.path.insert(0, ROOT)',
         'import _paths\nROOT = _paths.ROOT\nCAMPAIGN = _paths.CAMPAIGN\n'
         'sys.path.insert(0, r"D:\\brain-mcp")\nsys.path.insert(0, ROOT)'),
    ],
    "stage4_refine.py": [
        ('sys.path.insert(0, HERE)\nsys.path.insert(0, r"' + OLD + '")',
         'import _paths\nsys.path.insert(0, HERE)\nsys.path.insert(0, _paths.ROOT)'),
    ],
    "stage5_audit.py": [
        ('ROOT = r"' + OLD + '"\nCAMPAIGN = os.path.join(ROOT, "aegis_coldstart", "campaign_fnd17")\n'
         'sys.path.insert(0, r"D:\\brain-mcp")\nsys.path.insert(0, ROOT)',
         'import _paths\nROOT = _paths.ROOT\nCAMPAIGN = _paths.CAMPAIGN\n'
         'sys.path.insert(0, r"D:\\brain-mcp")\nsys.path.insert(0, ROOT)'),
    ],
}

for fn, subs in EDITS.items():
    p = BASE + "\\" + fn
    s = io.open(p, encoding="utf-8").read()
    for a, b in subs:
        if a not in s:
            print("!! MISS", fn, repr(a[:70]))
            continue
        s = s.replace(a, b, 1)
    io.open(p, "w", encoding="utf-8").write(s)
    print("ok", fn)
