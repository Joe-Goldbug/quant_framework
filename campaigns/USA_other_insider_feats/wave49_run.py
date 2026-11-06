import asyncio, json, re, time, sys
sys.path.insert(0, 'D:/brain-mcp')
import main as bm

CAMP = 'D:/python/Lib/site-packages/cnhkmcp/untracked/APP/.agents/quant_framework/campaigns/USA_other_insider_feats'

def core(power, outer_w):
    return (f'signed_power(subtract(group_rank(ts_mean(multiply(subtract(vec_avg(buy_sell_tx_count_ratio_all_20d_filled), '
            f'vec_avg(buy_sell_tx_count_ratio_all_60d_filled)), reverse(ts_mean(negative_score_average_value_3, 20))), '
            f'{outer_w}), subindustry), 0.5), {power})')

async def pc_check(aids):
    for aid in aids:
        for attempt in range(8):
            try:
                r = await bm.check_correlation(aid)
                s = r if isinstance(r, str) else json.dumps(r)
                m = re.search(r'"max_correlation"\s*:\s*([\d.]+)', s)
                if m:
                    print(f'PC {aid}: {m.group(1)}', flush=True)
                    break
                print(f'[pc {aid} try {attempt}] pending: {s[:100]}', flush=True)
            except Exception as e:
                print(f'[pc {aid} try {attempt}] ERR {str(e)[:100]}', flush=True)
            await asyncio.sleep(60)

async def wave49():
    groups = [
        ('d10', {'decay': 10}, [('p2_d10', core(2, 18)), ('p225_d10', core(2.25, 18))]),
        ('d12', {'decay': 12}, [('p225_d12', core(2.25, 18)), ('p25_d12', core(2.5, 18))]),
        ('d16', {'decay': 16}, [('p2_d16', core(2, 18)), ('p225_d16', core(2.25, 18))]),
    ]
    BASE = dict(instrument_type='EQUITY', region='USA', universe='TOP1000', delay=1,
                truncation=0.025, unit_handling='VERIFY', nan_handling='ON', pasteurization='ON',
                language='FASTEXPR', visualization=False)
    all_results = {'tags': [], 'result': {'alpha_results': []}}
    for gname, gset, gitems in groups:
        exprs = [e for _, e in gitems]
        loc = None
        for attempt in range(10):
            try:
                sub = await bm.create_multi_simulation(exprs, neutralization='INDUSTRY',
                                                       decay=gset['decay'], **BASE)
                sub = json.loads(sub) if isinstance(sub, str) else sub
                if sub.get('location'):
                    loc = sub['location']
                    print(f'[{gname}] SUBMITTED: {sub.get("multisimulation_id")}', flush=True)
                    break
                print(f'[{gname} attempt {attempt}] {str(sub)[:120]}', flush=True)
            except Exception as e:
                print(f'[{gname} attempt {attempt}] exc: {str(e)[:120]}', flush=True)
            await asyncio.sleep(20)
        if not loc:
            print(f'[{gname}] FAILED', flush=True)
            continue
        await asyncio.sleep(600)
        for i in range(40):
            try:
                res = await bm.fetch_multi_simulation_result(loc)
                res = json.loads(res) if isinstance(res, str) else res
                n = len(res.get('alpha_results') or [])
                print(f'[{gname} fetch {i}] {n}', flush=True)
                if n >= len(exprs):
                    all_results['tags'].extend(t for t, _ in gitems)
                    all_results['result']['alpha_results'].extend(res['alpha_results'])
                    break
            except Exception as e:
                print(f'[{gname} fetch {i}] {str(e)[:120]}', flush=True)
            await asyncio.sleep(30)
    fp = f'{CAMP}/gate1_wave49_result_{int(time.time())}.json'
    json.dump(all_results, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('SAVED:', fp, flush=True)

async def main():
    await asyncio.gather(pc_check(['QPvKlRGp', 'QPvKlRGp']), wave49())

asyncio.run(main())
