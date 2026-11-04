import json,re
d=json.load(open('fnd17_history_mined.json',encoding='utf-8'))
out=['type='+str(type(d))]
if isinstance(d,dict):
    out.append('keys='+str(list(d.keys()))[:600])
    k=list(d.keys())[0]
    v=d[k]
    out.append('sample '+k+' -> '+json.dumps(v,ensure_ascii=False)[:1200])
elif isinstance(d,list):
    out.append('len='+str(len(d)))
    out.append('item0 keys='+str(list(d[0].keys())) if isinstance(d[0],dict) else '')
    out.append(json.dumps(d[0],ensure_ascii=False)[:1500])
open('_tmp_to.txt','w',encoding='utf-8').write('\n'.join(out))
print('ok')
