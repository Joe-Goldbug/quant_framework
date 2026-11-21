import json, io, sys

d = json.load(open('agent_field_ref.json', encoding='utf-8'))
out = ['TOTAL ' + str(len(d))]
ids = ['fnd17_ani','fnd17_aniac','fnd17_cainq','fnd17_inq','fnd17_aniacnorm',
       'fnd17_aninorm','fnd17_aniexclxor','fnd17_aniacinclx','fnd17_fcfmtt',
       'fnd17_fcfq','fnd17_fcf1a','fnd17_rhsfcfmtt','fnd17_rhsfcfq','fnd17_ata',
       'fnd17_atmtt','fnd17_atotce','fnd17_qtotce']
for i in ids:
    out.append(i + ' :: ' + json.dumps(d.get(i), ensure_ascii=False))
open('_tmp_check.txt', 'w', encoding='utf-8').write('\n'.join(out))
print('ok')
