import json,collections
d=json.load(open('fnd17_history_mined.json',encoding='utf-8'))
out=[]
tos=[]
lt_vals=collections.Counter()
for a in d:
    if a.get('region')!='USA' or a.get('universe')!='TOP1000': continue
    if 'fnd17_' not in (a.get('code') or ''): continue
    to=a.get('turnover'); tos.append(to)
    cv=a.get('checks_vals') or {}
    if 'LOW_TURNOVER' in cv: lt_vals[(cv.get('LOW_TURNOVER'),cv.get('HIGH_TURNOVER'))]+=1
tos=[t for t in tos if t is not None]
tos.sort()
out.append('USA/TOP1000 fnd17 alphas n=%d turnover quantiles:'%len(tos))
if tos:
    for q in [0,0.1,0.25,0.5,0.75,0.9,1.0]:
        out.append('  p%-4s %.4f'%(int(q*100), tos[min(len(tos)-1,int(q*(len(tos)-1)))]))
out.append('LOW/HIGH_TURNOVER check value pairs (top 15):')
for k,v in lt_vals.most_common(15):
    out.append('  %s  x%d'%(k,v))
open('_tmp_to2.txt','w',encoding='utf-8').write('\n'.join(out))
print('ok')
