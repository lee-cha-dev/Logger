import os
import logging
from datetime import datetime, timedelta
from functools import wraps


class Logger:
    def __init__(self, name, path, level=logging.INFO, also_print=True, max_bytes=10*1024*1024, backup_count=5):
        """
        Class that will assist with stream lining logger creation and logging
        :param name: The name of your logger.
        :param path: The full path to the file that the logger will write to.
        :param level: The level the logger will be set to (logging.INFO is default input)
        :param also_print: Boolean - Print to console as well (True/False)
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # Create logs directory
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

        # Remove old log files
        self._remove_old_logs()

        # File Handler - handles automatically writing to file
        file_handler = logging.FileHandler(path)
        file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)

        # Console Handler - handles automatically printing to console.
        if also_print:
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

    def _remove_old_logs(self):
        """
        Removes log files older than 7 days
        :return:
        """
        if not os.path.exists(self.path):
            return

        with open(self.path, 'r') as file:
            lines = file.readlines()

        seven_days_ago = datetime.now() - timedelta(days=7)
        new_lines = []

        for line in lines:
            try:
                log_date = datetime.strptime(line.split(' - ')[0], "%Y-%m-%d %H:%M:%S,%f")
                if log_date >= seven_days_ago:
                    new_lines.append(line)
            except (ValueError, IndexError):
                # If we cannot parse the date, keep the line
                new_lines.append(f"{line} - CANNOT PARSE")

        with open(self.path, 'w') as file:
            file.writelines(new_lines)

    # Write methods for the logger
    def debug(self, message):
        self.logger.debug(message)

    def info(self, message):
        self.logger.info(message)

    def warning(self, message):
        self.logger.warning(message)

    def error(self, message):
        self.logger.error(message)

    def critical(self, message):
        self.logger.critical(message)

    @staticmethod
    def error_handler(logger):
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_message = f"Error in {func.__name__}: {str(e)}"
                    logger.error(error_message)
                    raise
            return wrapper
        return decorator
