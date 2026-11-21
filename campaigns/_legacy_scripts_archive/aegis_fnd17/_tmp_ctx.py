import json
out=[]
for f in ['red_team_verdict.json','red_team_verdict_S2.json']:
    d=json.load(open(f,encoding='utf-8'))
    out.append('='*70); out.append(f)
    out.append(json.dumps(d,ensure_ascii=False,indent=1)[:6000])
open('_tmp_ctx.txt','w',encoding='utf-8').write('\n'.join(out))
print('ok')
