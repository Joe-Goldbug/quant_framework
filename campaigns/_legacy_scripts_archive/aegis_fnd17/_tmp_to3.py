import json,collections
d=json.load(open('fnd17_history_mined.json',encoding='utf-8'))
out=[]
cnt=collections.Counter()
for a in d:
    c=a.get('code') or ''
    if 'fnd17' in c:
        cnt[(a.get('region'),a.get('universe'))]+=1
out.append('regions with fnd17 code: '+json.dumps({str(k):v for k,v in cnt.most_common()},ensure_ascii=False))
# turnover for USA any universe
tos=[]
for a in d:
    c=a.get('code') or ''
    if 'fnd17' in c and a.get('region')=='USA' and a.get('turnover') is not None:
        tos.append((a.get('turnover'),a.get('universe'),a.get('code','')[:120]))
tos.sort()
out.append('USA fnd17 with turnover n=%d'%len(tos))
for t in tos[:5]+tos[-15:]:
    out.append('  TO=%.4f %s %s'%t)
open('_tmp_to3.txt','w',encoding='utf-8').write('\n'.join(out))
print('ok')
