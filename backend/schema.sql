CREATE TABLE IF NOT EXISTS route_searches (
    id BIGSERIAL PRIMARY KEY,
    start_id VARCHAR(80) NOT NULL,
    end_id VARCHAR(80) NOT NULL,
    fastest_route_id VARCHAR(40) NOT NULL,
    calmest_route_id VARCHAR(40) NOT NULL,
    route_source VARCHAR(20) NOT NULL,
    pedestrian_source VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_route_searches_created_at
    ON route_searches (created_at DESC);

