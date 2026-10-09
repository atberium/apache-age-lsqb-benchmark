SELECT * from cypher('lsqb', $$
MATCH
  (person1:Person)-[:KNOWS]-(person2:Person),
  (person1)<-[:HAS_CREATOR]-(comment:Message {type: 'Comment'})-[:REPLY_OF]->(post:Message {type: 'Post'})-[:HAS_CREATOR]->(person2)
RETURN count(*) AS c
$$) AS (c agtype)
