import json
out=[]
for f in ['slices/slice_S4_CASH.json','slices/slice_Q5Q8.json']:
    try:
        d=json.load(open(f,encoding='utf-8'))
    except Exception as e:
        out.append(f+' ERR '+str(e)); continue
    out.append('='*70); out.append(f)
    cs=d.get('candidates',d if isinstance(d,list) else [])
    for c in cs:
        out.append('  %-20s %-14s %s'%(c.get('id'),c.get('question_type'),c.get('expression')))
open('_tmp_sib.txt','w',encoding='utf-8').write('\n'.join(out))
print('ok')
