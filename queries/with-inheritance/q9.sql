SELECT * from cypher('lsqb', $$
MATCH (person1:Person)-[:KNOWS]-(person2:Person)-[:KNOWS]-(person3:Person)-[:HAS_INTEREST]->(tag:Tag)
WHERE NOT EXISTS((person1)-[:KNOWS]-(person3))
  AND id(person1) <> id(person3)
RETURN count(*) AS c
$$) AS (c agtype)
