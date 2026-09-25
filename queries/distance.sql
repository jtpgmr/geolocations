WITH distances AS
    (SELECT ST_Distance(a.geo_location::geography, b.geo_location::geography) AS distance_meters
     FROM locations.states a
     JOIN locations.states b ON a.abbreviation = 'NY'
     AND b.abbreviation = 'NJ')
SELECT distance_meters,
       distance_meters / 1609.344 AS distance_miles
FROM distances;

-- Cartesian-style ordering POINT(longitutde, latitude)

SELECT name,
       ST_AsText(geo_location) as cartesian_coordinate,
       ST_Y(geo_location) AS latitude,
       ST_X(geo_location) AS longitude
FROM locations.states
WHERE abbreviation IN ('NJ',
                       'NY');

WITH coordinates as
    (SELECT name,
            abbreviation,
            ST_Y(geo_location) AS latitude,
            ST_X(geo_location) AS longitude
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