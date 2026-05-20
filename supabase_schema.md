# Supabase — Schema Lombardo Car

Comandos SQL para crear las tablas del proyecto. Pegar en **SQL Editor → New snippet**
en tu proyecto Supabase y correr **bloque por bloque** (de 1 a 5, en orden).

Todas las tablas llevan prefijo `datos_lombardo_car_` para identificación.

---

## 1. Tabla principal: vehículos activos

Captura los 99 campos del JSON de Copart. Los más usados van como columnas
indexadas; el resto se guarda en `raw_data JSONB` para no perder nada.

```sql
CREATE TABLE datos_lombardo_car_vehicles (
    -- Identificación
    lot_number          BIGINT       PRIMARY KEY,                -- ln (id único de Copart)
    vin                 TEXT,                                    -- fv (enmascarado: últimos 6 = ******)
    url_slug            TEXT,                                    -- ldu ("2004-toyota-camry-le-mo-st-louis")
    title               TEXT,                                    -- ld ("2004 TOYOTA CAMRY LE")

    -- Vehículo
    year                INTEGER,                                 -- lcy
    make                TEXT,                                    -- mkn ("TOYOTA")
    make_code           TEXT,                                    -- lmc ("TOYT")
    model               TEXT,                                    -- mmod ("CAMRY")
    model_group         TEXT,                                    -- lmg
    trim                TEXT,                                    -- ltd ("LE")
    body_style          TEXT,                                    -- bstl ("SEDAN 4D")
    vehicle_type        TEXT,                                    -- memberVehicleType
    color               TEXT,                                    -- clr
    engine              TEXT,                                    -- egn ("2.4L 4")
    cylinders           TEXT,                                    -- cy
    fuel_type           TEXT,                                    -- ft
    drivetrain          TEXT,                                    -- drv
    transmission        TEXT,                                    -- tmtp

    -- Condición / daño
    primary_damage      TEXT,                                    -- dd ("FRONT END")
    secondary_damage    TEXT,                                    -- sdd
    cert_code           TEXT,                                    -- lcc ("CERT-E")
    cert_description    TEXT,                                    -- lcd
    odometer            NUMERIC,                                 -- orr (puede venir 0)
    has_keys            BOOLEAN,                                 -- hk == 'YES' / 'NO'

    -- Subasta
    auction_date        TIMESTAMPTZ,                             -- lad (epoch ms convertido)
    auction_time        TEXT,                                    -- at ("12:00:00")
    auction_timezone    TEXT,                                    -- tz ("CDT")
    current_bid         NUMERIC,                                 -- dynamicLotDetails.currentBid
    sale_type           TEXT,                                    -- ess ("Pure Sale")
    currency            TEXT         DEFAULT 'USD',              -- cuc

    -- Ubicación
    country             TEXT,                                    -- locCountry
    state               TEXT,                                    -- locState ("MO")
    yard_name           TEXT,                                    -- syn ("MO - ST. LOUIS")
    yard_number         INTEGER,                                 -- ynumb

    -- Multimedia
    thumbnail_url       TEXT,                                    -- tims

    -- Pricing Lombardo (calculado/seteado por ellos)
    lombardo_price          NUMERIC,                             -- precio final que ofrece Lombardo
    lombardo_markup_amount  NUMERIC,                             -- aumento absoluto (USD)
    lombardo_markup_pct     NUMERIC,                             -- aumento porcentual

    -- JSON crudo y metadata
    raw_data            JSONB        NOT NULL,                   -- los 99 campos originales
    first_seen_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_seen_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Índices para queries del agente
CREATE INDEX dlc_idx_vehicles_make_model     ON datos_lombardo_car_vehicles (make, model);
CREATE INDEX dlc_idx_vehicles_year           ON datos_lombardo_car_vehicles (year);
CREATE INDEX dlc_idx_vehicles_state          ON datos_lombardo_car_vehicles (state);
CREATE INDEX dlc_idx_vehicles_auction_date   ON datos_lombardo_car_vehicles (auction_date);
CREATE INDEX dlc_idx_vehicles_current_bid    ON datos_lombardo_car_vehicles (current_bid);
CREATE INDEX dlc_idx_vehicles_body_style     ON datos_lombardo_car_vehicles (body_style);
CREATE INDEX dlc_idx_vehicles_last_seen      ON datos_lombardo_car_vehicles (last_seen_at);

-- Búsqueda libre (full-text) sobre title/make/model — útil para recomendaciones
CREATE INDEX dlc_idx_vehicles_fts ON datos_lombardo_car_vehicles
USING gin (
  to_tsvector('english',
    coalesce(title, '') || ' ' ||
    coalesce(make, '')  || ' ' ||
    coalesce(model, '') || ' ' ||
    coalesce(trim, '')  || ' ' ||
    coalesce(body_style, '')
  )
);
```

---

## 2. Tabla histórica: vehículos vendidos/removidos

Mismo schema que `vehicles` + `sold_at` y `final_bid`. El scraper mueve aquí
los lotes que dejan de aparecer en Copart.

