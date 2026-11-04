import json, re, collections

def walk(o, path=""):
    if isinstance(o, dict):
        for k,v in o.items():
            yield from walk(v, path+"/"+str(k))
    elif isinstance(o, list):
        for i,v in enumerate(o):
            yield from walk(v, path+"/"+str(i))
    else:
        yield path, o

for f in ['batch_S1.json','batch_S2.json','batch_S3.json']:
    try:
        d=json.load(open(f,encoding='utf-8'))
    except Exception as e:
        print(f,'ERR',e); continue
    exprs=[]
    for p,v in walk(d):
        if isinstance(v,str) and ('group_rank' in v or 'divide(' in v or 'power(' in v) and len(v)>40:
            exprs.append((p,v))
    print('='*70)
    print(f, 'expr-like strings:', len(exprs))
    for p,v in exprs[:60]:
        print(' ',p.split('/')[-2:], '=>', v[:220])
