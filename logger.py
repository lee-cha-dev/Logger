"""Enterprise-grade logging system with advanced features.

This module provides a comprehensive logging solution with features such as:
- Thread-safe metrics tracking
- Structured JSON logging
- Log rotation
- Buffered logging for high-throughput
- ELK Stack integration
- Enhanced error handling
- Singleton pattern for consistent logging
"""

import os
import json
import logging
import threading
import yaml
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

# Import new modules
from buffer_handler import BufferedHandler
from elk_stack_integration import ElasticsearchHandler
from enhanced_logger_config import EnhancedLoggerConfig
from error_handler import ErrorHandler


class LoggerConfigError(Exception):
    """Base exception for logger configuration errors"""
    pass


class LoggerInitializationError(LoggerConfigError):
    """Raised when logger initialization fails"""
    pass

@dataclass
class LoggerMetrics:
    """Class for tracking logger metrics.

    This class provides thread-safe counters for tracking log activity by level,
    with special tracking for errors and warnings.

    Attributes:
        log_counts: Counter for logs by level.
        errors: Total count of error logs.
        warnings: Total count of warning logs.
        last_error_timestamp: Timestamp of the most recent error.
        total_logs: Total count of all logs processed.
        _lock: Thread lock for ensuring thread safety.
    """
    log_counts: Dict[str, int] = field(default_factory=dict)
    errors: int = 0
    warnings: int = 0
    last_error_timestamp: Optional[datetime] = None
    total_logs: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def increment_level(self, level: str) -> None:
        """Thread-safe increment the count for a specific log level.

        Args:
            level: The log level to increment (e.g., "INFO", "ERROR").
        """
        with self._lock:
            self.log_counts[level] = self.log_counts.get(level, 0) + 1
            self.total_logs += 1
            if level == "ERROR":
                self.errors += 1
                self.last_error_timestamp = datetime.now()
            elif level == "WARNING":
                self.warnings += 1


class LoggerConfig:
    """Configuration constants for logger.

    This class contains default configuration values and constants used
    throughout the logger implementation.
    """
    DEFAULT_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    CONSOLE_FORMAT: str = "%(name)s - %(levelname)s - %(message)s"
    DEFAULT_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
    DEFAULT_ENCODING: str = "utf-8"
    DEFAULT_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB
    DEFAULT_BACKUP_COUNT: int = 5
    VALID_LOG_LEVELS: Dict[str, int] = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }


