import os
import socket
from pathlib import Path
from typing import Optional

from vla.utils.logging import get_logger

log = get_logger("lock")

# Socket path - in user's runtime dir or /tmp
_SOCKET_DIR = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
_SOCKET_PATH = _SOCKET_DIR / "vla-daemon.sock"

class DaemonLock:

    def __init__(self, socket_path: Path = None):
        self.socket_path = socket_path or _SOCKET_PATH
        self._socket: Optional[socket.socket] = None
        
    def acquire(self) -> bool:

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
        
    def release(self):

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
        """Check if the socket is actually being used by a running daemon."""
        try:
            test_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            test_socket.settimeout(1)
            test_socket.connect(str(self.socket_path))
            test_socket.close()
            return True  # Connection succeeded, daemon is running
        except (socket.error, OSError):
            return False  # Connection failed, socket is stale
        
    def __enter__(self):
        if not self.acquire():
            raise RuntimeError("Could not acquire daemon lock - is another daemon running?")
        return self
    
    def __exit__(self, *args):
        self.release()

def is_daemon_running(socket_path: Path = None) -> bool:
    """
    Check if the daemon is running.
    
    Returns:
        True if daemon is running and responsive
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
    """Get the daemon socket path."""
    return _SOCKET_PATH
