SELECT name,
       s.abbreviation,
       s.tigerweb_number,
       s.id,
       sg.state_id,
       sg.centroid,
       sg.boundary
FROM locations.states s
left join locations.state_geometries sg 
on s.id = sg.state_id
;