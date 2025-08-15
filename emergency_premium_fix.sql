-- EMERGENCY: Fix premium status corruption for ALL premium users
-- CRITICAL: Multiple premium customers showing as "Trial" in database
-- BUSINESS RULE: Mogens, Lars-Christian, Admin, and 7-day trial users should ALL be premium

-- 1. Fix Mogens (User ID: 3) - Owner/Premium
UPDATE users 
SET subscription_tier = 'premium', 
    is_premium = true,
    sms_notifications = true,
    phone_number = '30604639',
    country_code = '+45'
WHERE id = 3;

-- 2. Find and fix Lars-Christian
SELECT id, name, email, subscription_tier, is_premium 
FROM users 
WHERE name ILIKE '%lars%' OR name ILIKE '%christian%' OR email ILIKE '%lars%' OR email ILIKE '%christian%';

-- Fix Lars-Christian (update after finding ID)
UPDATE users 
SET subscription_tier = 'premium', 
    is_premium = true,
    sms_notifications = true
WHERE name ILIKE '%lars%' OR name ILIKE '%christian%' OR email ILIKE '%lars%' OR email ILIKE '%christian%';

-- 3. Fix Admin users
UPDATE users 
SET subscription_tier = 'premium', 
    is_premium = true,
    sms_notifications = true
WHERE is_admin = true OR role = 'admin';

-- 4. BUSINESS RULE: 7-day trial users should have premium features during trial
-- Set all recent users (last 7 days) to premium during trial period
UPDATE users 
SET subscription_tier = 'premium', 
    is_premium = true,
    sms_notifications = true
WHERE created_at >= NOW() - INTERVAL '7 days';

-- AUDIT: Find ALL users who might be affected
SELECT id, name, email, subscription_tier, is_premium, created_at
FROM users 
WHERE subscription_tier = 'trial' 
ORDER BY created_at DESC;

-- VERIFICATION: Check the fixes
SELECT id, name, email, subscription_tier, is_premium, sms_notifications, phone_number
FROM users 
WHERE id IN (3) OR name ILIKE '%lars%' OR name ILIKE '%christian%';
