import json
d=json.load(open('fnd17_field_dossier.json',encoding='utf-8'))
out=['type='+str(type(d))]
if isinstance(d,dict):
    out.append('keys='+str(list(d.keys()))[:800])
    for k in list(d.keys())[:2]:
        out.append(k+' -> '+json.dumps(d[k],ensure_ascii=False)[:1500])
elif isinstance(d,list):
    out.append('len='+str(len(d)))
    out.append(json.dumps(d[0],ensure_ascii=False)[:2000])
open('_tmp_doss.txt','w',encoding='utf-8').write('\n'.join(out))
print('ok')
