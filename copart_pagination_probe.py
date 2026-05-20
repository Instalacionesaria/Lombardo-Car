"""Probe rápido: ¿hasta qué página de la API de Copart podemos pedir antes de que falle o devuelva vacío?

Probamos páginas en escala logarítmica: 10, 50, 100, 200, 500, 1000, 2000.
"""

import asyncio
import json as _json
from playwright.async_api import async_playwright

API = "https://www.copart.com/public/lots/search-results"
LANDING = "https://www.copart.com/lotSearchResults?free=true&query="

PAGES_TO_TEST = [10, 50, 100, 200, 500, 1000, 2000]


def payload(page: int) -> dict:
    return {
        "query": [],
        "filter": {},
        "sort": ["auction_date_utc asc"],
        "page": page,
        "size": 100,
        "start": page * 100,
        "watchListOnly": False,
        "freeFormSearch": False,
        "hideImages": False,
        "defaultSort": False,
        "specificRowProvided": False,
        "displayName": "",
        "searchName": "",
        "backUrl": "",
        "includeTagByField": {},
        "rawParams": {},
    }


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            locale="en-US",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = await context.new_page()
        await page.goto(LANDING, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        print(f"{'page':>6} | {'status':>6} | {'lots':>6} | {'total':>8}")
        print("-" * 40)

        for p_idx in PAGES_TO_TEST:
            res = await page.evaluate(
                """async ({url, body}) => {
                    const r = await fetch(url, {
                        method: 'POST', credentials: 'include',
                        headers: {'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
                        body: JSON.stringify(body),
                    });
                    return {status: r.status, body: await r.text()};
                }""",
                {"url": API, "body": payload(p_idx)},
            )

            if res["status"] != 200:
                print(f"{p_idx:>6} | {res['status']:>6} | {'ERR':>6} | {'-':>8}")
                continue

            data = _json.loads(res["body"])
            results = ((data or {}).get("data") or {}).get("results") or {}
            content = results.get("content") or []
            total = results.get("totalElements", 0)
            ret_code = data.get("returnCode")
            ret_desc = data.get("returnCodeDesc", "")
            print(f"{p_idx:>6} | {res['status']:>6} | {len(content):>6} | {total:>8} | ret={ret_code} {ret_desc[:40]}")
            await asyncio.sleep(0.5)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
