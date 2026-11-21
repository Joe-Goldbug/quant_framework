import asyncio, json, re, sys
sys.path.insert(0, 'D:/brain-mcp')
import main as bm

async def main():
    for aid in ['wpQbLPO2', 'xArbRWQg']:
        for attempt in range(10):
            try:
                r = await bm.check_correlation(aid)
                s = r if isinstance(r, str) else json.dumps(r)
                m = re.search(r'"max_correlation"\s*:\s*([\d.]+)', s)
                if m:
                    print(f'PC {aid}: {m.group(1)}', flush=True)
                    break
                print(f'[{aid} try {attempt}] pending: {s[:100]}', flush=True)
            except Exception as e:
                print(f'[{aid} try {attempt}] ERR {str(e)[:100]}', flush=True)
            await asyncio.sleep(60)

asyncio.run(main())
