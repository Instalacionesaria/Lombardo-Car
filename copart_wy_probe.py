"""Listar todos los yards de Wyoming y luego filtrar por todos ellos."""

import asyncio
import json as _json
from playwright.async_api import async_playwright

API = "https://www.copart.com/public/lots/search-results"
LANDING = "https://www.copart.com/lotSearchResults?free=true&query="


async def fetch_pl(page, payload):
    res = await page.evaluate(
        """async ({url, body}) => {
            const r = await fetch(url, {
                method: 'POST', credentials: 'include',
                headers: {'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest'},
                body: JSON.stringify(body),
            });
            return {status: r.status, body: await r.text()};
        }""",
        {"url": API, "body": payload},
    )
    return _json.loads(res["body"]) if res["status"] == 200 else {}


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

        # 1. Obtener todos los yards desde los facets de una query general
        print("→ Listando todos los yards desde facets LOC...")
        general = await fetch_pl(page, {
            "query": [],
            "filter": {"MAKE": ['lot_make_desc:"TOYOTA"']},  # filter mínimo para no traer 0
            "sort": ["auction_date_utc asc"],
            "page": 0, "size": 1, "start": 0,
            "watchListOnly": False, "freeFormSearch": False,
            "hideImages": False, "defaultSort": False,
            "specificRowProvided": False,
            "displayName": "", "searchName": "", "backUrl": "",
            "includeTagByField": {}, "rawParams": {},
        })

        facets = general.get("data", {}).get("results", {}).get("facetFields", [])
        loc_facet = next((f for f in facets if f.get("quickPickCode") == "LOC"), None)

        if not loc_facet:
            print("   ! No se encontró facet LOC")
            print(f"   facets disponibles: {[f.get('quickPickCode') for f in facets]}")
            await browser.close()
            return

        # Los counts vienen como queries Solr: 'yard_name:"WY - CASPER"'
        all_yards = [c["query"] for c in loc_facet.get("facetCounts", [])]
        wy_yards = [y for y in all_yards if 'yard_name:"WY -' in y]
        print(f"   Total yards: {len(all_yards)}")
        print(f"   Yards de Wyoming: {wy_yards}")

        if not wy_yards:
            # Si Toyota no tiene lotes en WY, probemos sin filter
            print("   Toyota no tiene lotes en WY, listando con filter más amplio...")
            wider = await fetch_pl(page, {
                "query": [],
                "filter": {"YEAR": ['lot_year:"2024" OR lot_year:"2025" OR lot_year:"2026"']},
                "sort": ["auction_date_utc asc"],
                "page": 0, "size": 1, "start": 0,
                "watchListOnly": False, "freeFormSearch": False,
                "hideImages": False, "defaultSort": False,
                "specificRowProvided": False,
                "displayName": "", "searchName": "", "backUrl": "",
                "includeTagByField": {}, "rawParams": {},
            })
            facets2 = wider.get("data", {}).get("results", {}).get("facetFields", [])
            loc2 = next((f for f in facets2 if f.get("quickPickCode") == "LOC"), None)
            if loc2:
                all_yards2 = [c["query"] for c in loc2.get("facetCounts", [])]
                wy_yards = [y for y in all_yards2 if 'yard_name:"WY -' in y]
                print(f"   Con filter amplio — yards WY: {wy_yards}")

        # 2. Filtrar por los yards de WY
        if wy_yards:
            print(f"\n→ Filtrando por LOC con yards de WY ({len(wy_yards)} yards)...")
            wy_test = await fetch_pl(page, {
                "query": [],
                "filter": {"LOC": wy_yards},
                "sort": ["auction_date_utc asc"],
                "page": 0, "size": 10, "start": 0,
                "watchListOnly": False, "freeFormSearch": False,
                "hideImages": False, "defaultSort": False,
                "specificRowProvided": False,
                "displayName": "", "searchName": "", "backUrl": "",
                "includeTagByField": {}, "rawParams": {},
            })
            results = wy_test.get("data", {}).get("results", {})
            total = results.get("totalElements", 0)
            content = results.get("content") or []
            states = [lot.get("locState") for lot in content]
            yards = list({lot.get("syn") for lot in content})
            print(f"   total: {total}")
            print(f"   states en muestra: {states}")
            print(f"   yards en muestra: {yards}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
