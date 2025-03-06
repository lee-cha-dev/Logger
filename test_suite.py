import unittest
import os
import tempfile
import threading
import time
import json
import logging
from unittest.mock import patch, MagicMock
from logger import Logger, LoggerMetrics, LoggerConfig, LoggerConfigError
from buffer_handler import BufferedHandler
from elk_stack_integration import ElasticsearchHandler
from error_handler import ErrorHandler


class TestLogger(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for logs
        self.temp_dir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.temp_dir, "test.log")

        # Reset logger instances between tests
        Logger._instances = {}

    def tearDown(self):
        # Clean up
        for root, dirs, files in os.walk(self.temp_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
        os.rmdir(self.temp_dir)

    def test_singleton_pattern(self):
        """Test that get_instance returns the same instance for the same name"""
        logger1 = Logger.get_instance("test_singleton", self.log_path)
        logger2 = Logger.get_instance("test_singleton", "/different/path.log")  # Path should be ignored

        self.assertIs(logger1, logger2, "get_instance should return the same instance for the same name")

    def test_different_instances(self):
        """Test that different names create different instances"""
        logger1 = Logger.get_instance("test_instance1", self.log_path)
        logger2 = Logger.get_instance("test_instance2", self.log_path)

        self.assertIsNot(logger1, logger2, "Different names should create different logger instances")

    def test_log_file_creation(self):
        """Test that log files are created properly"""
        logger = Logger.get_instance("test_file_creation", self.log_path)
        logger.info("Test message")

        self.assertTrue(os.path.exists(self.log_path), "Log file should be created")

        with open(self.log_path, 'r') as f:
            content = f.read()
            self.assertIn("Test message", content, "Log message should be written to file")

    def test_log_levels(self):
        """Test that log levels work correctly"""
        logger = Logger.get_instance("test_levels", self.log_path, level=logging.WARNING)

        # These should not be logged
        logger.debug("Debug message")
        logger.info("Info message")

        # These should be logged
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")

        with open(self.log_path, 'r') as f:
            content = f.read()
            self.assertNotIn("Debug message", content)
            self.assertNotIn("Info message", content)
            self.assertIn("Warning message", content)
            self.assertIn("Error message", content)
            self.assertIn("Critical message", content)

    def test_metrics(self):
        """Test that metrics are tracked correctly"""
        logger = Logger.get_instance("test_metrics", self.log_path)

        logger.info("Info 1")
        logger.info("Info 2")
        logger.warning("Warning")
        logger.error("Error")

        metrics = logger.get_metrics()
        self.assertEqual(metrics['total_logs'], 4)
        self.assertEqual(metrics['errors'], 1)
        self.assertEqual(metrics['warnings'], 1)
        self.assertEqual(metrics['level_distribution'].get('INFO', 0), 2)

    def test_structured_logging(self):
        """Test structured logging format"""
        logger = Logger.get_instance("test_structured", self.log_path)

        logger.info("User action", user_id="123", action="login")

        with open(self.log_path, 'r') as f:
            content = f.read()
            # Extract JSON from the log line
            json_start = content.find('{')
            json_str = content[json_start:]
            data = json.loads(json_str)

            self.assertEqual(data['message'], "User action")
            self.assertEqual(data['context']['user_id'], "123")
            self.assertEqual(data['context']['action'], "login")

    def test_context_manager(self):
        """Test context manager functionality"""
        with Logger.get_instance("test_context", self.log_path) as logger:
            logger.info("Inside context")

        # After context exit, handlers should be closed
        for handler in logger.logger.handlers:
            self.assertTrue(handler.closed)

    def test_error_handler_decorator(self):
        """Test error handler decorator"""
        logger = Logger.get_instance("test_decorator", self.log_path)

        @Logger.error_handler(logger)
        def failing_function():
            raise ValueError("Test error")

        with self.assertRaises(ValueError):
            failing_function()

        with open(self.log_path, 'r') as f:
            content = f.read()
            self.assertIn("Error in failing_function: Test error", content)

    def test_thread_safety(self):
        """Test thread safety of logging and metrics"""
        logger = Logger.get_instance("test_threads", self.log_path)

        def log_messages(count):
            for i in range(count):
                logger.info(f"Thread message {i}")

        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=log_messages, args=(100,))
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify metrics
        metrics = logger.get_metrics()
        self.assertEqual(metrics['total_logs'], 1000)  # 10 threads × 100 messages
        self.assertEqual(metrics['level_distribution'].get('INFO', 0), 1000)

    def test_buffer_handler(self):
        """Test BufferedHandler functionality"""
        # Create a mock target handler
        mock_target = MagicMock()

        # Create a BufferedHandler with small capacity for easier testing
        buffer_handler = BufferedHandler(capacity=5, flush_interval=0.5)
        buffer_handler.set_target(mock_target)

        # Create a logger and add the buffer handler
        logger = logging.getLogger("test_buffer")
        logger.setLevel(logging.INFO)
        logger.addHandler(buffer_handler)

        # Log messages
        for i in range(10):
            logger.info(f"Buffer test message {i}")

        # Wait for flush interval
        time.sleep(1)

        # Verify that the mock target was called
        self.assertTrue(mock_target.emit.called)
        # Should be called at least twice (once when buffer reached capacity, once on timer)
        self.assertGreaterEqual(mock_target.emit.call_count, 2)

        # Clean up
        buffer_handler.close()

    def test_enhanced_error_handler(self):
        """Test enhanced ErrorHandler functionality"""
        logger = Logger.get_instance("test_enhanced_error", self.log_path)

        # Test with function arguments logging
        @ErrorHandler(logger, log_args=True, log_stack_trace=True)
        def func_with_args(name, age, data=None):
            raise ValueError("Test enhanced error")

        # Call with different argument types
        test_data = {"key": "value"}
        with self.assertRaises(ValueError):
            func_with_args("Alice", 30, test_data)

        # Check log content
        with open(self.log_path, 'r') as f:
            content = f.read()
            self.assertIn("Exception in func_with_args", content)
            self.assertIn("Test enhanced error", content)
            self.assertIn("'name': 'Alice'", content)
            self.assertIn("'age': 30", content)
            self.assertIn("'key': 'value'", content)
            self.assertIn("stack_trace", content)

    @patch('requests.post')
    def test_elasticsearch_handler(self, mock_post):
        """Test ElasticsearchHandler functionality"""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        # Create handler
        es_handler = ElasticsearchHandler(
            host="localhost",
            port=9200,
            index_prefix="test-logs"
        )

        # Set up formatter
        formatter = logging.Formatter("%(message)s")
        es_handler.setFormatter(formatter)

        # Create a record
        record = logging.LogRecord(
            name="test_es",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Test Elasticsearch log",
            args=(),
            exc_info=None
        )

        # Process the record
        es_handler.emit(record)

        # Verify that requests.post was called
        mock_post.assert_called_once()

        # Verify the data sent
        call_args = mock_post.call_args
        self.assertIn("json", call_args[1])
        self.assertEqual(call_args[1]["json"]["message"], "Test Elasticsearch log")
        self.assertEqual(call_args[1]["json"]["level"], "INFO")

        # Clean up
        es_handler.close()

    def test_non_serializable_context(self):
        """Test handling of non-serializable context values"""
        logger = Logger.get_instance("test_non_serializable", self.log_path)

        # Create a non-serializable object (a function)
        def non_serializable_func():
            pass

        # Log with this context
        logger.info("Message with non-serializable context",
                    func=non_serializable_func,
                    normal_value="This is normal")

        # Check log content
        with open(self.log_path, 'r') as f:
            content = f.read()
            # Should contain the normal value
            self.assertIn("This is normal", content)
            # Should contain a placeholder for the function
            self.assertIn("<non-serializable: function>", content)


if __name__ == "__main__":
    unittest.main()