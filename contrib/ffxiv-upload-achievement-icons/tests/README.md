# Tests for FFXIV Achievement Icons Upload Script

This directory contains comprehensive unit tests for the FFXIV achievement icons upload script and its components.

## Test Structure

```
tests/
├── __init__.py              # Test package initialization
├── conftest.py              # Shared pytest fixtures
├── test_saint_coinach.py    # Tests for SaintCoinach class
├── test_xivapi.py           # Tests for XIVAPI client
└── test_main.py             # Tests for main script functions
```

## Running Tests

### Option 1: Using the test runner script
```bash
python run_tests.py
```

### Option 2: Using unittest directly
```bash
python -m unittest discover tests -v
```

### Option 3: Using pytest (if installed)
```bash
pytest tests/ -v
```

## What's Tested

### SaintCoinach Module (`test_saint_coinach.py`)
- Database initialization and configuration
- Achievement counting and retrieval
- Icon path generation
- Timestamp tracking for updates
- Database schema management
- Error handling for missing data

### XIVAPI Module (`test_xivapi.py`)
- API client initialization
- HTTP request handling with proper parameters
- Achievement data retrieval
- Pagination handling for large datasets
- Timeout and error handling
- API key management

### Main Script (`test_main.py`)
- Custom log formatter functionality
- SSH client connection and file operations
- Configuration validation
- Achievement processing workflow
- Error handling for missing files
- File upload logic

## Test Features

- **Mocking**: Uses unittest.mock to isolate units under test
- **Temporary Resources**: Creates temporary databases and files for testing
- **Error Scenarios**: Tests both success and failure paths
- **Configuration**: Tests configuration validation and error handling
- **Logging**: Verifies logging functionality and log levels

## Dependencies

The tests require:
- Python 3.6+
- unittest (built-in)
- unittest.mock (built-in)
- tempfile (built-in)

Optional:
- pytest (for better test discovery and reporting)

## Coverage

The tests cover:
- ✅ Core functionality of all main classes
- ✅ Error handling and edge cases
- ✅ Configuration validation
- ✅ Database operations
- ✅ API interactions (mocked)
- ✅ File operations (mocked)
- ✅ Logging configuration

## Adding New Tests

When adding new tests:

1. Follow the naming convention `test_*.py`
2. Use descriptive test method names starting with `test_`
3. Include docstrings explaining what each test validates
4. Use appropriate fixtures from `conftest.py`
5. Mock external dependencies (network, filesystem, etc.)
6. Test both success and failure scenarios
