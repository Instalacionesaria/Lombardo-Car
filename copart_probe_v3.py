"""
Probe v3: llamar al endpoint /public/lots/search-results directamente
desde el browser context para inspeccionar 1 lote completo.

Después intenta replicar el POST con `requests` + cookies exportadas
para ver si podemos saltarnos Playwright en producción (más rápido).
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)

LANDING = "https://www.copart.com/lotSearchResults?free=true&query=toyota"
API = "https://www.copart.com/public/lots/search-results"

PAYLOAD = {
    "query": ["toyota"],
    "filter": {},
    "sort": [
        "salelight_priority asc",
        "member_damage_group_priority asc",
        "auction_date_type desc",
        "auction_date_utc asc",
    ],
    "page": 0,
    "size": 5,
    "start": 0,
    "watchListOnly": False,
    "freeFormSearch": True,
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
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        page = await context.new_page()

        # Cargamos la landing para que se resuelva el challenge de Kasada
        print(f"→ Cargando landing para obtener cookies Kasada: {LANDING}")
        await page.goto(LANDING, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)  # dejar que Kasada se resuelva

        cookies = await context.cookies()
        cookie_names = sorted({c["name"] for c in cookies})
        print(f"   total cookies: {len(cookies)}")
        print(f"   nombres: {cookie_names}")

        # Llamar al endpoint desde el contexto del browser (usa cookies+TLS+JS automáticamente)
        print(f"\n→ POST directo al endpoint con size=5...")
        result = await page.evaluate(
            """
            async ({url, body}) => {
              const r = await fetch(url, {
                method: 'POST',
                credentials: 'include',
                headers: {
                  'Content-Type': 'application/json',
                  'Accept': 'application/json, text/plain, */*',
                  'X-Requested-With': 'XMLHttpRequest',
                },
                body: JSON.stringify(body),
              });
              const text = await r.text();
              return {status: r.status, body: text};
            }
            """,
            {"url": API, "body": PAYLOAD},
        )

        print(f"   status: {result['status']}")
        print(f"   body size: {len(result['body'])} bytes")

        try:
            data = json.loads(result["body"])
        except Exception as e:
            print(f"   ! no es JSON válido: {e}")
            (OUT / "copart_v3_raw.txt").write_text(result["body"][:5000])
            return

        # Dumpear respuesta completa
        (OUT / "copart_v3_full.json").write_text(json.dumps(data, indent=2, default=str))

        # Inspeccionar campos del primer lote
        lots = data.get("data", {}).get("results", {}).get("content", [])
        print(f"\n→ Lotes devueltos: {len(lots)}")
        print(f"→ Total disponible: {data.get('data', {}).get('results', {}).get('totalElements')}")

        if lots:
            lot = lots[0]
            print(f"\n→ Campos del primer lote ({len(lot)} keys):")
            for k in sorted(lot.keys()):
                v = lot[k]
                preview = repr(v)
                if len(preview) > 90:
                    preview = preview[:90] + "..."
                print(f"   {k:40s} = {preview}")

            (OUT / "copart_v3_one_lot.json").write_text(json.dumps(lot, indent=2, default=str))
            print(f"\n→ Lote completo guardado en {OUT / 'copart_v3_one_lot.json'}")

        # Exportar cookies para futura prueba con curl_cffi
        (OUT / "copart_cookies.json").write_text(json.dumps(cookies, indent=2, default=str))
        print(f"→ Cookies exportadas a {OUT / 'copart_cookies.json'}")

        print("\n→ Navegador abierto 8s...")
        await asyncio.sleep(8)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
