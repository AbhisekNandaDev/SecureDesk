-- Run against an existing installation before using the updated application.
BEGIN;
ALTER TABLE users ADD COLUMN IF NOT EXISTS groups JSON NOT NULL DEFAULT '[]';
ALTER TABLE users ADD COLUMN IF NOT EXISTS support_departments JSON NOT NULL DEFAULT '[]';
-- Retire the old generic role without promoting legacy accounts.
UPDATE users SET user_type = 'employee' WHERE user_type = 'engineer';
ALTER TABLE users ALTER COLUMN user_type SET DEFAULT 'employee';
COMMIT;
