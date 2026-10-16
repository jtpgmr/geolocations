WITH state_points AS (
    SELECT
        abbreviation,
        geo_point::geography AS geog
    FROM locations.states
    WHERE abbreviation IN ('NY', 'NJ')
)
SELECT
    a.abbreviation AS state_a,
    b.abbreviation AS state_b,
    ST_Distance(a.geog, b.geog) AS distance_meters,
    ST_Distance(a.geog, b.geog) / 1609.344 AS distance_miles
FROM state_points a
JOIN state_points b ON a.abbreviation = 'NY' AND b.abbreviation = 'NJ';

-- Cartesian-style ordering POINT(longitutde, latitude)

SELECT name,
       ST_AsText(geo_point) as cartesian_coordinate,
       ST_Y(geo_point) AS latitude,
       ST_X(geo_point) AS longitude
FROM locations.states -- WHERE abbreviation IN ('NJ',
--                        'NY')
 ;

WITH coordinates as
    (SELECT name,
            abbreviation,
            ST_Y(geo_point) AS latitude,
            ST_X(geo_point) AS longitude
     FROM locations.states
     WHERE abbreviation IN ('NJ',
                            'NY')),
     gps_coordinates as
    (select name,
            abbreviation,
            ABS(latitude) || CASE
                                 WHEN latitude >= 0 THEN ' N'
                                 ELSE ' S'
                             END as gps_latitude,
                             ABS(longitude) || CASE
                                                   WHEN longitude >= 0 THEN ' E'
                                                   ELSE ' W'
                                               END gps_longitude
     FROM coordinates)
select gps_latitude,
       gps_longitude,
       gps_latitude || ',' || ' ' || gps_longitude as gps_location
from gps_coordinates ;

-- TODO: Implement location tables for `state_polygons` and `city_polygons`
SELECT
    s.id               AS state_id,
    s.name             AS state_name,
    s.abbreviation     AS state_abbr,
    s.tigerweb_number  AS state_fips,
    ST_X(s.geo_point)  AS state_lon,
    ST_Y(s.geo_point)  AS state_lat,

    c.id               AS city_id,
    c.name             AS city_name,
    c.tigerweb_number  AS city_geoid,
    ST_X(c.geo_point)  AS city_lon,
    ST_Y(c.geo_point)  AS city_lat,

    -- Great‑circle distance in metres (more accurate than plain Euclidean for lat/long)
    ST_DistanceSphere(s.geo_point, c.geo_point) AS dist_metres,

    -- Simple pass/fail flag – adjust the threshold as you see fit.
    CASE
        WHEN ST_DistanceSphere(s.geo_point, c.geo_point) < 500000   -- 500 km ≈ 5°
        THEN 'OK'
        ELSE 'TOO_FAR'
    END AS geo_check
FROM locations.states   AS s
JOIN locations.cities   AS c
  ON c.state_id = s.id;



-- How many cities are in each state, and what is the average geographic center of those cities?
SELECT
    s.abbreviation,
    s.name AS state_name,
    COUNT(c.id) AS city_count,
    -- Option 1: average of coordinates
    AVG(ST_X(c.geo_point)) AS avg_longitude,
    AVG(ST_Y(c.geo_point)) AS avg_latitude
    -- Option 2: centroid of collected points (uncomment to use)
    -- ST_X(ST_Centroid(ST_Collect(c.geo_point))) AS avg_longitude,
    -- ST_Y(ST_Centroid(ST_Collect(c.geo_point))) AS avg_latitude
FROM locations.states s
LEFT JOIN locations.cities c ON c.state_id = s.id
GROUP BY s.abbreviation, s.name
ORDER BY city_count DESC;