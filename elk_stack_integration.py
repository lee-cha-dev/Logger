"""Elasticsearch integration for logging.

This module provides a handler for sending log records to Elasticsearch,
implementing a circuit breaker pattern to handle connection failures.
"""

import json
from logging import Handler
import socket
import time
from datetime import datetime
import requests
from requests.exceptions import RequestException
from urllib.parse import urljoin

class ElasticsearchHandler(Handler):
    """Handler for sending logs to Elasticsearch.

    This handler formats log records as JSON documents and sends them
    to an Elasticsearch instance. It implements a circuit breaker pattern
    to handle connection failures gracefully.

    Attributes:
        base_url: The base URL for the Elasticsearch instance.
        index_prefix: Prefix for Elasticsearch indices.
        timeout: Request timeout in seconds.
        hostname: The local host name to include in log records.
        circuit_open: Whether the circuit breaker is currently open.
        failure_count: The number of consecutive failures.
        max_failures: The number of failures before opening the circuit.
        backoff_time: The time until which the circuit remains open.
    """

    def __init__(self, host='localhost', port=9200, index_prefix='logs', timeout=5):
        """
        Initialize Elasticsearch handler

        Args:
            host: Elasticsearch host
            port: Elasticsearch port
            index_prefix: Prefix for Elasticsearch indices
            timeout: Request timeout in seconds
        """
        super().__init__()
        self.base_url = f"http://{host}:{port}"
        self.index_prefix = index_prefix
        self.timeout = timeout
        self.hostname = socket.gethostname()
        self.circuit_open = False
        self.failure_count = 0
        self.max_failures = 3
        self.backoff_time = 0

    def _get_index_name(self):
        """Get the index name for today.

        Returns:
            A string containing the index name with date suffix.
        """
        today = datetime.now().strftime("%Y.%m.%d")
        return f"{self.index_prefix}-{today}"

    def emit(self, record):
        """Process a log record and send to Elasticsearch.

        If the circuit breaker is open, the method will return without
        processing the record until the backoff time has elapsed.

        Args:
            record: The log record to process, either as a formatted string 
                  or a LogRecord object.
        """        # Check if circuit breaker is open
        if self.circuit_open:
            current_time = time.time()
            if current_time < self.backoff_time:
                return
            # Reset circuit breaker after backoff
            self.circuit_open = False
            self.failure_count = 0

        try:
            # Format the record
            if isinstance(record, str):
                # Already formatted
                document = json.loads(record)
            else:
                # Format the record
                document = {
                    'timestamp': datetime.now().isoformat(),
                    'level': record.levelname,
                    'logger': record.name,
                    'message': record.getMessage(),
                    'host': self.hostname
                }

                # Add extra fields if available
                if hasattr(record, 'context'):
                    document['context'] = record.context

            # Add metadata
            document['@timestamp'] = document.get('timestamp', datetime.now().isoformat())

            # Send to Elasticsearch
            index_name = self._get_index_name()
            url = urljoin(self.base_url, f"/{index_name}/_doc")

            response = requests.post(
                url,
                json=document,
                timeout=self.timeout,
                headers={'Content-Type': 'application/json'}
            )

            if response.status_code >= 400:
                self._handle_failure(f"Elasticsearch error: {response.status_code} {response.text}")

        except (RequestException, json.JSONDecodeError) as e:
            self._handle_failure(f"Error sending to Elasticsearch: {str(e)}")

    def _handle_failure(self, error_message):
        """Handle a failure with circuit breaker pattern.

        Increments the failure count and opens the circuit breaker if
        the maximum number of failures is reached.

        Args:
            error_message: A description of the failure that occurred.
        """
        self.failure_count += 1

        if self.failure_count >= self.max_failures:
            self.circuit_open = True
            # Exponential backoff: 5s, 10s, 20s, etc.
            backoff_seconds = 5 * (2 ** (self.failure_count - self.max_failures))
            self.backoff_time = time.time() + backoff_seconds
            print(f"Circuit breaker opened. Backing off for {backoff_seconds}s: {error_message}")
        else:
            print(f"Elasticsearch error ({self.failure_count}/{self.max_failures}): {error_message}")

    def close(self):
        """Close the handler.

        No resources need to be cleaned up for this handler.
        """
        pass  # No resources to clean up
