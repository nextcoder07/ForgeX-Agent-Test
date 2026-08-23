import os
import re

page_dir = r"c:\Users\creat\OneDrive\Documents\iforgeu\anujfor\frontend\src\pages"

def refactor_file(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Add import
    if "useNavigate" not in content:
        content = re.sub(r'^(import .*?)$', r'\1\nimport { useNavigate, useParams } from "react-router-dom";', content, count=1, flags=re.MULTILINE)

    # Special interfaces
    content = re.sub(r'\s*onNavigate:\s*\(page:\s*PageId\)\s*=>\s*void;', '', content)
    
    # Remove from props destructuring (e.g., `{ onNavigate }` -> `{}`)
    content = re.sub(r'\{\s*onNavigate\s*\}', r'{}', content)
    content = re.sub(r'\{\s*onNavigate,\s*', r'{ ', content)
    content = re.sub(r',\s*onNavigate\s*\}', r' }', content)

    # Replace onNavigate('something') -> navigate('/something')
    content = re.sub(r'onNavigate\(\'([^\']+)\'\)', r'navigate("/\1")', content)
    content = re.sub(r'onNavigate\((step\.page)\)', r'navigate(`/${step.page}`)', content)

    # Component signature injections
    if "navigate(" in content and "const navigate = useNavigate();" not in content:
        content = re.sub(
            r'(export const [A-Za-z]+:.*?=>\s*\{)', 
            r'\1\n  const navigate = useNavigate();', 
            content
        )
        
    # Also for EvaluationRunPage we need jobId from useParams
    if "EvaluationRunPage" in path:
        if "const { jobId } = useParams();" not in content:
            content = re.sub(
                r'(export const EvaluationRunPage:.*?=>\s*\{)',
                r'\1\n  const { jobId } = useParams();',
                content
            )
        # Replace evaluationJobId with jobId
        content = re.sub(r'evaluationJobId\b', r'jobId', content)
        # Remove evaluationJobId from props
        content = re.sub(r'\{.*?jobId.*?\}', r'{}', content)
        content = re.sub(r'evaluationJobId\??:\s*string;', '', content)
        # Destructuring
        content = re.sub(r'\{\s*evaluationJobId\s*\}', r'{}', content)
        content = re.sub(r',\s*evaluationJobId', '', content)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

for file in os.listdir(page_dir):
    if file.endswith(".tsx"):
        refactor_file(os.path.join(page_dir, file))
