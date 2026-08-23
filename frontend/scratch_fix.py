import os
import re

page_dir = r"c:\Users\creat\OneDrive\Documents\iforgeu\anujfor\frontend\src\pages"

def fix_file(path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # If it uses navigate but doesn't define it
    if "navigate(" in content and "const navigate = useNavigate();" not in content:
        # Find export const ... = (...) => {
        # and insert const navigate = useNavigate(); right after
        content = re.sub(
            r'(export const [A-Za-z]+:.*?=>\s*\{)', 
            r'\1\n  const navigate = useNavigate();', 
            content
        )
        
    # Also for EvaluationRunPage we need jobId from useParams
    if "EvaluationRunPage" in path and "const { jobId } = useParams();" not in content:
        content = re.sub(
            r'(export const EvaluationRunPage:.*?=>\s*\{)',
            r'\1\n  const { jobId } = useParams();\n  const navigate = useNavigate();\n',
            content
        )
        # And replace evaluationJobId with jobId
        content = re.sub(r'evaluationJobId\b', r'jobId', content)
        # Remove evaluationJobId from props
        content = re.sub(r'\{.*?jobId.*?\}', r'{}', content)
        
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

for file in os.listdir(page_dir):
    if file.endswith(".tsx"):
        fix_file(os.path.join(page_dir, file))
