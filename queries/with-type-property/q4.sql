SELECT * from cypher('lsqb', $$
MATCH (:Tag)<-[:HAS_TAG]-(message:Message)-[:HAS_CREATOR]->(creator:Person),
  (message)<-[:LIKES]-(liker:Person),
  (message)<-[:REPLY_OF]-(comment:Message {type: 'Comment'})
RETURN count(*) AS c
$$) AS (c agtype)
