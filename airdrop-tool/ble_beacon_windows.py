"""Windows-only Bluetooth LE beacon that advertises this PC as an AirDrop
receiver.

Why this exists: testing against a real iPhone showed that iOS's AirDrop
share sheet does NOT populate its device list from Bonjour/mDNS alone (a
generic DNS-SD browser app could see our mDNS service, but AirDrop itself
still showed "No People Found"). Per the "Open Sesame" AirDrop
reverse-engineering research (Heinrich et al., ACM WiSec 2021), a receiving
device also continuously broadcasts a Bluetooth LE advertisement — the
sender's Share Sheet watches for that beacon and only then attempts the
mDNS/HTTPS handshake this tool already implements.

Confidence level: the outer envelope (Apple's manufacturer ID 0x004C, an
AirDrop sub-type byte of 0x05 inside Apple's multiplexed "Continuity"
advertisement format) is corroborated by multiple public write-ups. The
exact inner payload bytes are NOT — Apple has never documented this, and
the byte layout below is a best-effort reconstruction. If AirDrop still
doesn't show this PC after enabling this beacon, that inner payload is the
first thing to re-check, ideally by comparing against a real Apple
device's advertisement captured with a BLE scanner app (e.g. nRF Connect)
on another phone.

Requires Windows 10/11 and the `winrt-Windows.Devices.Bluetooth.Advertisement`
and `winrt-Windows.Storage.Streams` packages (see requirements.txt).
"""
import sys

APPLE_COMPANY_ID = 0x004C
AIRDROP_TYPE = 0x05


def _build_payload() -> bytes:
    """Best-effort AirDrop BLE advertisement payload.

    Layout (reconstructed, not officially documented):
      [0]    AirDrop sub-type (0x05)
      [1]    length of the remaining bytes
      [2-3]  version/prefix bytes
      [4:]   up to 4 truncated (2-byte) contact-identifier hashes;
             all-zero here, meaning "no contact restriction" (matches
             AirDrop's "Everyone" receiving mode rather than "Contacts Only").
    """
    version_prefix = bytes([0x00, 0x01])
    contact_hash_slots = bytes(8)  # 4 slots x 2 bytes, all zero
    inner = version_prefix + contact_hash_slots
    return bytes([AIRDROP_TYPE, len(inner)]) + inner


class AirDropBleBeacon:
    def __init__(self):
        self._publisher = None

    def start(self):
        if sys.platform != "win32":
            print("[airdrop-ble] BLE beacon is only implemented for Windows; skipping.")
            return False
        try:
            from winrt.windows.devices.bluetooth.advertisement import (
                BluetoothLEAdvertisementPublisher,
                BluetoothLEManufacturerData,
            )
            from winrt.windows.storage.streams import DataWriter
        except ImportError:
            print(
                "[airdrop-ble] winrt Bluetooth packages not installed, so the BLE beacon "
                "won't run (AirDrop's UI likely won't show this PC without it).\n"
                "              Install with: pip install winrt-Windows.Devices.Bluetooth.Advertisement "
                "winrt-Windows.Storage.Streams",
                file=sys.stderr,
            )
            return False

        writer = DataWriter()
        writer.write_bytes(list(_build_payload()))

        manufacturer_data = BluetoothLEManufacturerData()
        manufacturer_data.company_id = APPLE_COMPANY_ID
        manufacturer_data.data = writer.detach_buffer()

        publisher = BluetoothLEAdvertisementPublisher()
        publisher.advertisement.manufacturer_data.append(manufacturer_data)

        try:
            publisher.start()
        except Exception as exc:  # noqa: BLE001 - surface any WinRT/hardware error plainly
            print(f"[airdrop-ble] failed to start BLE advertising: {exc}", file=sys.stderr)
            return False

        self._publisher = publisher
        print("[airdrop-ble] broadcasting experimental AirDrop BLE beacon")
        return True

    def stop(self):
        if self._publisher is not None:
            self._publisher.stop()
            self._publisher = None
