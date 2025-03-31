from datetime import datetime
from enum import Enum


class LogLevel(Enum):
    DEBUG = 0
    INFO = 1
    WARN = 2
    ERROR = 3


COLORS = {
    LogLevel.DEBUG: "\x1b[90m",
    LogLevel.INFO: "\x1b[34m",
    LogLevel.WARN: "\x1b[93m",
    LogLevel.ERROR: "\x1b[31m",
}


class _Logger:
    # Name assigned to each process, used to log the process name
    process_name: str = "main"

    def set_process(self, name: str):
        self.process_name = name

    def log(self, level: LogLevel, message: str):
        """
        Logs a message with the given level in the format
        "[TIMESTAMP - PROCESS_NAME - LEVEL] [MESSAGE]"
        """
        print(
            COLORS[level],
            f"[{datetime.now():%H:%M:%S} "
            f"{level.name} - "
            f"{self.process_name:>3}] {message}"
            "\x1b[0m",
        )

    def info(self, message: str):
        self.log(LogLevel.INFO, message)

    def debug(self, message: str):
        self.log(LogLevel.DEBUG, message)

    def warn(self, message: str):
        self.log(LogLevel.WARN, message)

    def error(self, message: str):
        self.log(LogLevel.ERROR, message)


# The logger is a singleton global variable.
# Each process will clone it in the forking process and have its own copy.
Logger = _Logger()
Logger.log(LogLevel.INFO, "Test")
