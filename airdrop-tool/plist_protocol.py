"""Binary-plist request/response bodies for AirDrop's HTTP endpoints.

Reconstructed from public write-ups of the reverse-engineered AirDrop
protocol (e.g. the OpenDrop project and the "Open Sesame" research paper).
Apple has never published this format, so field names/values here are a
best-effort match to what real senders expect — not a guarantee against
every iOS/macOS version.
"""
import plistlib
from dataclasses import dataclass, field


def loads(data: bytes) -> dict:
    if not data:
        return {}
    return plistlib.loads(data)


def dumps(obj: dict) -> bytes:
    return plistlib.dumps(obj, fmt=plistlib.FMT_BINARY)


def discover_response(computer_name: str) -> bytes:
    return dumps(
        {
            "ReceiverComputerName": computer_name,
            "ReceiverModelName": "PC",
        }
    )


def ask_accept_response() -> bytes:
    return dumps({})


@dataclass
class AskRequest:
    sender_id: str
    sender_computer_name: str
    files: list = field(default_factory=list)

    @property
    def file_names(self) -> list[str]:
        return [f.get("FileName", "?") for f in self.files]


def parse_ask_request(data: bytes) -> AskRequest:
    plist = loads(data)
    return AskRequest(
        sender_id=plist.get("SenderID", "unknown"),
        sender_computer_name=plist.get("SenderComputerName", "Unknown device"),
        files=plist.get("Files", []),
    )
