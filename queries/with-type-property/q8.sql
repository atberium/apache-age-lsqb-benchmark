SELECT * from cypher('lsqb', $$
MATCH (tag1:Tag)<-[:HAS_TAG]-(message:Message)<-[:REPLY_OF]-(comment:Message {type: 'Comment'})-[:HAS_TAG]->(tag2:Tag)
WHERE NOT EXISTS((comment)-[:HAS_TAG]->(tag1))
  AND id(tag1) <> id(tag2)
RETURN count(*) AS c
$$) AS (c agtype)
