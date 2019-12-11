-- Initialize the database.
-- Drop any existing data and create empty tables.
-- AUTOINCREMENT changes to SERIAL 

DROP TABLE IF EXISTS usr CASCADE;
DROP TABLE IF EXISTS post CASCADE;

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
