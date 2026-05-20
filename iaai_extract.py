"""
Extracción real: ya pasamos las protecciones, ahora sacamos los datos.

Los listings están server-rendered con clase 'table-row'. Sacamos:
  - Year/Make/Model
  - VIN
  - Odometer
  - Damage
  - Sale info / fecha subasta
  - Link a detalle
  - InventoryId
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
        await page.goto(URL, wait_until="domcontentloaded", timeout=45000)

        # Espera al render
        await page.wait_for_selector(".table-row", timeout=20000)
        await asyncio.sleep(3)

        # Extracción con JS dentro del navegador — mucho más confiable que parsear HTML
        vehicles = await page.evaluate("""
            () => {
                const rows = document.querySelectorAll('.table-row');
                const items = [];
                rows.forEach(row => {
                    // Skip headers
                    if (row.querySelector('th') || row.textContent.includes('VEHICLE\\nCONDITION')) return;

                    const getText = (sel) => {
                        const el = row.querySelector(sel);
                        return el ? el.innerText.trim() : null;
                    };
                    const getAttr = (sel, attr) => {
                        const el = row.querySelector(sel);
                        return el ? el.getAttribute(attr) : null;
                    };

                    // El link al detalle suele tener la mejor info
                    const detailLink = row.querySelector('a[href*="VehicleDetails"]');
                    if (!detailLink) return;

                    const href = detailLink.getAttribute('href');
                    const title = detailLink.innerText.trim();

                    // InventoryId extraído del href
                    const idMatch = href.match(/(\\d{6,})/);
                    const inventoryId = idMatch ? idMatch[1] : null;

                    // Buscar campos comunes por texto/clases
                    const fullText = row.innerText;

                    items.push({
                        inventoryId,
                        title,
                        href: href.startsWith('http') ? href : 'https://www.iaai.com' + href,
                        rawText: fullText.replace(/\\s+/g, ' ').slice(0, 400),
                    });
                });
                return items;
            }
        """)

        print(f"\n✅ Extraídos {len(vehicles)} vehículos\n")
        print("=" * 70)
        for i, v in enumerate(vehicles[:5]):
            print(f"\n--- Vehículo {i+1} ---")
            print(f"  ID:    {v['inventoryId']}")
            print(f"  Title: {v['title']}")
            print(f"  Link:  {v['href']}")
            print(f"  Raw:   {v['rawText'][:200]}")

        # Guarda todo
        (OUT / "vehicles.json").write_text(json.dumps(vehicles, indent=2))
        print(f"\n📄 Total guardado en {OUT / 'vehicles.json'}")

        await asyncio.sleep(5)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
