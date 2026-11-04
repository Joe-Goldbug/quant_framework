import re
t=open('fnd17_catalog.md',encoding='utf-8').read()
out=[]
for key in ['aniacnorm','aninorm','aniexclxor','aniacinclx','fcfmtt','fcfq','fcf1a','rhsfcfmtt','rhsfcfq','cainq','inq','aniac','atmtt','atotce','qtotce','ata']:
    for m in re.finditer(re.escape(key), t):
        s=max(0,m.start()-260); e=min(len(t),m.end()+260)
        out.append('### '+key+' ###')
        out.append(t[s:e])
        break
open('_tmp_cat.txt','w',encoding='utf-8').write('\n'.join(out))
print('ok')
