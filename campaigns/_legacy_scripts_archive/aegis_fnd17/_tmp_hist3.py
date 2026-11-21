import json,re
d=json.load(open('fnd17_history_v4.json',encoding='utf-8'))
out=[]
fields=['aniacnorm','aninorm','aniexclxor','aniacinclx','aniac','fcfmtt','fcfq','fcf1a','rhsfcfmtt','rhsfcfq','cainq','inq','atmtt','atotce','qtotce','ata']
for a in d:
    code=a.get('code') or ''
    hit=[f for f in fields if f in code]
    if hit:
        out.append('%-12s %-6s %-10s Sh=%s Fit=%s TO=%s Ret=%s hit=%s' % (
            a.get('id'), a.get('region'), a.get('universe'), a.get('sharpe'), a.get('fitness'),
            a.get('turnover'), a.get('returns'), ','.join(hit)))
        out.append('    '+code[:300])
open('_tmp_hist3.txt','w',encoding='utf-8').write('\n'.join(out))
print('ok')
