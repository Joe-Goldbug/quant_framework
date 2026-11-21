import json
d=json.load(open('agent_field_ref.json',encoding='utf-8'))
out=[]
for k in sorted(d):
    if 'eps' in k.lower() and k.startswith('fnd17_'):
        out.append('%-24s ac=%-3s ax=%-28s %s'%(k,d[k].get('ac'),d[k].get('ax'),d[k].get('d','')[:90]))
open('_tmp_eps.txt','w',encoding='utf-8').write('\n'.join(out))
print('ok')
