import json
import socket
from dataclasses import dataclass


class BridgeUnavailable(Exception):
    pass


@dataclass(frozen=True)
class BridgeClient:
    host: str
    port: int
    timeout_seconds: float

    def read_state(self) -> dict:
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout_seconds) as connection:
                connection.sendall(b"state\n")
                stream = connection.makefile("r", encoding="utf-8")
                line = stream.readline()
        except OSError as error:
            raise BridgeUnavailable(
                f"cdmp agent bridge not reachable on {self.host}:{self.port} ({error}); "
                "is the game running with a cdmp.asi that has [agent] enabled=1?"
            ) from error
        if not line:
            raise BridgeUnavailable("cdmp agent bridge closed the connection without an answer")
        return json.loads(line)
