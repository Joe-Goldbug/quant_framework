import json
d=json.load(open('fnd17_history_v4.json',encoding='utf-8'))
out=[]
out.append('type: '+str(type(d)))
if isinstance(d,list):
    out.append('len '+str(len(d)))
    out.append('first item keys: '+str(list(d[0].keys())) if isinstance(d[0],dict) else str(d[0])[:500])
    out.append(json.dumps(d[:3],ensure_ascii=False,indent=1)[:4000])
else:
    out.append('keys: '+str(list(d.keys()))[:500])
open('_tmp_hist2.txt','w',encoding='utf-8').write('\n'.join(out))
print('ok')
