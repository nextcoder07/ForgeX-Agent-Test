"""
Dynamic Dependency Manager & Auto-Installer for Sandbox Execution.
Detects, verifies, and installs missing Python libraries temporarily on-the-fly
so agent execution in the sandbox never fails due to missing modules or packages.
"""

from __future__ import annotations

import os
import re
import sys
import ast
import logging
import subprocess
from typing import List, Set, Optional, Dict
from app.models.agent import AgentRecord

logger = logging.getLogger(__name__)

# Common import module name to PyPI package name mappings
IMPORT_TO_PACKAGE_MAP: Dict[str, str] = {
    "dotenv": "python-dotenv",
    "bs4": "beautifulsoup4",
    "yaml": "pyyaml",
    "cv2": "opencv-python",
    "PIL": "pillow",
    "sklearn": "scikit-learn",
    "google.generativeai": "google-generativeai",
    "google": "google-generativeai",
    "newspaper": "newspaper3k",
    "yfinance": "yfinance",
    "duckduckgo_search": "duckduckgo-search",
    "langchain": "langchain",
    "langchain_core": "langchain-core",
    "langchain_openai": "langchain-openai",
    "langchain_community": "langchain-community",
    "langchain_tavily": "langchain-tavily",
    "tavily": "tavily-python",
    "langchain_google_genai": "langchain-google-genai",
    "autogen": "pyautogen",
    "openai": "openai",
    "httpx": "httpx",
    "requests": "requests",
    "pydantic": "pydantic",
    "fastapi": "fastapi",
    "feedparser": "feedparser",
    "trafilatura": "trafilatura",
    "tiktoken": "tiktoken",
    "aiohttp": "aiohttp",
    "numpy": "numpy",
    "pandas": "pandas",
    "pkg_resources": "setuptools<70.0.0",
    "pkg-resources": "setuptools<70.0.0",
    "setuptools": "setuptools<70.0.0",
    "faker": "faker",
}

# Standard library modules that never need pip installation
STANDARD_LIBS: Set[str] = {
    "os", "sys", "time", "json", "math", "re", "io", "random", "typing",
    "datetime", "uuid", "tempfile", "subprocess", "inspect", "logging",
    "argparse", "pathlib", "collections", "itertools", "functools",
    "urllib", "http", "shutil", "traceback", "copy", "hashlib",
    "dataclasses", "enum", "asyncio", "socket", "threading", "multiprocessing",
    "base64", "csv", "sqlite3", "unittest", "contextlib", "glob", "heapq",
    "operator", "secrets", "string", "struct", "warnings", "xml", "zipfile", "site"
}


# Global in-memory caches to prevent redundant or stalling pip installations
_ATTEMPTED_PACKAGES_CACHE: Set[str] = set()
_FAILED_PACKAGES_CACHE: Set[str] = set()
_SUCCESS_PACKAGES_CACHE: Set[str] = set()
_CHECKED_AGENTS_CACHE: Set[str] = set()


def is_module_installed(module_name: str) -> bool:
    """Checks if a module or package root is importable in the current Python environment."""
    clean = re.split(r'[=><~!]', str(module_name))[0].strip()
    root_module = clean.split(".")[0].strip()
    if not root_module or root_module in STANDARD_LIBS:
        return True

    clean_key = root_module.replace("-", "_").lower()

    pip_to_module = {
        "python_dotenv": "dotenv",
        "pyyaml": "yaml",
        "pillow": "PIL",
        "scikit_learn": "sklearn",
    }
    target = pip_to_module.get(clean_key, clean_key)

    import importlib.util
    for cand in (target, clean_key, root_module):
        try:
            if importlib.util.find_spec(cand) is not None:
                return True
        except Exception:
            pass
        try:
            __import__(cand)
            return True
        except Exception:
            pass

    return False


