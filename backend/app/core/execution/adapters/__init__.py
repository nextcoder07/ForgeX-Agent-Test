"""
Interface Adapters for executing agents via CLI, HTTP, Function, Chat, Event, and Batch contracts.
All adapters output standardized canonical trajectory events.
"""
from app.core.execution.adapters.cli import CLIAdapter
from app.core.execution.adapters.http import HTTPAdapter
from app.core.execution.adapters.function import FunctionAdapter
from app.core.execution.adapters.chat import ChatAdapter
from app.core.execution.adapters.event import EventAdapter
from app.core.execution.adapters.batch import BatchAdapter

__all__ = [
    "CLIAdapter",
    "HTTPAdapter",
    "FunctionAdapter",
    "ChatAdapter",
    "EventAdapter",
    "BatchAdapter",
]
