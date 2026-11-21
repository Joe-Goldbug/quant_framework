import json,re
d=json.load(open('fnd17_history_v4.json',encoding='utf-8'))
out=[]
def keys(o,p='',depth=0):
    if depth>2: return
    if isinstance(o,dict):
        for k in list(o.keys())[:12]:
            out.append(p+'/'+str(k))
            keys(o[k],p+'/'+str(k),depth+1)
    elif isinstance(o,list):
        out.append(p+' list len='+str(len(o)))
keys(d)
open('_tmp_hist.txt','w',encoding='utf-8').write('\n'.join(out[:80]))
print('ok')