def install_package_sync(package_spec: str) -> bool:
    """Installs a package dynamically using pip in the current Python environment with caching."""
    clean_spec = package_spec.strip()
    if not clean_spec:
        return True

    spec_key = clean_spec.lower()
    if spec_key in _SUCCESS_PACKAGES_CACHE:
        return True
    if spec_key in _FAILED_PACKAGES_CACHE or spec_key in _ATTEMPTED_PACKAGES_CACHE:
        return False

    _ATTEMPTED_PACKAGES_CACHE.add(spec_key)

    base_pkg = re.split(r'[=><~!]', clean_spec)[0].strip()
    base_mod = base_pkg.replace("-", "_")

    if is_module_installed(base_mod) or is_module_installed(base_pkg):
        _SUCCESS_PACKAGES_CACHE.add(spec_key)
        return True

    logger.info(f"[DEPENDENCY_INSTALLER] Dynamically installing missing package: {clean_spec}...")
    try:
        cmd = [
            sys.executable, "-m", "pip", "install", clean_spec,
            "--quiet", "--no-warn-script-location", "--disable-pip-version-check"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if res.returncode == 0:
            _SUCCESS_PACKAGES_CACHE.add(spec_key)
            return True
        else:
            if base_pkg and base_pkg != clean_spec:
                base_key = base_pkg.lower()
                if base_key not in _FAILED_PACKAGES_CACHE:
                    cmd_fallback = [
                        sys.executable, "-m", "pip", "install", base_pkg,
                        "--quiet", "--no-warn-script-location", "--disable-pip-version-check"
                    ]
                    res2 = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=15)
                    if res2.returncode == 0:
                        _SUCCESS_PACKAGES_CACHE.add(spec_key)
                        return True
        
        # Check if user cancelled with Ctrl+C (Windows exit code 3221225786 / 0xC000013A, or SIGINT -2)
        if res.returncode in (3221225786, -2) or "cancelled by user" in (res.stderr or "").lower():
            logger.warning(f"[DEPENDENCY_INSTALLER] Pip installation aborted by user (Ctrl+C).")
            _FAILED_PACKAGES_CACHE.add(spec_key)
            raise KeyboardInterrupt("Pip installation cancelled by user.")
        if res.returncode == 0:
            logger.info(f"[DEPENDENCY_INSTALLER] Successfully installed {clean_spec}.")
            _SUCCESS_PACKAGES_CACHE.add(spec_key)
            return True
        else:
            logger.warning(
                f"[DEPENDENCY_INSTALLER] Pip install returned code {res.returncode} for {clean_spec}: {res.stderr[:200]}"
            )
            # Try without version specifier if failed (e.g. langchain==0.3.0 -> langchain)
            if "==" in clean_spec or ">=" in clean_spec:
                base_pkg = re.split(r"[><=~]", clean_spec)[0].strip()
                if base_pkg and base_pkg != clean_spec:
                    base_key = base_pkg.lower()
                    if base_key not in _FAILED_PACKAGES_CACHE:
                        logger.info(f"[DEPENDENCY_INSTALLER] Retrying unpinned: pip install {base_pkg}...")
                        cmd_fallback = [
                            sys.executable, "-m", "pip", "install", base_pkg,
                            "--quiet", "--no-warn-script-location", "--disable-pip-version-check"
                        ]
                        res2 = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=120)
                        if res2.returncode in (3221225786, -2) or "cancelled by user" in (res2.stderr or "").lower():
                            _FAILED_PACKAGES_CACHE.add(spec_key)
                            _FAILED_PACKAGES_CACHE.add(base_key)
                            raise KeyboardInterrupt("Pip installation cancelled by user.")
                        if res2.returncode == 0:
                            _SUCCESS_PACKAGES_CACHE.add(spec_key)
                            _SUCCESS_PACKAGES_CACHE.add(base_key)
                            return True
            _FAILED_PACKAGES_CACHE.add(spec_key)
            return False
    except KeyboardInterrupt:
        _FAILED_PACKAGES_CACHE.add(spec_key)
        raise
    except Exception as exc:
        logger.error(f"[DEPENDENCY_INSTALLER] Error installing {clean_spec}: {exc}")
        _FAILED_PACKAGES_CACHE.add(spec_key)
        return False


