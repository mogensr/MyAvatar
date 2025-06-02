import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('if not avatar.get("heygen_avatar_id"):', 'if not avatar["heygen_avatar_id"]:')

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed!')
