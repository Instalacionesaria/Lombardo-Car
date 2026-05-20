"""
Scraper Copart — produce datos para datos_lombardo_car_vehicles.

Estrategia: iteramos por marca (facet MAKE) porque Copart no expone un facet
de estado directo. Filter usa formato Solr: {"MAKE": ['lot_make_desc:"TOYOTA"']}.
Después en el mapper descartamos lotes que no son de USA.

Modo de uso:
  python copart_scraper.py                          # default: TOYOTA (test)
  python copart_scraper.py --makes "TOYOTA,HONDA"   # subset
  python copart_scraper.py --all-makes              # todos los makes (extrae de facet)
  python copart_scraper.py --max-pages 5            # cap de páginas por make (testing)
"""

import argparse
import asyncio
import json as _json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from playwright.async_api import async_playwright

from db import (
    finish_scrape_run,
    move_stale_to_sold,
    start_scrape_run,
    upsert_vehicles,
)
from mapper import map_lot_to_row

load_dotenv(Path(__file__).parent / ".env")

PAGE_SIZE = int(os.environ.get("COPART_PAGE_SIZE", "100"))
HEADLESS = os.environ.get("COPART_HEADLESS", "False").lower() == "true"

LANDING_URL = "https://www.copart.com/lotSearchResults?free=true&query="
API_URL = "https://www.copart.com/public/lots/search-results"


def build_payload(make: str, page: int) -> dict:
    """POST body: filter por marca con query Solr lot_make_desc:"<MAKE>"."""
    return {
        "query": [],
        "filter": {"MAKE": [f'lot_make_desc:"{make}"']},
        "sort": [
            "salelight_priority asc",
            "member_damage_group_priority asc",
            "auction_date_type desc",
            "auction_date_utc asc",
        ],
        "page": page,
        "size": PAGE_SIZE,
        "start": page * PAGE_SIZE,
        "watchListOnly": False,
        "freeFormSearch": False,
        "hideImages": False,
        "defaultSort": False,
        "specificRowProvided": False,
        "displayName": "",
        "searchName": "",
        "backUrl": "",
        "includeTagByField": {},
        "rawParams": {},
    }


async def fetch_post(page, payload: dict) -> dict:
    # Headers idénticos al probe diag que funciona consistentemente.
    res = await page.evaluate(
        """async ({url, body}) => {
            const r = await fetch(url, {
                method: 'POST', credentials: 'include',
                headers: {'Content-Type':'application/json','X-Requested-With':'XMLHttpRequest'},
                body: JSON.stringify(body),
            });
            return {status: r.status, body: await r.text()};
        }""",
        {"url": API_URL, "body": payload},
    )
    return res


async def discover_makes(page, retries: int = 3) -> list[str]:
    """Extrae todos los makes desde el facet MAKE de una query inicial.
    Retry porque a veces la primera request post-Kasada vuelve vacía."""
    payload = {
        "query": [],
        "filter": {"YEAR": ['lot_year:"2024" OR lot_year:"2025" OR lot_year:"2026"']},
        "sort": ["salelight_priority asc", "auction_date_utc asc"],
        "page": 0, "size": 1, "start": 0,
        "watchListOnly": False, "freeFormSearch": False,
        "hideImages": False, "defaultSort": False,
        "specificRowProvided": False,
        "displayName": "", "searchName": "", "backUrl": "",
        "includeTagByField": {}, "rawParams": {},
    }

    for attempt in range(retries):
        res = await fetch_post(page, payload)
        if res["status"] != 200 or not res["body"]:
            print(f"   discover_makes attempt {attempt+1}: status={res['status']} body_len={len(res['body'])}")
            await asyncio.sleep(3)
            continue
        try:
            data = _json.loads(res["body"])
        except _json.JSONDecodeError:
            print(f"   discover_makes attempt {attempt+1}: body no es JSON (preview: {res['body'][:100]!r})")
            await asyncio.sleep(3)
            continue

        facets = data.get("data", {}).get("results", {}).get("facetFields", []) or []
        make_facet = next((f for f in facets if f.get("quickPickCode") == "MAKE"), None)
        if not make_facet:
            print(f"   discover_makes attempt {attempt+1}: facet MAKE no encontrado, retrying...")
            await asyncio.sleep(3)
            continue

        makes = []
        for c in make_facet.get("facetCounts") or []:
            q = c.get("query", "")
            if '"' in q:
                makes.append(q.split('"')[1])
        return makes

    return []


