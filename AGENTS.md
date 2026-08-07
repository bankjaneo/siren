# AGENTS.md

## Build, Lint, and Test Commands

### Development Setup
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the application
./start.sh
```

### Testing
```bash
# Run all tests (if test framework is added)
pytest tests/

# Run a single test
pytest tests/test_stream_audio.py::test_get_mp3_files

# Run with coverage
pytest tests/ --cov=.
```

### Code Quality
```bash
# Lint code
ruff check stream_audio.py

# Format code
ruff format stream_audio.py

# Type checking (if mypy is configured)
mypy stream_audio.py
```

## Code Style Guidelines

### Python Version and Dependencies
- Use Python 3.11+
- Flask 3.0.0 for web framework
- pychromecast 14.0.9 for Chromecast control
- zeroconf 0.135.0 for service discovery
- flask-cors 4.0.0 for CORS support

### Import Organization
1. Standard library modules (logging, os, socket, threading, time)
2. Third-party packages (flask, flask_cors, pychromecast, zeroconf)
3. Local modules (none in this project)

Imports are sorted alphabetically by ruff (isort), with a blank line separating stdlib from third-party.

Example:
```python
import logging
import os
import socket
import threading
import time
from collections.abc import Generator
from functools import wraps
from typing import Any

import pychromecast
from flask import Flask, Response, render_template
from flask_cors import CORS
from pychromecast import CastBrowser
from pychromecast.discovery import SimpleCastListener
from zeroconf import InterfaceChoice, Zeroconf
```

### Naming Conventions
- **Functions**: snake_case (e.g., `get_mp3_files`, `find_chromecast`)
- **Variables**: snake_case (e.g., `is_paused`, `chromecast`, `current_volume`)
- **Constants**: UPPER_SNAKE_CASE (e.g., `MUSIC_FOLDER`, `DEFAULT_DEVICE`, `PORT`)
- **Classes**: PascalCase (none used in current codebase)

### Code Structure
1. Module-level constants and global variables
2. Helper functions (get_mp3_files, run_discovery, find_chromecast, set_volume, stream_audio, etc.)
3. Flask route handlers (stream_audio_endpoint, index, play, pause, etc.)
4. Main execution block

### Function Documentation
- Use docstrings for all functions
- Describe purpose, parameters, and return values
- Include examples for complex functions

Example:
```python
def find_chromecast(device_name=None):
    """Find and connect to Chromecast device

    Args:
        device_name: Optional specific device name to connect to

    Returns:
        bool: True if successful, False otherwise
    """
```

### Error Handling
- Use try-except blocks for exception handling
- Catch generic Exception for broad error handling
- Log errors appropriately
- Return meaningful error messages

Example:
```python
try:
    with open(current_file, "rb") as f:
        while True:
            data = f.read(4096)
            if not data:
                break
            yield data
except Exception:
    pass
```

### Threading and Concurrency
- Use threading.Lock() for shared state protection
- Use threading.Event() for pause/resume control
- Global variables should be declared at module level
- Thread-safe operations with proper locking

### Flask Application Structure
- Use Flask app factory pattern (app = Flask(__name__))
- Enable CORS with CORS(app)
- Suppress unnecessary logging (werkzeug warnings)
- Use Response with generators for streaming
- Route decorators for URL mapping

### Code Organization
- Keep related functions together
- Group route handlers logically
- Use descriptive variable and function names
- Avoid code duplication

### Logging
- Configure logging at module level
- Suppress development server warnings
- Use appropriate log levels

### Type Hints
- Type hints are used for function parameters and return values
- Use modern annotations (`list[str]`, `dict[str, ...]`, `str | None`)

### Testing Guidelines
- Write tests for all route handlers
- Test error cases (no MP3 files, no Chromecast found)
- Test pause/resume functionality
- Test volume control
- Mock external dependencies when possible

### Code Review Checklist
- All imports are properly organized
- Functions have docstrings
- Error handling is appropriate
- Global variables are documented
- Thread safety is maintained
- Flask routes are properly decorated
- Constants are uppercase
- Code follows existing style patterns
