CREATE TABLE IF NOT EXISTS route_searches (
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
    ON route_searches (created_at DESC);

CREATE TABLE IF NOT EXISTS sensor_locations (
    location_id VARCHAR(80) PRIMARY KEY,
    sensor_name VARCHAR(200) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    location_type VARCHAR(80),
    status VARCHAR(30),
    data_source VARCHAR(80),
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_sensor_locations_status
    ON sensor_locations (status);

CREATE TABLE IF NOT EXISTS pedestrian_readings (
    reading_id BIGSERIAL PRIMARY KEY,
    location_id VARCHAR(80) NOT NULL REFERENCES sensor_locations(location_id),
    sensed_at TIMESTAMPTZ NOT NULL,
    direction_1 INTEGER CHECK (direction_1 IS NULL OR direction_1 >= 0),
    direction_2 INTEGER CHECK (direction_2 IS NULL OR direction_2 >= 0),
    total_count INTEGER NOT NULL CHECK (total_count >= 0),
    interval_minutes INTEGER NOT NULL CHECK (interval_minutes > 0),
    source VARCHAR(80) NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_pedestrian_reading_identity
        UNIQUE (location_id, sensed_at, interval_minutes, source)
);

CREATE INDEX IF NOT EXISTS idx_pedestrian_readings_sensed_at
    ON pedestrian_readings (sensed_at);
CREATE INDEX IF NOT EXISTS idx_pedestrian_readings_location_time
    ON pedestrian_readings (location_id, sensed_at);

CREATE TABLE IF NOT EXISTS sensor_historical_profiles (
    location_id VARCHAR(80) NOT NULL REFERENCES sensor_locations(location_id),
    day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    hour_of_day INTEGER NOT NULL CHECK (hour_of_day BETWEEN 0 AND 23),
    mean_count DOUBLE PRECISION NOT NULL CHECK (mean_count >= 0),
    median_count DOUBLE PRECISION NOT NULL CHECK (median_count >= 0),
    percentile_80 DOUBLE PRECISION NOT NULL CHECK (percentile_80 >= 0),
    std_dev DOUBLE PRECISION NOT NULL CHECK (std_dev >= 0),
    sample_count INTEGER NOT NULL CHECK (sample_count >= 0),
    generated_at TIMESTAMPTZ NOT NULL,
    source_period_start DATE NOT NULL,
    source_period_end DATE NOT NULL,
    data_version VARCHAR(40) NOT NULL,
    PRIMARY KEY (location_id, day_of_week, hour_of_day),
    CHECK (source_period_end >= source_period_start)
);

CREATE INDEX IF NOT EXISTS idx_profiles_day_hour
    ON sensor_historical_profiles (day_of_week, hour_of_day);

CREATE TABLE IF NOT EXISTS refuges (
    refuge_id VARCHAR(80) PRIMARY KEY,
    name VARCHAR(160) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    refuge_type VARCHAR(80) NOT NULL,
    indoor_outdoor VARCHAR(40),
    has_seating BOOLEAN,
    is_shaded BOOLEAN,
    lighting_level VARCHAR(80),
    opening_hours VARCHAR(200),
    short_description VARCHAR(300) NOT NULL,
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    data_source VARCHAR(80),
    last_checked_at TIMESTAMPTZ
);
