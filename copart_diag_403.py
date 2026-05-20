"""Diagnosticar 403: ver el body de la respuesta y cookies actuales."""

import asyncio
import json as _json
from playwright.async_api import async_playwright

API = "https://www.copart.com/public/lots/search-results"
LANDING = "https://www.copart.com/lotSearchResults?free=true&query="


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
        print(f"→ Cargando landing...")
        await page.goto(LANDING, wait_until="domcontentloaded", timeout=60000)
        print(f"→ Esperando 15 seg (más generoso)...")
        await asyncio.sleep(15)

        cookies = await ctx.cookies()
        names = sorted({c["name"] for c in cookies})
        print(f"→ Cookies ({len(cookies)}): {names}")

        res = await page.evaluate(
            """async () => {
                const r = await fetch('https://www.copart.com/public/lots/search-results', {
                    method: 'POST', credentials: 'include',
                    headers: {'Content-Type':'application/json','X-Requested-With':'XMLHttpRequest'},
                    body: JSON.stringify({
                        query: [], filter: {"MAKE": ['lot_make_desc:"TOYOTA"']},
                        sort: ['auction_date_utc asc'],
                        page: 0, size: 5, start: 0,
                        watchListOnly: false, freeFormSearch: false,
                        hideImages: false, defaultSort: false,
                        specificRowProvided: false,
                        displayName: '', searchName: '', backUrl: '',
                        includeTagByField: {}, rawParams: {}
                    }),
                });
                return {status: r.status, body: await r.text(), headers: [...r.headers.entries()]};
            }"""
        )
        print(f"→ Status: {res['status']}")
        print(f"→ Body (primeros 500):\n{res['body'][:500]}")
        print(f"→ Headers:")
        for h in res["headers"][:20]:
            print(f"   {h[0]}: {h[1]}")

        print("\n→ Navegador abierto 20s para inspección manual...")
        await asyncio.sleep(20)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
