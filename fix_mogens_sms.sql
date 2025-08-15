-- Fix Mogens' SMS notification issues
-- User ID: 3 (MogensR)

-- 1. Update premium status from 'trial' to 'premium'
UPDATE users 
SET subscription_tier = 'premium', 
    is_premium = true
WHERE id = 3;

-- 2. Enable SMS notifications
UPDATE users 
SET sms_notifications = true
WHERE id = 3;

-- 3. Ensure phone number and country code are set
UPDATE users 
SET phone_number = '30604639',
    country_code = '+45'
WHERE id = 3;

-- 4. Verify the changes
SELECT id, name, email, subscription_tier, is_premium, sms_notifications, 
       phone_number, country_code
FROM users 
WHERE id = 3;
