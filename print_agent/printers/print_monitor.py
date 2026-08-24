# Backward-compatible import for the original advanced executor.
from printers.print_monitors import (
    monitor_print,
    open_printer,
    close_printer,
    get_jobs,
)

__all__ = [
    "monitor_print",
    "open_printer",
    "close_printer",
    "get_jobs",
]
