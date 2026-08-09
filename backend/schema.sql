CREATE TABLE IF NOT EXISTS public.route_searches (
    id BIGSERIAL PRIMARY KEY,
    start_id VARCHAR(80) NOT NULL,
    end_id VARCHAR(80) NOT NULL,
    fastest_route_id VARCHAR(40) NOT NULL,
    calmest_route_id VARCHAR(40) NOT NULL,
    route_source VARCHAR(20) NOT NULL,
    pedestrian_source VARCHAR(20) NOT NULL,
    selected_route_type VARCHAR(40),
    confidence VARCHAR(10),
    route_count INTEGER,
    used_historical_prediction BOOLEAN,
    prediction_confidence VARCHAR(10),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_route_searches_created_at
    ON public.route_searches (created_at DESC);
