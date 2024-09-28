from logger import Logger
import logging


def main():
    log_bot = Logger(
        "log_bot",
        "logs/test_log.log",
        logging.INFO,
        True
    )

    log_bot.info("Starting Log Test")
    log_bot.debug("Debug message.")
    log_bot.warning("This is a warning")
    log_bot.error("This is an error")
    log_bot.critical("This is a critical error")


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    main()
