CREATE VIRTUAL TABLE IF NOT EXISTS vectors_fts USING fts5(
    text,
    content='vectors',
    content_rowid='rowid',
    tokenize='unicode61'
);
CREATE TRIGGER IF NOT EXISTS vectors_ai AFTER INSERT ON vectors BEGIN
    INSERT INTO vectors_fts(rowid, text) VALUES (new.rowid, new.text);
END;
CREATE TRIGGER IF NOT EXISTS vectors_ad AFTER DELETE ON vectors BEGIN
    INSERT INTO vectors_fts(vectors_fts, rowid, text)
        VALUES ('delete', old.rowid, old.text);
END;
CREATE TRIGGER IF NOT EXISTS vectors_au AFTER UPDATE ON vectors BEGIN
    INSERT INTO vectors_fts(vectors_fts, rowid, text)
        VALUES ('delete', old.rowid, old.text);
    INSERT INTO vectors_fts(rowid, text) VALUES (new.rowid, new.text);
END;
