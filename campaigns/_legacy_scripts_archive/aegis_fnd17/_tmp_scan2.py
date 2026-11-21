import json

def walk(o, path=""):
    if isinstance(o, dict):
        for k,v in o.items():
            yield from walk(v, path+"/"+str(k))
    elif isinstance(o, list):
        for i,v in enumerate(o):
            yield from walk(v, path+"/"+str(i))
    else:
        yield path, o

out=[]
for f in ['batch_S1.json','batch_S2.json','batch_S3.json','batch_S3_CAMPAIGN.json']:
    try:
        d=json.load(open(f,encoding='utf-8'))
    except Exception as e:
        out.append(f+' ERR '+str(e)); continue
    out.append('='*70); out.append(f)
    for p,v in walk(d):
        if p.endswith('/expression') and isinstance(v,str):
            out.append(v)
open('_tmp_exprs.txt','w',encoding='utf-8').write('\n'.join(out))
print('ok')
