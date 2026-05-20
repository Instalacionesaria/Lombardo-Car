"""
Scraper IAAI — versión funcional.

Extrae datos estructurados aprovechando que el sitio renderiza los listings
en HTML con onclick="ImageModalClicked(stock, inventoryId, vin, ?, year, make, model, trim)"
que es oro: ya nos vienen parseados.

Para datos adicionales (odómetro, daños, ubicación, fecha subasta, precio actual)
los sacamos de la lista de items debajo del título.
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
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = await context.new_page()

        print(f"→ Cargando {URL}")
        await page.goto(URL, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_selector(".table-row-border", timeout=20000)
        await asyncio.sleep(3)

        vehicles = await page.evaluate(r"""
            () => {
                const rows = document.querySelectorAll('.table-row-border');
                const items = [];

                rows.forEach(row => {
                    // El botón "View All Images" carga datos parseados en su onclick
                    const imgBtn = row.querySelector('button[onclick^="ImageModalClicked"]');
                    if (!imgBtn) return;

                    const onclick = imgBtn.getAttribute('onclick') || '';
                    // ImageModalClicked('stock','invId~US','vin','?','year','make','model','trim','false')
                    const m = onclick.match(/ImageModalClicked\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'/);

                    let stock = null, inventoryId = null, vin = null, year = null, make = null, model = null, trim = null;
                    if (m) {
                        [, stock, inventoryId, vin, , year, make, model, trim] = m;
                    }

                    // Watch button trae auctionId y fecha
                    const watchBtn = row.querySelector('a.btn-watch[onclick]');
                    let auctionId = null, auctionDate = null, status = null;
                    if (watchBtn) {
                        const wo = watchBtn.getAttribute('onclick') || '';
                        const wm = wo.match(/AddDelWatch\(this,\s*'([^']*)',\s*'(\d+)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)'/);
                        if (wm) {
                            auctionDate = wm[3];
                            auctionId = wm[4];
                            status = wm[5];
                        }
                    }

                    // Link al detalle
                    const detail = row.querySelector('a[href*="/VehicleDetail/"]');
                    const detailUrl = detail ? 'https://www.iaai.com' + detail.getAttribute('href') : null;

                    // Imagen
                    const img = row.querySelector('img[data-src*="vis.iaai.com"], img[src*="vis.iaai.com"]');
                    const imageUrl = img ? (img.getAttribute('data-src') || img.getAttribute('src')) : null;

                    // Toda la lista de detalles (odómetro, daños, motor, ubicación, etc.)
                    const dataItems = Array.from(row.querySelectorAll('.data-list__item'))
                        .map(li => li.innerText.trim())
                        .filter(t => t.length > 0);

                    // Heurísticas para campos comunes dentro de dataItems
                    const findBy = (regex) => {
                        for (const t of dataItems) if (regex.test(t)) return t;
                        return null;
                    };
                    const odometer = findBy(/\b\d[\d,]*\s*mi\b/i);
                    const fuel = findBy(/\b(Gasoline|Diesel|Electric|Hybrid|Flex)\b/i);
                    const cylinders = findBy(/\b\d\s*Cyl/i);
                    const damage = findBy(/(Front End|Rear End|Side|Roll Over|Flood|Hail|Vandalism|Burn|All Over|Normal Wear)/i);
                    const location = findBy(/\(.*(Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|Hampshire|Jersey|Mexico|York|Carolina|Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode|Tennessee|Texas|Utah|Vermont|Virginia|Washington|Wisconsin|Wyoming).*\)/i);
                    const runDrive = findBy(/Run & Drive|Stationary|Starts|Engine/i);

                    items.push({
                        stock,
                        inventoryId,
                        vin,
                        year: year ? parseInt(year) : null,
                        make,
                        model,
                        trim,
                        odometer,
                        fuel,
                        cylinders,
                        damage,
                        runDrive,
                        location,
                        auctionId,
                        auctionDate,
                        status,
                        imageUrl,
                        detailUrl,
                        allFields: dataItems,
                    });
                });
                return items;
            }
        """)

        # Filtra basura (filas vacías)
        vehicles = [v for v in vehicles if v.get("stock") or v.get("vin")]

        print(f"\n✅ Extraídos {len(vehicles)} vehículos\n")
        print("=" * 70)

        for i, v in enumerate(vehicles[:5]):
            print(f"\n--- Vehículo {i+1} ---")
            print(f"  Stock:     {v['stock']}")
            print(f"  Inv ID:    {v['inventoryId']}")
            print(f"  Vehículo:  {v['year']} {v['make']} {v['model']} {v['trim']}")
            print(f"  VIN:       {v['vin']}")
            print(f"  Odómetro:  {v['odometer']}")
            print(f"  Daño:      {v['damage']}")
            print(f"  Estado:    {v['runDrive']}")
            print(f"  Motor:     {v['fuel']} / {v['cylinders']}")
            print(f"  Ubicación: {v['location']}")
            print(f"  Subasta:   {v['auctionDate']} (id {v['auctionId']}, status {v['status']})")
            print(f"  URL:       {v['detailUrl']}")

        (OUT / "vehicles.json").write_text(json.dumps(vehicles, indent=2))
        print(f"\n📄 Total: {len(vehicles)} vehículos en {OUT / 'vehicles.json'}")

        await asyncio.sleep(3)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
