"""Probar diferentes formatos de filter para descubrir el correcto para estado/yard."""

import asyncio
import json as _json
from playwright.async_api import async_playwright

API = "https://www.copart.com/public/lots/search-results"
LANDING = "https://www.copart.com/lotSearchResults?free=true&query="

# Combinaciones a probar (filter, descripción)
TESTS = [
    ({}, "filter vacío"),
    ({"Misc Item State": ["WY"]}, "'Misc Item State': ['WY']"),
    ({"LOC": ["AL - BIRMINGHAM"]}, "LOC plain"),
    ({"LOC": ['yard_name:"AL - BIRMINGHAM"']}, "LOC con solr query"),
    ({"MAKE": ["TOYOTA"]}, "MAKE plain"),
    ({"MAKE": ['lot_make_desc:"TOYOTA"']}, "MAKE con solr query"),
    ({"YEAR": ["2025"]}, "YEAR plain"),
    ({"YEAR": ['lot_year:"2025"']}, "YEAR con solr query"),
    ({"FETI": ['member_lot_condition:USED']}, "FETI featured items"),
    ({"SLOC": ['auction_host_name:"AL - BIRMINGHAM"']}, "SLOC auction host"),
]


def payload(flt: dict) -> dict:
    return {
        "query": [],
        "filter": flt,
        "sort": ["auction_date_utc asc"],
        "page": 0, "size": 5, "start": 0,
        "watchListOnly": False, "freeFormSearch": False,
        "hideImages": False, "defaultSort": False,
        "specificRowProvided": False,
        "displayName": "", "searchName": "", "backUrl": "",
        "includeTagByField": {}, "rawParams": {},
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

        print(f"{'desc':<40} | {'total':>8} | states (top 5)")
        print("-" * 90)

        for flt, desc in TESTS:
            res = await page.evaluate(
                """async ({url, body}) => {
                    const r = await fetch(url, {
                        method: 'POST', credentials: 'include',
                        headers: {'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
                        body: JSON.stringify(body),
                    });
                    return {status: r.status, body: await r.text()};
                }""",
                {"url": API, "body": payload(flt)},
            )

            data = _json.loads(res["body"]) if res["status"] == 200 else {}
            results = ((data or {}).get("data") or {}).get("results") or {}
            content = results.get("content") or []
            total = results.get("totalElements", 0)
            states_sample = [lot.get("locState") for lot in content[:5]]
            print(f"{desc:<40} | {total:>8} | {states_sample}")
            await asyncio.sleep(0.3)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
