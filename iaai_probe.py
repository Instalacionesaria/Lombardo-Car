"""
Diagnóstico: ¿qué pasa cuando entramos a IAAI con Playwright?

Objetivo: ver honestamente la primera barrera. Visible (headless=False) para
poder mirar challenges, captchas o redirects. Captura screenshots, headers,
y detecta Akamai en las respuestas.
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

URL = "https://www.iaai.com/Vehiclelisting/Cars"
OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)


async def main():
    akamai_hits = []
    blocked_signals = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
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

        # Quita el flag más obvio de automatización
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        page = await context.new_page()

        def on_response(resp):
            url = resp.url
            headers = resp.headers
            server = headers.get("server", "")
            akamai_h = [k for k in headers if "akamai" in k.lower() or k.lower().startswith("x-akamai")]
            if "akamai" in server.lower() or akamai_h:
                akamai_hits.append({"url": url[:120], "server": server, "akamai_headers": akamai_h})
            if resp.status in (403, 429, 503):
                blocked_signals.append({"url": url[:120], "status": resp.status})

        page.on("response", on_response)

        print(f"→ Navegando a {URL}")
        try:
            response = await page.goto(URL, wait_until="domcontentloaded", timeout=45000)
            print(f"  status: {response.status if response else 'sin respuesta'}")
        except Exception as e:
            print(f"  ERROR navegando: {e}")

        # Espera por si Akamai mete challenge JS
        await asyncio.sleep(5)

        await page.screenshot(path=str(OUT / "01_initial.png"), full_page=True)
        print(f"  screenshot → {OUT / '01_initial.png'}")

        title = await page.title()
        current_url = page.url
        print(f"  title: {title!r}")
        print(f"  url final: {current_url}")

        # Marcadores típicos de bloqueo Akamai/captcha
        html = await page.content()
        markers = {
            "akamai_reference": "Reference #" in html or "reference #" in html.lower(),
            "access_denied": "Access Denied" in html or "access denied" in html.lower(),
            "captcha": "captcha" in html.lower() or "recaptcha" in html.lower(),
            "pardon_interruption": "pardon" in html.lower() and "interruption" in html.lower(),
            "checking_browser": "checking your browser" in html.lower(),
            "bm_sz_cookie": False,  # se llena abajo
        }

        cookies = await context.cookies()
        cookie_names = [c["name"] for c in cookies]
        markers["bm_sz_cookie"] = any(c.startswith(("bm_", "ak_", "_abck")) for c in cookie_names)

        # ¿Hay listings? buscamos selectores comunes
        listing_selectors = [
            "[data-testid*='vehicle']",
            ".vehicle-card",
            ".result-item",
            "a[href*='VehicleDetails']",
            "[class*='vehicle' i]",
        ]
        found_listings = {}
        for sel in listing_selectors:
            try:
                count = await page.locator(sel).count()
                if count:
                    found_listings[sel] = count
            except Exception:
                pass

        # Guarda HTML para inspección
        (OUT / "page.html").write_text(html, encoding="utf-8")

        report = {
            "final_url": current_url,
            "title": title,
            "html_bytes": len(html),
            "akamai_response_hits": akamai_hits[:5],
            "akamai_total_hits": len(akamai_hits),
            "blocked_status_codes": blocked_signals[:10],
            "akamai_cookies_present": markers["bm_sz_cookie"],
            "all_cookies": cookie_names,
            "block_markers": {k: v for k, v in markers.items() if v},
            "listing_selectors_found": found_listings,
        }

        print("\n" + "=" * 60)
        print("REPORTE")
        print("=" * 60)
        print(json.dumps(report, indent=2, default=str))

        (OUT / "report.json").write_text(json.dumps(report, indent=2, default=str))

        print(f"\nDejaré el navegador abierto 15s para que mires...")
        await asyncio.sleep(15)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
