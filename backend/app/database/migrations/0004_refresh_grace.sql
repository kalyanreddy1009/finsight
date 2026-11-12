-- Remember the outgoing refresh token so a just-rotated token (double-fired refresh, second tab)
-- can be told apart from a genuinely replayed one.
ALTER TABLE devices ADD COLUMN prev_refresh_token_hash TEXT;
ALTER TABLE devices ADD COLUMN refresh_rotated_at TEXT;
