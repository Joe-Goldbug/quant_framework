import json,collections
d=json.load(open('fnd17_history_mined.json',encoding='utf-8'))
out=[]
tos=[]
for a in d:
    if a.get('region')=='USA' and a.get('universe')=='TOP1000' and a.get('turnover') is not None:
        tos.append(a.get('turnover'))
tos.sort()
out.append('USA/TOP1000 all-dataset alphas with turnover n=%d'%len(tos))
if tos:
    for q in [0,0.05,0.1,0.25,0.5,0.75,0.9,0.95,1.0]:
        out.append('  p%-4s %.4f'%(int(q*100), tos[min(len(tos)-1,int(q*(len(tos)-1)))]))
out.append('')
out.append('fnd17-based USA/TOP1000 alphas (from fnd17_history_v4):')
h=json.load(open('fnd17_history_v4.json',encoding='utf-8'))
for a in h:
    if a.get('region')=='USA' and a.get('universe')=='TOP1000':
        out.append('  TO=%s  Sh=%s  %s'%(a.get('turnover'),a.get('sharpe'),(a.get('code') or '')[:110]))
open('_tmp_to4.txt','w',encoding='utf-8').write('\n'.join(out))
print('ok')
