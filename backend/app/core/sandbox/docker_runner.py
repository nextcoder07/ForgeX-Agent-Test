"""
Docker Sandbox Execution Engine.
Detects Docker CLI availability on the host system and manages containerized sandbox execution.
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def is_docker_available() -> bool:
    """Checks whether Docker CLI executable is available on the host system PATH."""
    try:
        res = shutil.which("docker")
        if res is not None:
            proc = subprocess.run(["docker", "--version"], capture_output=True, timeout=3)
            return proc.returncode == 0
    except Exception:
        pass
    return False


def generate_dockerfile_contents(runtime_config: Dict[str, Any]) -> str:
    """Generates an ephemeral Dockerfile configuration for an agent sandbox."""
    python_ver = runtime_config.get("version", "3.12")
    return f"""
FROM python:{python_ver}-slim
WORKDIR /app
RUN useradd -m -s /bin/bash sandboxuser
USER sandboxuser
ENV PYTHONUNBUFFERED=1
ENV SANDBOX_MODE=docker_container
CMD ["python3"]
"""