def extract_imports_from_code(code_str: str) -> Set[str]:
    """Extracts top-level and from-import module roots from Python source code."""
    imported_roots: Set[str] = set()
    try:
        tree = ast.parse(code_str)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0].strip()
                    if root and root not in STANDARD_LIBS:
                        imported_roots.add(root)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    root = node.module.split(".")[0].strip()
                    if root and root not in STANDARD_LIBS:
                        imported_roots.add(root)
    except Exception:
        # Fallback to regex
        for line in code_str.splitlines():
            line = line.strip()
            m_imp = re.match(r"^import\s+([a-zA-Z0-9_]+)", line)
            if m_imp:
                r = m_imp.group(1).strip()
                if r not in STANDARD_LIBS:
                    imported_roots.add(r)
            m_from = re.match(r"^from\s+([a-zA-Z0-9_]+)", line)
            if m_from:
                r = m_from.group(1).strip()
                if r not in STANDARD_LIBS:
                    imported_roots.add(r)
    return imported_roots


def ensure_agent_dependencies(agent: AgentRecord, sandbox_dir: Optional[str] = None) -> List[str]:
    """
    Inspects agent dependencies, source files, requirements.txt, and AST imports,
    and automatically installs any missing packages on-the-fly.
    Returns the list of installed package names.
    """
    if getattr(agent, "id", None) and agent.id in _CHECKED_AGENTS_CACHE:
        return []

    if getattr(agent, "id", None):
        _CHECKED_AGENTS_CACHE.add(agent.id)

    installed_packages: List[str] = []
    packages_to_check: Set[str] = set()

    # 1. From agent.dependencies
    if agent.dependencies:
        for d in agent.dependencies:
            name = d.name.strip()
            if name:
                packages_to_check.add(name)

    # 2. From agent.source_files requirements.txt
    if agent.source_files:
        for fname, content in agent.source_files.items():
            if fname.lower() in ("requirements.txt", "requirement.txt"):
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        packages_to_check.add(line)
            elif fname.endswith(".py"):
                # 3. Extract AST imports from python files
                imports = extract_imports_from_code(content)
                for imp in imports:
                    pkg_name = IMPORT_TO_PACKAGE_MAP.get(imp, imp)
                    packages_to_check.add(pkg_name)

    # 4. Check and install missing ones
    for pkg_spec in packages_to_check:
        base_name = re.split(r"[><=~]", pkg_spec)[0].strip()
        # Find corresponding module name
        mod_name = base_name.replace("-", "_")
        for k, v in IMPORT_TO_PACKAGE_MAP.items():
            if v.lower() == base_name.lower():
                mod_name = k
                break

        if not is_module_installed(mod_name) and not is_module_installed(base_name):
            success = install_package_sync(pkg_spec)
            if success:
                installed_packages.append(pkg_spec)

    return installed_packages


def auto_install_missing_module_from_error(error_message: str) -> Optional[str]:
    """
    Parses a ModuleNotFoundError or ImportError message, identifies the missing module,
    maps it to a package name, and installs it dynamically.
    Returns the package name installed if successful, None otherwise.
    """
    # Matches: No module named 'xyz' or No module named xyz
    match = re.search(r"No module named ['\"]?([a-zA-Z0-9_\-]+)['\"]?", error_message)
    if not match:
        # Matches: cannot import name 'xyz' from 'abc'
        match = re.search(r"from ['\"]?([a-zA-Z0-9_\-]+)['\"]?", error_message)

    if not match:
        return None

    missing_mod = match.group(1).split(".")[0].strip()
    if not missing_mod or missing_mod in STANDARD_LIBS:
        return None

    target_pkg = IMPORT_TO_PACKAGE_MAP.get(missing_mod, missing_mod.replace("_", "-"))
    if install_package_sync(target_pkg):
        return target_pkg
    return None
