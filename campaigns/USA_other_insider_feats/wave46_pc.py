import asyncio, json, re, sys
sys.path.insert(0, "D:/brain-mcp")
import main as bm

async def go():
    for aid in ['MPY3P66r','vR12RAYd','A1Vv1xxg','j2Y82aaQ','Xg9Jgaam']:
        try:
            r = await bm.check_correlation(aid)
            s = r if isinstance(r, str) else json.dumps(r)
            m = re.search(r'"max_correlation"\s*:\s*([\d.]+)', s)
            print(aid, 'PC:', m.group(1) if m else s[:150], flush=True)
        except Exception as e:
            print(aid, 'ERR', str(e)[:120], flush=True)

asyncio.run(go())
