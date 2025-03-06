"""Error handling utilities for the logger system.

This module provides enhanced error handling functionality that can be used
as decorators to automatically log exceptions with detailed context.
"""

from functools import wraps
import traceback
import inspect


class ErrorHandler:
    """Enhanced error handler with customization options.

    This class provides a decorator that captures and logs exceptions
    raised by decorated functions, with options to control logging behavior.

    Attributes:
        logger: The logger instance to use for logging errors.
        swallow_exceptions: Whether to swallow exceptions instead of reraising.
        log_args: Whether to log function arguments.
        log_stack_trace: Whether to log the full stack trace.
        reraise: Whether to reraise the exception.
        max_arg_length: Maximum length for argument logging.
    """

    def __init__(self, logger, swallow_exceptions=False,
                 log_args=True, log_stack_trace=True,
                 reraise=True, max_arg_length=1000):
        """Initialize the error handler.

        Args:
            logger: Logger instance to use for logging errors.
            swallow_exceptions: Whether to swallow exceptions instead of reraising.
            log_args: Whether to log function arguments.
            log_stack_trace: Whether to log the full stack trace.
            reraise: Whether to reraise the exception.
            max_arg_length: Maximum length for argument logging.
        """
        self.logger = logger
        self.swallow_exceptions = swallow_exceptions
        self.log_args = log_args
        self.log_stack_trace = log_stack_trace
        self.reraise = reraise
        self.max_arg_length = max_arg_length

    def __call__(self, func):
        """Make the error handler callable as a decorator.

        Args:
            func: The function to decorate.

        Returns:
            A wrapped function that includes error handling.
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Prepare error context
                error_context = {
                    'exception_type': type(e).__name__,
                    'exception_message': str(e),
                    'function': func.__name__,
                    'module': func.__module__
                }

                # Log function arguments if enabled
                if self.log_args:
                    # Get argument names and values
                    arg_spec = inspect.getfullargspec(func)
                    arg_names = arg_spec.args

                    # Handle 'self' or 'cls' for methods
                    if arg_names and arg_names[0] in ('self', 'cls') and len(args) > 0:
                        arg_names = arg_names[1:]  # Skip 'self'/'cls'
                        args = args[1:]           # Skip the instance/class

                    # Map positional arguments
                    pos_args = {}
                    for i, arg_value in enumerate(args):
                        if i < len(arg_names):
                            pos_args[arg_names[i]] = self._format_arg(arg_value)
                        else:
                            pos_args[f'arg{i}'] = self._format_arg(arg_value)

                    # Format keyword arguments
                    kw_args = {k: self._format_arg(v) for k, v in kwargs.items()}

                    # Add to context
                    error_context['args'] = pos_args
                    error_context['kwargs'] = kw_args

                # Log stack trace if enabled
                if self.log_stack_trace:
                    error_context['stack_trace'] = traceback.format_exc()

                # Log the error
                self.logger.error(
                    f"Exception in {func.__name__}: {str(e)}",
                    **error_context
                )

                # Handle the exception
                if self.reraise:
                    raise
                return None

        return wrapper

    def _format_arg(self, arg):
        """Format an argument for logging, with length limit.

        Converts the argument to a string representation and truncates it
        if it exceeds the maximum length.

        Args:
            arg: The argument value to format.

        Returns:
            A string representation of the argument.
        """
        try:
            arg_str = repr(arg)
            if len(arg_str) > self.max_arg_length:
                return arg_str[:self.max_arg_length] + "..."
            return arg_str
        except Exception:
            return f"<Error formatting argument of type {type(arg).__name__}>"
