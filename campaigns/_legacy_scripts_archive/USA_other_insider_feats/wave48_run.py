import asyncio, json, re, time, sys
sys.path.insert(0, 'D:/brain-mcp')
import main as bm

CAMP = 'D:/python/Lib/site-packages/cnhkmcp/untracked/APP/.agents/quant_framework/campaigns/USA_other_insider_feats'

W16 = 'signed_power(subtract(group_rank(ts_mean(multiply(subtract(vec_avg(buy_sell_tx_count_ratio_all_20d_filled), vec_avg(buy_sell_tx_count_ratio_all_60d_filled)), reverse(ts_mean(negative_score_average_value_3, 20))), 16), subindustry), 0.5), 2)'
W18 = 'signed_power(subtract(group_rank(ts_mean(multiply(subtract(vec_avg(buy_sell_tx_count_ratio_all_20d_filled), vec_avg(buy_sell_tx_count_ratio_all_60d_filled)), reverse(ts_mean(negative_score_average_value_3, 20))), 18), subindustry), 0.5), 2)'

async def pc_check():
    for attempt in range(6):
        try:
            r = await bm.check_correlation('N1NVqZYg')
            s = r if isinstance(r, str) else json.dumps(r)
            m = re.search(r'"max_correlation"\s*:\s*([\d.]+)', s)
            if m:
                print(f'N1NVqZYg PC: {m.group(1)}', flush=True)
                return
            print(f'[pc try {attempt}] pending: {s[:120]}', flush=True)
        except Exception as e:
            print(f'[pc try {attempt}] ERR {str(e)[:120]}', flush=True)
        await asyncio.sleep(60)

async def wave48():
    groups = [
        ('decay12', {'decay': 12, 'truncation': 0.025}, [('nc18_d12', W18), ('nc16_d12', W16)]),
        ('trunc05', {'decay': 8, 'truncation': 0.05}, [('nc18_t05', W18), ('nc18_d12_t05', W18)]),
        ('trunc01', {'decay': 8, 'truncation': 0.01}, [('nc18_t01', W18), ('nc16_t01', W16)]),
    ]
    BASE = dict(instrument_type='EQUITY', region='USA', universe='TOP1000', delay=1,
                unit_handling='VERIFY', nan_handling='ON', pasteurization='ON',
                language='FASTEXPR', visualization=False)
    all_results = {'tags': [], 'location': None, 'result': {'alpha_results': []}}
    for gname, gset, gitems in groups:
        exprs = [e for _, e in gitems]
        loc = None
        for attempt in range(10):
            try:
                sub = await bm.create_multi_simulation(exprs, neutralization='INDUSTRY',
                                                       decay=gset['decay'], truncation=gset['truncation'], **BASE)
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
    fp = f'{CAMP}/gate1_wave48_result_{int(time.time())}.json'
    json.dump(all_results, open(fp, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('SAVED:', fp, flush=True)

async def main():
    await asyncio.gather(pc_check(), wave48())

asyncio.run(main())
