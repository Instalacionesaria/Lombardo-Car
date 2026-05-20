"""
Probe v2 de Copart: hacer una búsqueda REAL y capturar:
  1) El endpoint exacto que devuelve los lotes (POST a /public/data/lotdetails/...)
  2) Estructura del JSON de respuesta.
  3) Una muestra de 3 lotes con sus campos.
  4) Si la paginación funciona.

Probamos con búsqueda genérica "Toyota" via la URL pública /lotSearchResults/.
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

SEARCH_URL = "https://www.copart.com/lotSearchResults?free=true&query=toyota"
OUT = Path(__file__).parent / "out"
OUT.mkdir(exist_ok=True)


async def main():
    lot_search_responses = []  # respuestas que parecen contener lotes
    all_json_xhr = []
    challenges = []

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
                challenges.append({"status": status, "url": url[:200]})

            if "json" not in ct or rtype not in ("xhr", "fetch"):
                return

            try:
                body = await resp.body()
                size = len(body)
            except Exception:
                return

            entry = {
                "method": resp.request.method,
                "url": url,
                "status": status,
                "size": size,
                "post_data": resp.request.post_data,
                "request_headers": {k: v for k, v in resp.request.headers.items()
                                    if k.lower() in ("content-type", "accept", "x-requested-with")},
            }
            all_json_xhr.append(entry)

            # Heurística para identificar endpoint de búsqueda de lotes
            keywords = ("lotsearch", "lotdetails", "solr", "search", "lot")
            if any(k in url.lower() for k in keywords) and size > 1000:
                # Intentar parsear y ver si tiene array de lotes
                try:
                    data = json.loads(body)
                    entry["json_preview"] = _preview(data)
                    lot_search_responses.append(entry)
                except Exception:
                    pass

        page.on("response", on_response)

        print(f"→ Cargando búsqueda: {SEARCH_URL}")
        try:
            await page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            print(f"   ! goto falló: {e}")

        print("→ Esperando render dinámico (10s) + scroll...")
        await asyncio.sleep(4)
        await page.mouse.wheel(0, 1500)
        await asyncio.sleep(3)
        await page.mouse.wheel(0, 1500)
        await asyncio.sleep(3)

        await page.screenshot(path=str(OUT / "copart_v2_search.png"), full_page=False)

        # Buscar filas en el DOM con selectores típicos de Copart
        candidates = [
            "table#serverSideDataTable tbody tr",
            "tr[data-uname='lotsearchResults']",
            "[data-uname='lotsearchLotnumber']",
            "a[href*='/lot/']",
            "tr.p-datatable-row",
            "[class*='search-result-row']",
            "table tbody tr",
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
                    sample_rows.append(text[:600])
                except Exception as e:
                    sample_rows.append(f"err: {e}")

        # Reporte
        print("\n" + "=" * 60)
        print(f"Challenges Kasada/Akamai: {len(challenges)}")
        print("=" * 60)
        for h in challenges[:10]:
            print(f"  [{h['status']}] {h['url']}")
        if not challenges:
            print("  (ninguno)")

        print("\n" + "=" * 60)
        print(f"Candidatos a endpoint de búsqueda de lotes: {len(lot_search_responses)}")
        print("=" * 60)
        for c in lot_search_responses[:10]:
            print(f"\n  [{c['status']}] {c['method']:5} {c['size']:>8}b  {c['url'][:140]}")
            if c.get("post_data"):
                print(f"      POST body: {c['post_data'][:300]}")
            if c.get("json_preview"):
                print(f"      JSON preview:\n{c['json_preview']}")

        print("\n" + "=" * 60)
        print("Selectores DOM que matchean")
        print("=" * 60)
        print(json.dumps(found, indent=2))

        print("\n" + "=" * 60)
        print(f"Muestra de filas DOM ({best_sel})")
        print("=" * 60)
        for i, r in enumerate(sample_rows):
            print(f"\n--- fila {i} ---")
            print(r)

        (OUT / "copart_v2_report.json").write_text(json.dumps({
            "challenges": challenges,
            "all_json_xhr_count": len(all_json_xhr),
            "lot_search_candidates": lot_search_responses,
            "all_json_xhr": [{**c, "post_data": (c.get("post_data") or "")[:500]}
                             for c in all_json_xhr],
            "selectors_found": found,
            "best_selector": best_sel,
            "sample_rows": sample_rows,
        }, indent=2, default=str))

        print(f"\n→ Reporte completo en {OUT / 'copart_v2_report.json'}")
        print("→ Navegador abierto 20s para inspección manual...")
        await asyncio.sleep(20)
        await browser.close()


def _preview(data, depth=0, max_depth=2):
    """Resumen corto de un JSON sin imprimir megabytes."""
    pad = "        " + "  " * depth
    if isinstance(data, dict):
        keys = list(data.keys())
        out = []
        for k in keys[:15]:
            v = data[k]
            if isinstance(v, (dict, list)) and depth < max_depth:
                inner = _preview(v, depth + 1, max_depth)
                out.append(f"{pad}{k}: {inner.lstrip()}" if "\n" not in inner else f"{pad}{k}:\n{inner}")
            else:
                preview = repr(v)
                if len(preview) > 80:
                    preview = preview[:80] + "..."
                out.append(f"{pad}{k}: {preview}")
        return "\n".join(out)
    if isinstance(data, list):
        if not data:
            return f"{pad}[] (vacío)"
        head = f"{pad}[lista de {len(data)} items]"
        if depth < max_depth:
            inner = _preview(data[0], depth + 1, max_depth)
            return f"{head}\n{pad}primer item:\n{inner}"
        return head
    return f"{pad}{repr(data)[:80]}"


if __name__ == "__main__":
    asyncio.run(main())
