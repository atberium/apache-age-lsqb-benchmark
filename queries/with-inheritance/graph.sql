SET search_path = ag_catalog, "$user", public;

SELECT create_graph('lsqb');

SELECT create_vlabel('lsqb','Company');
SELECT create_vlabel('lsqb','University');
SELECT create_vlabel('lsqb','Continent');
SELECT create_vlabel('lsqb','Post');
SELECT create_vlabel('lsqb','Comment');
SELECT create_vlabel('lsqb','Message');
SELECT create_vlabel('lsqb','Country');
SELECT create_vlabel('lsqb','City');
SELECT create_vlabel('lsqb','Tag');
SELECT create_vlabel('lsqb','TagClass');
SELECT create_vlabel('lsqb','Forum');
SELECT create_vlabel('lsqb','Person');

ALTER TABLE lsqb."Comment" INHERIT lsqb."Message";
ALTER TABLE lsqb."Post"    INHERIT lsqb."Message";

SELECT create_elabel('lsqb','HAS_MEMBER');
SELECT create_elabel('lsqb','HAS_INTEREST');
SELECT create_elabel('lsqb','LIKES');
SELECT create_elabel('lsqb','KNOWS');
SELECT create_elabel('lsqb','REPLY_OF');
SELECT create_elabel('lsqb','HAS_TAG');
SELECT create_elabel('lsqb','IS_PART_OF');
SELECT create_elabel('lsqb','HAS_TYPE');
SELECT create_elabel('lsqb','HAS_CREATOR');
SELECT create_elabel('lsqb','IS_LOCATED_IN');
SELECT create_elabel('lsqb','CONTAINER_OF');

SELECT load_labels_from_file('lsqb', 'Company', 'Company.csv');
SELECT load_labels_from_file('lsqb', 'University', 'University.csv');
SELECT load_labels_from_file('lsqb', 'Continent', 'Continent.csv');
SELECT load_labels_from_file('lsqb', 'Country', 'Country.csv');
SELECT load_labels_from_file('lsqb', 'City', 'City.csv');
SELECT load_labels_from_file('lsqb', 'Forum', 'Forum.csv');
SELECT load_labels_from_file('lsqb', 'Person', 'Person.csv');
SELECT load_labels_from_file('lsqb', 'Tag', 'Tag.csv');
SELECT load_labels_from_file('lsqb', 'TagClass', 'TagClass.csv');
SELECT load_labels_from_file('lsqb', 'Post', 'Post.csv');
SELECT load_labels_from_file('lsqb', 'Comment', 'Comment.csv');

SELECT load_edges_from_file('lsqb', 'HAS_TAG', 'Comment_hasTag_Tag.csv');
SELECT load_edges_from_file('lsqb', 'HAS_TAG', 'Post_hasTag_Tag.csv');
SELECT load_edges_from_file('lsqb', 'HAS_MEMBER', 'Forum_hasMember_Person.csv');
SELECT load_edges_from_file('lsqb', 'HAS_INTEREST', 'Person_hasInterest_Tag.csv');
SELECT load_edges_from_file('lsqb', 'LIKES', 'Person_likes_Comment.csv');
SELECT load_edges_from_file('lsqb', 'LIKES', 'Person_likes_Post.csv');
SELECT load_edges_from_file('lsqb', 'KNOWS', 'Person_knows_Person.csv');
SELECT load_edges_from_file('lsqb', 'IS_PART_OF', 'City_isPartOf_Country.csv');
SELECT load_edges_from_file('lsqb', 'HAS_TYPE', 'Tag_hasType_TagClass.csv');
SELECT load_edges_from_file('lsqb', 'HAS_CREATOR', 'Post_hasCreator_Person.csv');
SELECT load_edges_from_file('lsqb', 'HAS_CREATOR', 'Comment_hasCreator_Person.csv');
SELECT load_edges_from_file('lsqb', 'REPLY_OF', 'Comment_replyOf_Comment.csv');
SELECT load_edges_from_file('lsqb', 'REPLY_OF', 'Comment_replyOf_Post.csv');
SELECT load_edges_from_file('lsqb', 'IS_LOCATED_IN', 'Person_isLocatedIn_City.csv');
SELECT load_edges_from_file('lsqb', 'CONTAINER_OF', 'Forum_containerOf_Post.csv');