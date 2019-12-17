-- Initialize the database.
-- Drop any existing data and create empty tables.
-- AUTOINCREMENT changes to SERIAL 

DROP TABLE IF EXISTS usr CASCADE;
DROP TABLE IF EXISTS post CASCADE;
DROP TABLE IF EXISTS tag CASCADE;
DROP TABLE IF EXISTS post_tag CASCADE;

CREATE TABLE usr (
  id SERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  pass TEXT NOT NULL
);

CREATE TABLE post (
  id SERIAL PRIMARY KEY,
  author_id INTEGER NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  FOREIGN KEY (author_id) REFERENCES usr (id)
);

CREATE INDEX idx_post_id ON post (id);

CREATE TABLE tag (
  id SERIAL PRIMARY KEY,
  title TEXT UNIQUE NOT NULL,
  slug TEXT UNIQUE NOT NULL
);

CREATE TABLE post_tag (
  post_id INTEGER NOT NULL,
  tag_id INTEGER NOT NULL,
  FOREIGN KEY (post_id) REFERENCES post (id),
  FOREIGN KEY (tag_id) REFERENCES tag (id)
);
