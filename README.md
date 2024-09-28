# Logger

This project provides a flexible and easy-to-use logging solution for Python applications. It offers a `Logger` class that streamlines the process of creating and managing loggers with various output options and automatic log rotation.

## Features

- Easy setup for file and console logging
- Automatic creation of log directories
- Log rotation with removal of old log entries
- Customizable log levels
- Decorator for error handling and logging
- Formatted log messages for both file and console output

## Installation

To use this logger, simply copy the `logger.py` file into your project directory.

## Usage

### Basic Usage

```python
from logger import Logger
import logging

# Create a logger instance
logger = Logger(
    name="my_app",
    path="/path/to/your/logfile.log",
    level=logging.INFO,
    also_print=True
)

# Use the logger
logger.info("Application started")
logger.warning("This is a warning message")
logger.error("An error occurred")
```

### Error Handling Decorator

The `Logger` class provides a decorator for error handling:

```python
@Logger.error_handler(logger)
def some_function():
    # Your code here
    pass
```

This decorator will catch any exceptions, log them using the provided logger, and re-raise the exception.

## Class: Logger

### Parameters

- `name` (str): The name of your logger.
- `path` (str): The full path to the file that the logger will write to.
- `level` (int, optional): The logging level. Default is `logging.INFO`.
- `also_print` (bool, optional): Whether to print log messages to the console. Default is `True`.
- `max_bytes` (int, optional): Maximum size of the log file before rotation. Default is 10MB.
- `backup_count` (int, optional): Number of backup files to keep. Default is 5.

### Methods

- `debug(message)`: Log a debug message.
- `info(message)`: Log an info message.
- `warning(message)`: Log a warning message.
- `error(message)`: Log an error message.
- `critical(message)`: Log a critical message.

### Static Methods

- `error_handler(logger)`: A decorator for error handling and logging.

## Log Rotation

The logger automatically manages log rotation:

- It removes log entries older than 7 days when initializing a new logger instance.
- If a log entry's date cannot be parsed, it's kept in the log file with a "CANNOT PARSE" note.

## Note

Ensure that the application has write permissions for the directory where log files will be stored.