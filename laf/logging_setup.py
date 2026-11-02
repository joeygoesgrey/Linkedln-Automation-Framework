"""Root logger setup that writes one timestamped file and prints to console."""

import logging
from datetime import datetime
from pathlib import Path

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def configure_logging(debug: bool, log_dir: str = "logs") -> Path:
    """Set up the root logger with one file handler and one console handler.

    WHY
        Without one shared setup each module prints to a different place and a
        debug run leaves no file to inspect later.

    Args
        debug: true to let DEBUG lines reach the log file.
        log_dir: folder that holds the log file, defaulting to logs.

    Returns
        Path: the log file that was opened.

    Raises
        OSError: when the folder cannot be made or the file cannot be opened.

    MUTATIONS
        write: creates the log folder, closes and removes any root handlers,
        then attaches a file handler and a console handler to the root logger.
    """
    directory = Path(log_dir)
    directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_file = directory / f"laf_{timestamp}.log"

    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()

    root.setLevel(logging.DEBUG if debug else logging.INFO)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    return log_file
