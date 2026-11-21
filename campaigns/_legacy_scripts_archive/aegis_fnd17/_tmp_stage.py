import json
d=json.load(open('fnd17_history_v4.json',encoding='utf-8'))
out=[]
for a in d:
    if a.get('region')=='USA' and a.get('universe')=='TOP1000':
        out.append('%-12s stage=%-6s status=%-9s Sh=%-6s Fit=%-5s self=%-6s prod=%-6s sub=%s' % (
            a.get('id'), a.get('stage'), a.get('status'), a.get('sharpe'), a.get('fitness'),
            a.get('self_corr'), a.get('prod_corr'), a.get('dateSubmitted')))
        out.append('    '+ (a.get('code') or '')[:220])
open('_tmp_stage.txt','w',encoding='utf-8').write('\n'.join(out))
print('ok')
