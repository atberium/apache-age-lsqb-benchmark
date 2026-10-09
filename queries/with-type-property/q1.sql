SELECT * from cypher('lsqb', $$
MATCH (:Country)<-[:IS_PART_OF]-(:City)<-[:IS_LOCATED_IN]-(:Person)<-[:HAS_MEMBER]-(:Forum)-[:CONTAINER_OF]->(:Message {type: 'Post'})<-[:REPLY_OF]-(:Message {type: 'Comment'})-[:HAS_TAG]->(:Tag)-[:HAS_TYPE]->(:TagClass)
RETURN count(*) AS c
$$) AS (c agtype)