async def scrape_make(page, make: str, max_pages: int | None) -> tuple[int, int]:
    """Pagina todos los lotes de una marca. Devuelve (fetched, upserted)."""
    fetched = 0
    upserted = 0
    page_idx = 0

    while True:
        if max_pages is not None and page_idx >= max_pages:
            print(f"   [{make}] cap de {max_pages} páginas alcanzado, paro.")
            break

        payload = build_payload(make, page_idx)
        res = await fetch_post(page, payload)

        if res["status"] != 200:
            print(f"   [{make}] HTTP {res['status']} en página {page_idx} — abortando")
            break

        data = _json.loads(res["body"])
        results = (data.get("data") or {}).get("results") or {}
        content = results.get("content") or []
        total = results.get("totalElements", 0)

        if page_idx == 0:
            print(f"   [{make}] total declarado: {total}")

        if not content:
            break

        # Filtrar solo USA antes de upsert
        usa_lots = [lot for lot in content if (lot.get("locCountry") or "").upper() == "USA"]

        if usa_lots:
            now_iso = datetime.now(timezone.utc).isoformat()
            rows = []
            for lot in usa_lots:
                row = map_lot_to_row(lot)
                row["first_seen_at"] = now_iso
                rows.append(row)
            n = upsert_vehicles(rows)
            upserted += n

        fetched += len(content)
        non_usa = len(content) - len(usa_lots)
        non_usa_note = f" (-{non_usa} no-USA)" if non_usa else ""

        print(f"   [{make}] página {page_idx}: +{len(usa_lots)}{non_usa_note}  total={fetched}/{total}")

        if len(content) < PAGE_SIZE:
            break

        page_idx += 1
        await asyncio.sleep(0.5)

    return fetched, upserted


async def main(makes: list[str] | None, all_makes: bool, max_pages: int | None, move_sold: bool):
    run_id = start_scrape_run(notes=f"makes={makes} all_makes={all_makes}")
    print(f"→ scrape_run iniciado: id={run_id}")

    total_fetched = 0
    total_upserted = 0
    total_moved = 0
    error_msg = None
    status = "success"
    actual_makes = makes or []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=HEADLESS,
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
        print(f"→ Cargando landing para resolver Kasada...")
        await page.goto(LANDING_URL, wait_until="domcontentloaded", timeout=60000)
        print(f"   esperando 15s para que Kasada resuelva...")
        await asyncio.sleep(15)

        # Warmup con retry con backoff exponencial
        print(f"→ Warmup query...")
        for warmup_attempt in range(5):
            warm = await fetch_post(page, build_payload("TOYOTA", 0))
            if warm["status"] == 200 and warm["body"]:
                print(f"   warmup OK (intento {warmup_attempt+1})")
                break
            backoff = 10 * (warmup_attempt + 1)
            print(f"   warmup intento {warmup_attempt+1}: status={warm['status']}, esperando {backoff}s...")
            await asyncio.sleep(backoff)
        else:
            raise RuntimeError("Kasada no resolvió después de 5 intentos — IP probablemente penalizada, esperar 10-15 min")
        await asyncio.sleep(2)

        try:
            if all_makes:
                print("→ Descubriendo makes desde facet MAKE...")
                actual_makes = await discover_makes(page)
                print(f"   encontrados: {len(actual_makes)} makes")
                if not actual_makes:
                    raise RuntimeError("No se descubrió ningún make")

            print(f"→ Makes a scrapear: {len(actual_makes)}")

            for make in actual_makes:
                fetched, upserted = await scrape_make(page, make, max_pages)
                total_fetched += fetched
                total_upserted += upserted

            if move_sold:
                print(f"→ Moviendo lotes desaparecidos a vehicles_sold...")
                total_moved = move_stale_to_sold(threshold_hours=6)
                print(f"   movidos: {total_moved}")

        except Exception as e:
            status = "failed"
            error_msg = f"{type(e).__name__}: {e}"
            print(f"\n! Error: {error_msg}")
        finally:
            await browser.close()

    finish_scrape_run(
        run_id,
        status=status,
        states_scraped=actual_makes,  # reusamos el campo (array) para guardar makes
        lots_fetched=total_fetched,
        lots_inserted=total_upserted,
        lots_moved_to_sold=total_moved,
        error_message=error_msg,
    )
    print(f"\n✓ scrape_run cerrado | fetched={total_fetched} upserted={total_upserted} moved={total_moved}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--makes", default="TOYOTA",
                        help="Makes separados por coma (default: TOYOTA)")
    parser.add_argument("--all-makes", action="store_true",
                        help="Descubre y scrapea todos los makes")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Cap de páginas por make (útil en pruebas)")
    parser.add_argument("--no-move-sold", action="store_true",
                        help="No mover lotes a vehicles_sold")
    args = parser.parse_args()

    makes = None if args.all_makes else [m.strip().upper() for m in args.makes.split(",")]
    asyncio.run(main(makes, args.all_makes, args.max_pages, move_sold=not args.no_move_sold))
