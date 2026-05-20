"""Encontrar el cap de paginación exacto de Copart."""

import asyncio
import json as _json
from playwright.async_api import async_playwright

API = "https://www.copart.com/public/lots/search-results"
LANDING = "https://www.copart.com/lotSearchResults?free=true&query="


def payload(p_idx, sz):
    return {
        "query": [],
        "filter": {"MAKE": ['lot_make_desc:"TOYOTA"']},
        "sort": ["salelight_priority asc", "member_damage_group_priority asc",
                 "auction_date_type desc", "auction_date_utc asc"],
        "page": p_idx, "size": sz, "start": p_idx * sz,
        "watchListOnly": False, "freeFormSearch": False,
        "hideImages": False, "defaultSort": False,
        "specificRowProvided": False,
        "displayName": "", "searchName": "", "backUrl": "",
        "includeTagByField": {}, "rawParams": {},
    }


async def query(page, p_idx, sz=100):
    res = await page.evaluate(
        """async ({url, body}) => {
            const r = await fetch(url, {method:'POST', credentials:'include',
                headers:{'Content-Type':'application/json','X-Requested-With':'XMLHttpRequest'},
                body: JSON.stringify(body)});
            return {status: r.status, body: await r.text()};
        }""",
        {"url": API, "body": payload(p_idx, sz)},
    )
    try:
        data = _json.loads(res["body"]) if res["status"] == 200 else {}
        results = ((data or {}).get("data") or {}).get("results") or {}
        content = results.get("content") or []
        total = results.get("totalElements", 0)
        return len(content), total
    except Exception as e:
        return -1, -1  # error parsing


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900}, locale="en-US",
        )
        await ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        page = await ctx.new_page()
        await page.goto(LANDING, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        print("Test secuencial size=100: ¿llegamos hasta el final de Toyota (~466 pages)?")
        print(f"{'page':>5} | {'lots':>5} | {'total':>7}")
        first_zero = None
        last_ok = -1
        for p_idx in range(0, 500):
            n, total = await query(page, p_idx, 100)
            if p_idx % 20 == 0 or n <= 0:
                print(f"{p_idx:>5} | {n:>5} | {total:>7}")
            if n == 0:
                first_zero = p_idx
                break
            if n > 0:
                last_ok = p_idx
            await asyncio.sleep(0.3)
        print(f"\nÚltima página con datos: {last_ok}")
        print(f"Primera página con 0 lotes: {first_zero}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
