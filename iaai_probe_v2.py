"""
Probe v2: ahora que sabemos que pasa la primera barrera (Imperva+Kasada),
buscamos:
  1) El endpoint XHR/fetch real que devuelve los listings (oro puro).
  2) Esperar al render dinámico y extraer filas reales.
  3) Ver si paginación / filtros también responden.
"""

import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright

URL = "https://www.iaai.com/Vehiclelisting/Cars"
OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)


async def main():
    xhr_calls = []  # endpoints potencialmente útiles

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

        async def on_response(resp):
            url = resp.url
            ct = resp.headers.get("content-type", "")
            if "json" in ct and resp.request.resource_type in ("xhr", "fetch"):
                try:
                    size = len(await resp.body())
                except Exception:
                    size = -1
                xhr_calls.append({
                    "method": resp.request.method,
                    "url": url,
                    "status": resp.status,
                    "size": size,
                    "post_data": resp.request.post_data,
                })

        page.on("response", on_response)

        print(f"→ Cargando {URL}")
        await page.goto(URL, wait_until="domcontentloaded", timeout=45000)

        # Espera al render dinámico — scroll para forzar lazy loading si lo hubiera
        print("→ Esperando render dinámico (8s)...")
        await asyncio.sleep(3)
        await page.mouse.wheel(0, 1500)
        await asyncio.sleep(2)
        await page.mouse.wheel(0, 1500)
        await asyncio.sleep(3)

        # Intenta múltiples selectores para encontrar filas reales
        candidates = [
            "table tbody tr",
            "[class*='table-row']",
            "[class*='vehicle-card']",
            "a[href*='/VehicleDetails/']",
            ".table-row",
            ".tbl_listings tbody tr",
            "div[data-uname='vehicleResult']",
        ]
        found = {}
        for sel in candidates:
            try:
                n = await page.locator(sel).count()
                if n:
                    found[sel] = n
            except Exception:
                pass

        # Si encuentra filas, extrae las 3 primeras como muestra
        sample_rows = []
        best_sel = max(found, key=found.get) if found else None
        if best_sel:
            print(f"→ Mejor selector: {best_sel} ({found[best_sel]} elementos)")
            for i in range(min(3, found[best_sel])):
                try:
                    text = await page.locator(best_sel).nth(i).inner_text()
                    sample_rows.append(text[:500])
                except Exception as e:
                    sample_rows.append(f"err: {e}")

        # Captura screenshot ya con todo cargado
        await page.screenshot(path=str(OUT / "02_loaded.png"), full_page=False)

        # Reporta XHR interesantes (filtra ruido)
        IGNORE = ("google", "facebook", "tiktok", "analytics", "doubleclick", "kampyle", "hotjar")
        useful = [c for c in xhr_calls if not any(k in c["url"].lower() for k in IGNORE)]

        print("\n" + "=" * 60)
        print("XHR / FETCH potencialmente útiles")
        print("=" * 60)
        for c in useful[:20]:
            print(f"  [{c['status']}] {c['method']:5} {c['size']:>8}b  {c['url'][:140]}")
            if c["post_data"]:
                print(f"       POST body: {c['post_data'][:200]}")

        print("\n" + "=" * 60)
        print("Selectores que matchean")
        print("=" * 60)
        print(json.dumps(found, indent=2))

        print("\n" + "=" * 60)
        print(f"Muestra de filas (usando {best_sel})")
        print("=" * 60)
        for i, r in enumerate(sample_rows):
            print(f"\n--- fila {i} ---")
            print(r)

        # Guarda reporte completo
        (OUT / "report_v2.json").write_text(json.dumps({
            "xhr_useful": useful,
            "selectors_found": found,
            "best_selector": best_sel,
            "sample_rows": sample_rows,
        }, indent=2, default=str))

        print(f"\n→ Reporte completo en {OUT / 'report_v2.json'}")
        print("→ Navegador abierto 15s...")
        await asyncio.sleep(15)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