class Logger:
    """Enterprise-level logger implementation with advanced features.

    This logger provides a comprehensive set of features for enterprise
    applications including thread-safety, structured logging, buffering,
    log rotation, and ELK stack integration.

    Attributes:
        _instance_lock: Class-level lock for thread-safe singleton access.
        _instances: Dictionary of logger instances by name.
    """
    _instance_lock = threading.Lock()
    _instances: Dict[str, 'Logger'] = {}

    def __init__(
            self,
            name: str,
            path: str,
            level: int = logging.INFO,
            also_print: bool = True,
            max_bytes: int = LoggerConfig.DEFAULT_MAX_BYTES,
            backup_count: int = LoggerConfig.DEFAULT_BACKUP_COUNT,
            config_file: Optional[str] = None,
            use_buffer: bool = False,
            buffer_capacity: int = 100,
            buffer_flush_interval: float = 5.0,
            use_elasticsearch: bool = False,
            es_host: str = 'localhost',
            es_port: int = 9200,
            es_index_prefix: str = 'logs'
    ) -> None:
        """Initialize the logger with specified configuration.

        Args:
            name: The name of the logger.
            path: Path to the log file.
            level: Logging level (default: INFO).
            also_print: Whether to print to console (default: True).
            max_bytes: Maximum size of log file before rotation.
            backup_count: Number of backup files to keep.
            config_file: Optional path to YAML configuration file.
            use_buffer: Whether to use buffered logging.
            buffer_capacity: Buffer capacity for buffered logging.
            buffer_flush_interval: Flush interval for buffered logging in seconds.
            use_elasticsearch: Whether to send logs to Elasticsearch.
            es_host: Elasticsearch host.
            es_port: Elasticsearch port.
            es_index_prefix: Prefix for Elasticsearch indices.
        """
        self.name = name
        self.path = path
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.metrics = LoggerMetrics()
        self.use_buffer = use_buffer
        self.buffer_capacity = buffer_capacity
        self.buffer_flush_interval = buffer_flush_interval
        self.use_elasticsearch = use_elasticsearch
        self.es_host = es_host
        self.es_port = es_port
        self.es_index_prefix = es_index_prefix

        # Load configuration using enhanced logger config if config file provided
        if config_file:
            config = EnhancedLoggerConfig.get_config(config_file)
            self._apply_config(config)

        self._validate_level(level)
        self._setup_logger(name, level, also_print)

    def _apply_config(self, config: Dict[str, Any]) -> None:
        """Apply configuration from EnhancedLoggerConfig.

        This method updates logger settings from a configuration dictionary,
        typically loaded from a YAML file or environment variables.

        Args:
            config: Dictionary containing configuration values.
        """
        # Set basic configuration values
        if 'level' in config:
            level_name = config['level'].upper()
            if level_name in LoggerConfig.VALID_LOG_LEVELS:
                self.level = LoggerConfig.VALID_LOG_LEVELS[level_name]

        # Set other configuration values
        self.max_bytes = config.get('max_bytes', self.max_bytes)
        self.backup_count = config.get('backup_count', self.backup_count)
        self.use_buffer = config.get('buffer_size', 0) > 0
        if self.use_buffer:
            self.buffer_capacity = config.get('buffer_size', self.buffer_capacity)
            self.buffer_flush_interval = config.get('flush_interval', self.buffer_flush_interval)

        # Elasticsearch configuration
        if 'elasticsearch' in config:
            es_config = config['elasticsearch']
            self.use_elasticsearch = es_config.get('enabled', False)
            self.es_host = es_config.get('host', self.es_host)
            self.es_port = es_config.get('port', self.es_port)
            self.es_index_prefix = es_config.get('index_prefix', self.es_index_prefix)

    def _load_config(self, config_path: str) -> None:
        """Load configuration from a YAML file.

        Note: This is maintained for backward compatibility.
        New code should use EnhancedLoggerConfig.

        Args:
            config_path: Path to the YAML configuration file.

        Raises:
            LoggerInitializationError: If the config file can't be loaded.
        """
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
                self.max_bytes = config.get('max_bytes', self.max_bytes)
                self.backup_count = config.get('backup_count', self.backup_count)
                level_name = config.get('level', 'INFO').upper()
                if level_name in LoggerConfig.VALID_LOG_LEVELS:
                    self.level = LoggerConfig.VALID_LOG_LEVELS[level_name]
        except FileNotFoundError:
            raise LoggerInitializationError(f"Config file not found: {config_path}")
        except yaml.YAMLError as e:
            raise LoggerInitializationError(f"Error parsing config file: {e}")
        except Exception as e:
            raise LoggerInitializationError(f"Unknown error loading config: {e}")

    @staticmethod
    def _validate_level(level: int) -> None:
        """Validate the logging level.

        Args:
            level: The logging level to validate.

        Raises:
            LoggerInitializationError: If the level is not valid.
        """
        if level not in LoggerConfig.VALID_LOG_LEVELS.values():
            raise LoggerInitializationError(f"Invalid logging level: {level}\nMust be one of the following: {list(LoggerConfig.VALID_LOG_LEVELS.keys())}")

    def _setup_logger(self, name: str, level: int, also_print: bool) -> None:
        """Set up the logger with the specified configuration.

        Args:
            name: The name of the logger.
            level: The logging level.
            also_print: Whether to print to console.

        Raises:
            LoggerInitializationError: If logger setup fails.
        """
        try:
            self.logger = logging.getLogger(name)
            self.logger.setLevel(level)
            self.logger.handlers = []  # Clear any existing handlers

            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            self._setup_file_handler()

            if also_print:
                self._setup_console_handler()

            # Add buffer handler if enabled
            if self.use_buffer:
                self._setup_buffer_handler()

            # Add Elasticsearch handler if enabled
            if self.use_elasticsearch:
                self._setup_elasticsearch_handler()

        except Exception as e:
            raise LoggerInitializationError(f"Error setting up logger: {e}")

    def _setup_file_handler(self) -> None:
        """Set up the file handler for the logger.

        Creates a rotating file handler that automatically rotates log files
        when they reach the configured size.
        """
        file_handler = RotatingFileHandler(
            self.path,
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding=LoggerConfig.DEFAULT_ENCODING
        )
        file_formatter = logging.Formatter(
            LoggerConfig.DEFAULT_FORMAT,
            LoggerConfig.DEFAULT_DATE_FORMAT
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

    def _setup_console_handler(self) -> None:
        """Set up the console handler.

        Creates a console handler that outputs log messages to the console.
        """
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            LoggerConfig.CONSOLE_FORMAT,
            LoggerConfig.DEFAULT_DATE_FORMAT
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

    def _setup_buffer_handler(self) -> None:
        """Set up the buffer handler with appropriate target.

        Creates a buffer handler that collects log records and periodically
        flushes them to a target handler.
        """
        # Create a RotatingFileHandler as the target for buffered logs
        target_handler = RotatingFileHandler(
            self.path + ".buffer",  # Store buffered logs in a separate file
            maxBytes=self.max_bytes,
            backupCount=self.backup_count,
            encoding=LoggerConfig.DEFAULT_ENCODING
        )

        # Set formatter for the target handler
        target_formatter = logging.Formatter(
            LoggerConfig.DEFAULT_FORMAT,
            LoggerConfig.DEFAULT_DATE_FORMAT
        )
        target_handler.setFormatter(target_formatter)

        # Create the buffer handler
        buffer_handler = BufferedHandler(
            capacity=self.buffer_capacity,
            flush_interval=self.buffer_flush_interval
        )

        # Set formatter for the buffer handler
        buffer_formatter = logging.Formatter(
            LoggerConfig.DEFAULT_FORMAT,
            LoggerConfig.DEFAULT_DATE_FORMAT
        )
        buffer_handler.setFormatter(buffer_formatter)

        # Set the target handler
        buffer_handler.set_target(target_handler)

        # Add to the logger
        self.logger.addHandler(buffer_handler)

    def _setup_elasticsearch_handler(self) -> None:
        """Set up the Elasticsearch handler.

        Creates a handler that sends log records to Elasticsearch.
        """
        es_handler = ElasticsearchHandler(
            host=self.es_host,
            port=self.es_port,
            index_prefix=self.es_index_prefix
        )
        self.logger.addHandler(es_handler)

    def _update_metrics(self, level: str) -> None:
        """Update metrics for the logger.

        Args:
            level: The log level to update metrics for.
        """
        self.metrics.increment_level(level)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug message.

        Args:
            message: The message to log.
            **kwargs: Additional context data for structured logging.
        """
        try:
            self._update_metrics("DEBUG")
            if kwargs:
                message = self._format_structured_message(message, kwargs)
            self.logger.debug(message)
        except Exception as e:
            # Prevent logging failures from affecting application flow
            print(f"Logging error in debug: {str(e)}")  # Fallback logging

    def info(self, message: str, **kwargs: Any) -> None:
        """Log an info message.

        Args:
            message: The message to log.
            **kwargs: Additional context data for structured logging.
        """
        try:
            self._update_metrics("INFO")
            if kwargs:
                message = self._format_structured_message(message, kwargs)
            self.logger.info(message)
        except Exception as e:
            # Prevent logging failures from affecting application flow
            print(f"Logging error in info: {str(e)}")  # Fallback logging

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message.

        Args:
            message: The message to log.
            **kwargs: Additional context data for structured logging.
        """
        try:
            self._update_metrics("WARNING")
            if kwargs:
                message = self._format_structured_message(message, kwargs)
            self.logger.warning(message)
        except Exception as e:
            # Prevent logging failures from affecting application flow
            print(f"Logging error in warning: {str(e)}")  # Fallback logging

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message.

        Args:
            message: The message to log.
            **kwargs: Additional context data for structured logging.
        """
        try:
            self._update_metrics('ERROR')
            if kwargs:
                message = self._format_structured_message(message, kwargs)
            self.logger.error(message)
        except Exception as e:
            # Prevent logging failures from affecting application flow
            print(f"Logging error in error: {str(e)}")  # Fallback logging

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message.

        Args:
            message: The message to log.
            **kwargs: Additional context data for structured logging.
        """
        try:
            self._update_metrics('CRITICAL')
            if kwargs:
                message = self._format_structured_message(message, kwargs)
            self.logger.critical(message)
        except Exception as e:
            # Prevent logging failures from affecting application flow
            print(f"Logging error in critical: {str(e)}")  # Fallback logging

    def _format_structured_message(self, message: str, context: Dict[str, Any]) -> str:
        """Format a structured message with context.

        Handles non-serializable objects by falling back to string representations.

        Args:
            message: The message to format.
            context: Additional context data for the message.

        Returns:
            A JSON-formatted string containing the message and context.
        """
        try:
            # Add standard fields
            structured_message = {
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "logger": self.name,
                "level": context.get("_level", "INFO"),
                "context": {}
            }

            # Move special keys like '_level' to the top level
            for key in list(context.keys()):
                if key.startswith('_'):
                    if key != '_level':  # We already handled _level
                        structured_message[key[1:]] = context[key]
                    context.pop(key)

            # Add remaining context
            structured_message["context"] = context

            return json.dumps(structured_message)
        except TypeError:
            # Handle non-serializable objects
            safe_context = {}
            for key, value in context.items():
                try:
                    # Test if it's serializable
                    json.dumps({key: value})
                    safe_context[key] = value
                except TypeError:
                    # Fall back to string representation
                    safe_context[key] = f"<non-serializable: {type(value).__name__}>"

            return self._format_structured_message(message, safe_context)

    @staticmethod
    def error_handler(logger: 'Logger', **kwargs):
        """Decorator for handling and logging errors in functions.

        Note: This is maintained for backward compatibility.
        New code should use the enhanced ErrorHandler class.

        Args:
            logger: The logger instance to use for error logging.
            **kwargs: Additional configuration for the error handler.

        Returns:
            A decorator that handles and logs errors.
        """
        # Use the enhanced ErrorHandler with default settings
        return ErrorHandler(logger=logger, **kwargs)

    @classmethod
    def get_instance(cls, name: str, *args, **kwargs) -> 'Logger':
        """Get or create a logger instance (Singleton pattern).

        Args:
            name: The name of the logger instance.
            *args: Additional arguments to pass to the constructor.
            **kwargs: Additional keyword arguments to pass to the constructor.

        Returns:
            A Logger instance with the specified name.
        """
        with cls._instance_lock:
            if name not in cls._instances:
                cls._instances[name] = cls(name, *args, **kwargs)
            return cls._instances[name]

    def get_metrics(self) -> Dict[str, Any]:
        """Get current logger metrics.

        Returns:
            A dictionary containing metrics about logger activity.
        """
        return {
            'total_logs': self.metrics.total_logs,
            'errors': self.metrics.errors,
            'warnings': self.metrics.warnings,
            'last_error': self.metrics.last_error_timestamp.isoformat() if self.metrics.last_error_timestamp else None,
            'level_distribution': self.metrics.log_counts
        }

    def __enter__(self) -> 'Logger':
        """Context manager entry.

        Returns:
            The logger instance.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit.

        Args:
            exc_type: Type of exception, if any.
            exc_val: Exception value, if any.
            exc_tb: Exception traceback, if any.
        """
        self.close()

    def close(self) -> None:
        """Clean up handlers and close the logger."""
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)
