-- MyAvatar Credit System - PostgreSQL Migration
-- Run this on your PostgreSQL production database

-- Step 1: Add credit columns to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS credits_remaining INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS trial_end_date TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS total_credits_purchased INTEGER DEFAULT 0;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_trial_used BOOLEAN DEFAULT FALSE;

-- Step 2: Create credit transactions table
CREATE TABLE IF NOT EXISTS credit_transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    transaction_type VARCHAR(50) NOT NULL, -- 'purchase', 'admin_grant', 'usage', 'bonus', 'trial_start'
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_admin_id INTEGER, -- If granted by admin
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (created_by_admin_id) REFERENCES users (id)
);

-- Step 3: Create credit packages table
CREATE TABLE IF NOT EXISTS credit_packages (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    credits INTEGER NOT NULL,
    price_usd DECIMAL(10, 2) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Step 4: Insert default credit packages (only if table is empty)
INSERT INTO credit_packages (name, credits, price_usd) 
SELECT 'Starter Pack', 10, 4.99
WHERE NOT EXISTS (SELECT 1 FROM credit_packages);

INSERT INTO credit_packages (name, credits, price_usd) 
SELECT 'Popular Pack', 50, 19.99
WHERE NOT EXISTS (SELECT 1 FROM credit_packages WHERE name = 'Popular Pack');

INSERT INTO credit_packages (name, credits, price_usd) 
SELECT 'Pro Pack', 150, 49.99
WHERE NOT EXISTS (SELECT 1 FROM credit_packages WHERE name = 'Pro Pack');

INSERT INTO credit_packages (name, credits, price_usd) 
SELECT 'Bulk Pack', 500, 149.99
WHERE NOT EXISTS (SELECT 1 FROM credit_packages WHERE name = 'Bulk Pack');

-- Step 5: Set trial end date for existing users (14 days from now)
UPDATE users 
SET trial_end_date = CURRENT_TIMESTAMP + INTERVAL '14 days'
WHERE trial_end_date IS NULL AND created_at > CURRENT_TIMESTAMP - INTERVAL '1 day';

-- Step 6: Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_credit_transactions_user_id ON credit_transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_credit_transactions_type ON credit_transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_users_trial_end ON users(trial_end_date);

-- Step 7: Create admin activity log
CREATE TABLE IF NOT EXISTS admin_activities (
    id SERIAL PRIMARY KEY,
    admin_id INTEGER NOT NULL,
    action_type VARCHAR(50) NOT NULL, -- 'grant_credits', 'create_user', 'modify_user'
    target_user_id INTEGER,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (admin_id) REFERENCES users (id),
    FOREIGN KEY (target_user_id) REFERENCES users (id)
);