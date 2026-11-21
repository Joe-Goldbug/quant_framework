import json
d=json.load(open('agent_field_ref.json',encoding='utf-8'))
out=[]
aq=[k for k,v in d.items() if 'accrual_quality' in (v.get('ax') or [])]
out.append('ref fields tagged accrual_quality ('+str(len(aq))+'):')
for k in sorted(aq):
    out.append('  '+k+' ac='+str(d[k].get('ac')))
out.append('')
out.append('EPS-like / ebt / cash-ish fields in ref (for cross-check):')
for k in sorted(d):
    kl=k.lower()
    if any(s in kl for s in ['eps','ebit','ocf','cashflow','fcf']):
        out.append('  '+k+' ac='+str(d[k].get('ac'))+' ax='+str(d[k].get('ax'))+' :: '+d[k].get('d','')[:80])
open('_tmp_ax.txt','w',encoding='utf-8').write('\n'.join(out))
print('ok')
