INSERT INTO usr (id,username,email,profile_pic)
VALUES
  (1,'test','user@example.com','test'),
  (2,'other','other@example.com','test');

INSERT INTO post (title, body, author_id, created, thank_count, title_slug)
VALUES
  ('test title', 'test body', 1, '2019-01-01 00:00:00', 0, 'test-title');
