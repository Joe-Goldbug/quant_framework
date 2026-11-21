import json
d=json.load(open('fnd17_history_v4.json',encoding='utf-8'))
out=[]
for a in d:
    code=a.get('code') or ''
    if 'power(' in code or 'group_rank' in code and 'sector' in code:
        out.append('%-12s %-5s %-9s Sh=%s Fit=%s TO=%s L=%s S=%s' % (
            a.get('id'), a.get('region'), a.get('universe'), a.get('sharpe'), a.get('fitness'),
            a.get('turnover'), a.get('longCount'), a.get('shortCount')))
        out.append('    '+code[:400])
open('_tmp_hist4.txt','w',encoding='utf-8').write('\n'.join(out))
print('ok')
