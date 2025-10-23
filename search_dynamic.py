import os
import re

def search_dynamic_access(directory):
    patterns = [
        r'getattr\([^,]+,\s*[\'\"](.*?check.*action.*filter.*applied.*?)[\'\"]',
        r'hasattr\([^,]+,\s*[\'\"](.*?check.*action.*filter.*applied.*?)[\'\"]',
        r'setattr\([^,]+,\s*[\'\"](.*?check.*action.*filter.*applied.*?)[\'\"]',
        r'delattr\([^,]+,\s*[\'\"](.*?check.*action.*filter.*applied.*?)[\'\"]',
        r'self\.__dict__\[[\'\"](.*?check.*action.*filter.*applied.*?)[\'\"]',
        r'vars\([^)]+\)\[[\'\"](.*?check.*action.*filter.*applied.*?)[\'\"]'
    ]
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    for pattern in patterns:
                        matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                        for match in matches:
                            line_num = content[:match.start()].count('\n') + 1
                            print(f'{file_path}:{line_num}: {match.group(0)}')
                            
                except Exception as e:
                    continue

if __name__ == "__main__":
    search_dynamic_access('src')