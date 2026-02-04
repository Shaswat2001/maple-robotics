"""
Daemon locking utilities.

This module provides Unix socket-based locking to ensure only one instance
of the MAPLE daemon runs at a time. It uses filesystem Unix domain sockets
as a locking mechanism, which automatically releases when a process terminates.

Key features:
- Single daemon instance enforcement
- Automatic stale lock detection and cleanup
- Context manager support for RAII pattern
- Socket liveness checking
- Runtime directory support (XDG_RUNTIME_DIR)

The DaemonLock class uses bind() semantics on Unix sockets - only one process
can bind to a socket path at a time. This provides a reliable, OS-level locking
mechanism that automatically releases if the daemon crashes.
"""

import os
import socket
from pathlib import Path
from typing import Optional

from maple.utils.logging import get_logger

log = get_logger("lock")

# Socket path - in user's runtime dir or /tmp
_SOCKET_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
_SOCKET_PATH = _SOCKET_DIR / "vla-daemon.sock"

class DaemonLock:
    """
    Unix socket-based lock for ensuring single daemon instance.
    
    Implements a file-based locking mechanism using Unix domain sockets.
    Only one process can bind to a socket path at a time, providing
    reliable mutex semantics. The lock automatically releases when the
    process terminates, preventing permanent lock files.
    
    The class detects and removes stale locks (socket files that exist
    but no process is listening on them) to handle crash recovery.
    
    Supports context manager protocol for automatic lock acquisition
    and release using the 'with' statement.
    """

    def __init__(self, socket_path: Path = None):
        """
        Initialize the DaemonLock.
        
        Creates a lock instance with the specified socket path. Does not
        acquire the lock - call acquire() or use as context manager.
        
        :param socket_path: Optional custom path for the socket file.
                           Defaults to XDG_RUNTIME_DIR/vla-daemon.sock
                           or /tmp/vla-daemon.sock.
        """
        self.socket_path = socket_path or _SOCKET_PATH
        self._socket: Optional[socket.socket] = None

    def acquire(self) -> bool:
        """
        Attempt to acquire the daemon lock.
        
        Tries to bind to the Unix socket path. If successful, the lock
        is held until release() is called or the process terminates.
        
        Handles stale locks by testing connectivity - if a socket file
        exists but no daemon responds, it's removed and lock acquisition
        is retried.
        
        :return: True if lock was successfully acquired, False if another
                daemon is already running or lock acquisition failed.
        """
        if self._socket:
            return True

        try:
            if self.socket_path.exists():
                if self._is_socket_alive():
                    log.debug("Daemon already running (socket in use)")
                    return False
                else:
                    # Stale socket, remove it
                    log.debug("Removing stale socket file")
                    self.socket_path.unlink()

            self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._socket.bind(str(self.socket_path))
            self._socket.listen(1)
            self._socket.setblocking(False)

            log.debug(f"Daemon lock acquired: {self.socket_path}")
            return True

        except OSError as e:
            log.debug(f"Failed to acquire lock: {e}")
            if self._socket:
                self._socket.close()
                self._socket = None
            return False

    def release(self) -> None:
        """
        Release the daemon lock.
        
        Closes the socket and removes the socket file. Safe to call
        multiple times or when lock is not held. Automatically called
        when used as a context manager.
        
        After release, the lock can be acquired again if needed.
        """
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None

        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except Exception:
                pass

        log.debug("Daemon lock released")

    def _is_socket_alive(self) -> bool:
        """
        Check if the socket is actually being used by a running daemon.
        
        Tests connectivity to the socket by attempting a connection.
        A successful connection indicates a daemon is actively listening.
        A failed connection indicates a stale socket file.
        
        :return: True if daemon is running and listening on the socket,
                False if socket file is stale (no daemon listening).
        """
        try:
            test_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            test_socket.settimeout(1)
            test_socket.connect(str(self.socket_path))
            test_socket.close()
            return True  # Connection succeeded, daemon is running
        except (socket.error, OSError):
            return False  # Connection failed, socket is stale

    def __enter__(self) -> None:
        """
        Enter context manager - acquire lock.
        
        Attempts to acquire the daemon lock. Raises RuntimeError if
        acquisition fails (another daemon is running).
        
        :return: Self for use in 'with' statement.
        :raises RuntimeError: If lock cannot be acquired.
        """
        if not self.acquire():
            raise RuntimeError("Could not acquire daemon lock - is another daemon running?")
        return self

    def __exit__(self, *args) -> None:
        """
        Exit context manager - release lock.
        
        Automatically releases the lock when exiting the 'with' block,
        even if an exception occurred.
        
        :param args: Exception information (type, value, traceback) if
                    an exception occurred, otherwise (None, None, None).
        """
        self.release()

def is_daemon_running(socket_path: Path = None) -> bool:
    """
    Check if the MAPLE daemon is currently running.
    
    Tests for daemon presence by checking socket file existence and
    attempting to connect. Returns False if socket doesn't exist or
    if connection fails (stale socket).
    
    This is a non-invasive check that doesn't interfere with the
    running daemon.
    
    :param socket_path: Optional custom socket path to check.
                       Defaults to the standard daemon socket path.
    :return: True if daemon is running and responsive, False otherwise.
    """
    socket_path = socket_path or _SOCKET_PATH

    if not socket_path.exists():
        return False

    try:
        test_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        test_socket.settimeout(2)
        test_socket.connect(str(socket_path))
        test_socket.close()
        return True
    except (socket.error, OSError):
        return False

def get_socket_path() -> Path:
    """
    Get the default daemon socket path.
    
    Returns the path where the daemon socket file is located. This
    respects the XDG_RUNTIME_DIR environment variable if set, otherwise
    falls back to /tmp.
    
    :return: Path object pointing to the daemon socket file location.
    """
    return _SOCKET_PATH