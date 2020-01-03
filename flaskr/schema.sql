-- Initialize the database.
-- Drop any existing data and create empty tables.
-- AUTOINCREMENT changes to SERIAL 

DROP TABLE IF EXISTS usr CASCADE;
DROP TABLE IF EXISTS post CASCADE;
DROP TABLE IF EXISTS tag CASCADE;
DROP TABLE IF EXISTS post_tag CASCADE;
DROP TABLE IF EXISTS post_comment CASCADE;

CREATE TABLE usr (
  id TEXT PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  email TEXT UNIQUE NOT NULL,
  pass TEXT,
  profile_pic TEXT NOT NULL,
  about TEXT,
  username_slug TEXT
);

CREATE TABLE post (
  id BIGSERIAL PRIMARY KEY,
  author_id TEXT NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  thank_count INTEGER NOT NULL,
  FOREIGN KEY (author_id) REFERENCES usr (id)
);

CREATE INDEX idx_post_id ON post (id);

CREATE TABLE tag (
  id BIGSERIAL PRIMARY KEY,
  title TEXT UNIQUE NOT NULL,
  slug TEXT UNIQUE NOT NULL
);

CREATE TABLE post_tag (
  post_id BIGINT NOT NULL,
  tag_id BIGINT NOT NULL,
  FOREIGN KEY (post_id) REFERENCES post (id),
  FOREIGN KEY (tag_id) REFERENCES tag (id)
);

CREATE TABLE post_comment (
  id BIGSERIAL PRIMARY KEY,
  author_id TEXT NOT NULL, 
  body TEXT NOT NULL,
  created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  post_id BIGINT NOT NULL,
  FOREIGN KEY (post_id) REFERENCES post (id)
);
