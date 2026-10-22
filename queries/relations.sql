SELECT name,
       s.abbreviation,
       s.tigerweb_number,
       s.id,
       sg.state_id,
       sg.centroid,
       sg.boundary
FROM locations.states s
left join locations.state_geometries sg on s.id = sg.state_id ;


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