```sql
CREATE TABLE datos_lombardo_car_vehicles_sold (
    lot_number          BIGINT       PRIMARY KEY,
    vin                 TEXT,
    url_slug            TEXT,
    title               TEXT,

    year                INTEGER,
    make                TEXT,
    make_code           TEXT,
    model               TEXT,
    model_group         TEXT,
    trim                TEXT,
    body_style          TEXT,
    vehicle_type        TEXT,
    color               TEXT,
    engine              TEXT,
    cylinders           TEXT,
    fuel_type           TEXT,
    drivetrain          TEXT,
    transmission        TEXT,

    primary_damage      TEXT,
    secondary_damage    TEXT,
    cert_code           TEXT,
    cert_description    TEXT,
    odometer            NUMERIC,
    has_keys            BOOLEAN,

    auction_date        TIMESTAMPTZ,
    auction_time        TEXT,
    auction_timezone    TEXT,
    final_bid           NUMERIC,                                 -- último currentBid antes de desaparecer
    sale_type           TEXT,
    currency            TEXT         DEFAULT 'USD',

    country             TEXT,
    state               TEXT,
    yard_name           TEXT,
    yard_number         INTEGER,

    thumbnail_url       TEXT,

    lombardo_price          NUMERIC,
    lombardo_markup_amount  NUMERIC,
    lombardo_markup_pct     NUMERIC,

    raw_data            JSONB        NOT NULL,
    first_seen_at       TIMESTAMPTZ  NOT NULL,                   -- copiado de la tabla activa
    last_seen_at        TIMESTAMPTZ  NOT NULL,                   -- última vez que apareció en scrape
    sold_at             TIMESTAMPTZ  NOT NULL DEFAULT NOW()      -- cuándo lo movimos aquí
);
-- Nota: días que estuvo activo se calcula en la query cuando se necesita:
--   SELECT (sold_at::date - first_seen_at::date) AS days_active FROM ...

CREATE INDEX dlc_idx_sold_make_model    ON datos_lombardo_car_vehicles_sold (make, model);
CREATE INDEX dlc_idx_sold_year          ON datos_lombardo_car_vehicles_sold (year);
CREATE INDEX dlc_idx_sold_state         ON datos_lombardo_car_vehicles_sold (state);
CREATE INDEX dlc_idx_sold_sold_at       ON datos_lombardo_car_vehicles_sold (sold_at);
```

---

## 3. Log de ejecuciones del scraper

Para saber si el cron está corriendo bien, cuánto tardó cada noche, y debuggear errores.

```sql
CREATE TABLE datos_lombardo_car_scrape_runs (
    id                  BIGSERIAL    PRIMARY KEY,
    started_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    finished_at         TIMESTAMPTZ,
    status              TEXT         NOT NULL DEFAULT 'running',  -- running | success | failed
    states_scraped      TEXT[],                                   -- ['CA','TX','FL',...]
    lots_fetched        INTEGER      DEFAULT 0,
    lots_inserted       INTEGER      DEFAULT 0,
    lots_updated        INTEGER      DEFAULT 0,
    lots_moved_to_sold  INTEGER      DEFAULT 0,
    error_message       TEXT,
    notes               TEXT,
    duration_seconds    INTEGER
);

CREATE INDEX dlc_idx_runs_started_at  ON datos_lombardo_car_scrape_runs (started_at DESC);
CREATE INDEX dlc_idx_runs_status      ON datos_lombardo_car_scrape_runs (status);
```

---

## 4. Trigger para mantener `updated_at` al día

Cada vez que el scraper actualice un lote (precio cambió, etc.), `updated_at` se refresca automático.

```sql
CREATE OR REPLACE FUNCTION datos_lombardo_car_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER dlc_trg_vehicles_updated_at
    BEFORE UPDATE ON datos_lombardo_car_vehicles
    FOR EACH ROW EXECUTE FUNCTION datos_lombardo_car_touch_updated_at();
```

---

## 5. Row Level Security (RLS)

Activamos RLS sin políticas en las tablas. Esto hace que:

- La **secret key** (`sb_secret_...`) que usa el scraper en DigitalOcean **bypasea RLS** → ve y escribe todo.
- La **publishable key** (`sb_publishable_...`) no ve **nada** por defecto → seguro si llega a filtrarse.

Más adelante, si el frontend o algún cliente público necesita lectura, agregamos
políticas específicas.

```sql
ALTER TABLE datos_lombardo_car_vehicles       ENABLE ROW LEVEL SECURITY;
ALTER TABLE datos_lombardo_car_vehicles_sold  ENABLE ROW LEVEL SECURITY;
ALTER TABLE datos_lombardo_car_scrape_runs    ENABLE ROW LEVEL SECURITY;
```

---

## Cómo ejecutar

1. Entrar al dashboard de Supabase → tu proyecto.
2. Sidebar izquierdo → **SQL Editor** → **New snippet**.
3. Pegar **bloque 1** (vehicles) → **Run**. Confirma "Success".
4. Repetir para bloques 2, 3, 4 y 5.
5. Sidebar → **Table Editor** → deberías ver las 3 tablas con prefijo `datos_lombardo_car_`.

## Verificación rápida

```sql
-- Ver que las tablas existen
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name LIKE 'datos_lombardo_car_%';

-- Ver índices creados
SELECT indexname FROM pg_indexes
WHERE indexname LIKE 'dlc_%'
ORDER BY indexname;
```

## Si necesitas revertir todo (cuidado, borra datos)

```sql
DROP TABLE IF EXISTS datos_lombardo_car_vehicles       CASCADE;
DROP TABLE IF EXISTS datos_lombardo_car_vehicles_sold  CASCADE;
DROP TABLE IF EXISTS datos_lombardo_car_scrape_runs    CASCADE;
DROP FUNCTION IF EXISTS datos_lombardo_car_touch_updated_at() CASCADE;
```
