SELECT name,
       s.abbreviation,
       s.tigerweb_number,
       s.id,
       sg.state_id,
       sg.centroid,
       sg.boundary
FROM locations.states s
left join locations.state_geometries sg on s.id = sg.state_id ;


SELECT c.name,
       s.abbreviation,
       c.state_id,
       c.id,
       c.name,
       c.tigerweb_number,
       cg.city_id,
       cg.centroid,
       cg.boundary
FROM locations.cities c
left join locations.city_geometries cg on c.id = cg.city_id
left join locations.states s on s.id = c.state_id ;


select count(*)
from locations.cities;


SELECT name,
       s.abbreviation,
       s.tigerweb_number,
       s.id,
       sg.state_id,
       sg.centroid,
       sg.boundary,
       ST_AsText(sg.centroid) AS centroid,
       ST_AsText(sg.boundary) AS boundaries,
       ST_AsGeoJSON(sg.centroid) AS centroid_geojson,
       ST_AsGeoJSON(sg.boundary) AS boundaries_geojson
FROM locations.states s
left join locations.state_geometries sg on s.id = sg.state_id
where s.abbreviation = 'NY' ;