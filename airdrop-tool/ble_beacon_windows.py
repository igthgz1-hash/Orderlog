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
import time

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
                BluetoothLEAdvertisementPublisherStatus,
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
        writer.write_bytes(_build_payload())

        manufacturer_data = BluetoothLEManufacturerData()
        manufacturer_data.company_id = APPLE_COMPANY_ID
        manufacturer_data.data = writer.detach_buffer()

        publisher = BluetoothLEAdvertisementPublisher()
        publisher.advertisement.manufacturer_data.append(manufacturer_data)

        def on_status_changed(_publisher, args):
            status = args.status
            print(f"[airdrop-ble] publisher status changed: {status}")
            if status == BluetoothLEAdvertisementPublisherStatus.ABORTED:
                print(f"[airdrop-ble] advertising aborted, error={args.error}", file=sys.stderr)

        publisher.add_status_changed(on_status_changed)

        try:
            publisher.start()
        except Exception as exc:  # noqa: BLE001 - surface any WinRT/hardware error plainly
            print(f"[airdrop-ble] failed to start BLE advertising: {exc}", file=sys.stderr)
            return False

        # publisher.start() can return before Windows has actually confirmed
        # advertising started (or silently failed, e.g. no BLE-capable radio).
        # Give it a moment, then report the real status instead of assuming
        # success just because start() didn't raise.
        time.sleep(1)
        print(f"[airdrop-ble] publisher status: {publisher.status}")
        if publisher.status != BluetoothLEAdvertisementPublisherStatus.STARTED:
            print(
                "[airdrop-ble] WARNING: status is not STARTED — this PC is likely NOT "
                "actually broadcasting. Check that Bluetooth is on and this machine has "
                "a BLE-capable adapter.",
                file=sys.stderr,
            )

        self._publisher = publisher
        return True

    def stop(self):
        if self._publisher is not None:
            self._publisher.stop()
            self._publisher = None
