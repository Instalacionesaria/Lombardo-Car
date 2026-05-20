"""
Probe inicial de Copart.com — análogo al que corrimos en IAAI.

Objetivos:
  1) ¿Pasamos Akamai Bot Manager? (cookies _abck, bm_sz, bm_sv, ak_bmsc)
  2) ¿Renderiza listings sin login?
  3) ¿Qué XHR/fetch traen los datos (idealmente JSON)?
  4) Capturar selectores útiles y una muestra de filas.

Empezamos desde el home y luego intentamos una búsqueda genérica
(`/vehicleFinderSearch/` o similar) para ver paginación.
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

HOME = "https://www.copart.com/"
# Búsqueda pública que suele renderizar resultados sin login.
SEARCH = "https://www.copart.com/vehicleFinderSearch/"

OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)


async def main():
    xhr_calls = []
    challenge_hits = []  # respuestas 403/429/202 típicas de Akamai

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
            rtype = resp.request.resource_type
            status = resp.status

            if status in (403, 429, 202) and rtype in ("xhr", "fetch", "document"):
                challenge_hits.append({
                    "status": status,
                    "url": url[:200],
                    "type": rtype,
                })

            if "json" in ct and rtype in ("xhr", "fetch"):
                try:
                    size = len(await resp.body())
                except Exception:
                    size = -1
                xhr_calls.append({
                    "method": resp.request.method,
                    "url": url,
                    "status": status,
                    "size": size,
                    "post_data": resp.request.post_data,
                })

        page.on("response", on_response)

        # ---------- 1) HOME ----------
        print(f"→ Cargando home: {HOME}")
        try:
            await page.goto(HOME, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            print(f"   ! goto home falló: {e}")

        await asyncio.sleep(3)
        await page.screenshot(path=str(OUT / "copart_01_home.png"), full_page=False)

        cookies_home = await context.cookies()
        akamai_cookies = [c["name"] for c in cookies_home if c["name"] in (
            "_abck", "bm_sz", "bm_sv", "ak_bmsc", "bm_mi", "bm_so", "bm_lso"
        )]
        print(f"   cookies Akamai detectadas: {akamai_cookies or 'NINGUNA'}")
        print(f"   total cookies: {len(cookies_home)}")

        # ---------- 2) BÚSQUEDA ----------
        print(f"\n→ Cargando búsqueda: {SEARCH}")
        try:
            await page.goto(SEARCH, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            print(f"   ! goto search falló: {e}")

        print("→ Esperando render dinámico (8s) + scroll...")
        await asyncio.sleep(3)
        await page.mouse.wheel(0, 1500)
        await asyncio.sleep(2)
        await page.mouse.wheel(0, 1500)
        await asyncio.sleep(3)

        await page.screenshot(path=str(OUT / "copart_02_search.png"), full_page=False)

        # Selectores candidatos basados en lo común en Copart
        candidates = [
            "table#serverSideDataTable tbody tr",
            "table tbody tr",
            "a[href*='/lot/']",
            "[data-uname='lotsearchLotnumber']",
            "[class*='search-result']",
            "[class*='lot-card']",
            "[class*='vehicle-card']",
            "tr.p-datatable-row",
            "[data-uname='lotsearchResults']",
        ]
        found = {}
        for sel in candidates:
            try:
                n = await page.locator(sel).count()
                if n:
                    found[sel] = n
            except Exception:
                pass

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
        else:
            print("→ Ningún selector matcheó — probablemente bloqueo o render distinto.")

        # ---------- REPORTE ----------
        IGNORE = ("google", "facebook", "tiktok", "analytics", "doubleclick",
                  "kampyle", "hotjar", "newrelic", "qualtrics", "optimizely",
                  "akstat", "akamaihd", "fonts.")
        useful = [c for c in xhr_calls if not any(k in c["url"].lower() for k in IGNORE)]

        print("\n" + "=" * 60)
        print("Challenges Akamai (403/429/202)")
        print("=" * 60)
        for h in challenge_hits[:20]:
            print(f"  [{h['status']}] {h['type']:8}  {h['url']}")
        if not challenge_hits:
            print("  (ninguno — buena señal)")

        print("\n" + "=" * 60)
        print("XHR / FETCH JSON potencialmente útiles")
        print("=" * 60)
        for c in useful[:25]:
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

        (OUT / "copart_report.json").write_text(json.dumps({
            "akamai_cookies": akamai_cookies,
            "total_cookies": len(cookies_home),
            "challenges": challenge_hits,
            "xhr_useful": useful,
            "selectors_found": found,
            "best_selector": best_sel,
            "sample_rows": sample_rows,
        }, indent=2, default=str))

        print(f"\n→ Reporte completo en {OUT / 'copart_report.json'}")
        print("→ Navegador abierto 15s para inspección manual...")
        await asyncio.sleep(15)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
