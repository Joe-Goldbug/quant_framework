import json,os
out=[]
for f in ['batch_S3_result.json']:
    if not os.path.exists(f): continue
    d=json.load(open(f,encoding='utf-8'))
    out.append('type '+str(type(d)))
    out.append('keys '+str(list(d.keys()))[:300] if isinstance(d,dict) else 'list len %d'%len(d))
open('_tmp_s3audit.txt','w',encoding='utf-8').write('\n'.join(out))
print('ok')
