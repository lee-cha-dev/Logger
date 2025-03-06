"""Module for buffered logging handler implementation."""

import logging
import threading


class BufferedHandler(logging.Handler):
    """Handler that buffers log records and flushes periodically.

    This handler collects log records in a buffer and flushes them either when
    the buffer reaches a specified capacity or after a specified time interval.
    This is useful for high-throughput logging scenarios where immediate
    processing of individual log records might cause performance bottlenecks.

    Attributes:
        capacity (int): Maximum number of records to buffer before flushing.
        flush_interval (float): Time in seconds between forced buffer flushes.
    """
    def __init__(self, capacity=100, flush_interval=5.0):
        """Initialize the buffered handler.

        Args:
            capacity: Maximum number of records to hold before flushing.
                Default is 100.
            flush_interval: Time in seconds between automatic flushes.
                Default is 5.0 seconds.
        """
        super().__init__()
        self.buffer = []
        self.capacity = capacity
        self.flush_interval = flush_interval
        self.lock = threading.Lock()
        self.timer = None
        self.target_handler = None
        # Don't schedule a flush in __init__
        # Do it in emit instead - causing process to hang.
        # self._schedule_flush()

    def set_target(self, handler):
        """Set a target handler to receive the processed records.

        Args:
            handler: The handler that will process the buffered records
                when they are flushed.
        """
        self.target_handler = handler

    def _schedule_flush(self):
        """Schedule the next automatic flush operation.

        Creates a timer that will trigger a flush after the specified interval.
        The timer is set as a daemon thread to prevent it from blocking
        application exit.
        """
        self.timer = threading.Timer(self.flush_interval, self.flush)
        self.timer.daemon = True
        self.timer.start()

    def emit(self, record):
        """Add a log record to the buffer.

        This method is called by the logging framework for each log record.
        It adds the record to the buffer and triggers a flush if the buffer
        reaches its capacity.

        Args:
            record: The log record to be buffered.
        """
        with self.lock:
            # Start timer if it doesn't exist
            if self.timer is None:
                self._schedule_flush()

            self.buffer.append(record)
            if len(self.buffer) >= self.capacity:
                self.flush()

    def flush(self):
        """Process all buffered log records.

        Acquires the lock, copies and clears the buffer, then releases the lock
        before processing the records to minimize lock contention. If a target
        handler is configured, each record is sent to that handler; otherwise,
        records are formatted and printed to the console.
        """
        records_to_process = []
        with self.lock:
            if not self.buffer:
                return
            # Copy buffer contents and clear the buffer
            records_to_process = self.buffer.copy()
            self.buffer.clear()

        # Process the records outside the lock to avoid blocking
        for record in records_to_process:
            try:
                # Format the record using the formatter
                formatted_record = self.format(record)

                # If a target handler is set, forward the formatted record
                if self.target_handler:
                    self.target_handler.emit(record)
                else:
                    # Default behavior: just print the formatted record
                    print(formatted_record)
            except Exception as e:
                # Don't let one failed record prevent processing others
                print(f"Error processing log record: {e}")

        self._schedule_flush()

    def force_flush_for_testing(self):
        """Force an immediate flush for testing purposes."""
        # Cancel the existing timer
        if self.timer:
            self.timer.cancel()
            self.timer = None

        # Manually flush without rescheduling
        with self.lock:
            if not self.buffer:
                return
            records_to_process = self.buffer.copy()
            self.buffer.clear()

        for record in records_to_process:
            try:
                formatted_record = self.format(record)
                if self.target_handler:
                    self.target_handler.emit(record)
                else:
                    print(formatted_record)
            except Exception as e:
                print(f"Error processing log record: {e}")

    def close(self):
        """Clean up resources used by the handler."""
        if self.timer:
            try:
                self.timer.cancel()
            except Exception as e:
                pass  # Ignore any errors during cancellation
            self.timer = None

        try:
            self.flush()
        except Exception as e:
            pass  # Ignore any errors during final flush
        super().close()
