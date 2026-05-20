"""Inspector: volcamos la estructura real de una fila para entender el HTML."""

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

URL = "https://www.iaai.com/Vehiclelisting/Cars"
OUT = Path(__file__).parent / "out"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = await context.new_page()
        await page.goto(URL, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_selector(".table-row", timeout=20000)
        await asyncio.sleep(4)

        # Dump del DOM renderizado (post-JS)
        rendered_html = await page.content()
        (OUT / "rendered.html").write_text(rendered_html, encoding="utf-8")
        print(f"DOM renderizado: {len(rendered_html)} bytes → {OUT / 'rendered.html'}")

        # Estructura de las primeras filas con contenido real
        sample = await page.evaluate("""
            () => {
                const rows = Array.from(document.querySelectorAll('.table-row'));
                // saltamos headers, buscamos filas con texto real >50 chars
                const real = rows.filter(r => r.innerText.trim().length > 80).slice(0, 3);
                return real.map(r => ({
                    outerHTML: r.outerHTML.slice(0, 2500),
                    text: r.innerText
                }));
            }
        """)
        for i, s in enumerate(sample):
            print(f"\n{'='*60}\nFILA REAL {i+1}\n{'='*60}")
            print("TEXTO:")
            print(s["text"])
            print("\nHTML:")
            print(s["outerHTML"])

        # Cualquier link que contenga 'vehicle' o IDs
        links = await page.evaluate("""
            () => Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.getAttribute('href'))
                .filter(h => h && (h.includes('Vehicle') || h.match(/\\d{6,}/)))
                .slice(0, 10)
        """)
        print(f"\n\nLinks con 'Vehicle' o IDs ({len(links)}):")
        for l in links:
            print(f"  {l}")

        await asyncio.sleep(5)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
