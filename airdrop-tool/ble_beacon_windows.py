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
inner payload layout below follows the furiousMAC/continuity project's
documented AirDrop message structure (github.com/furiousMAC/continuity,
messages/airdrop.md), cross-checked against a real captured advertisement
byte dump (`17FF4C000512...`) referenced in an unrelated AirDrop
interoperability project's issue tracker. It is still not an official
Apple spec, so it may not hold across every iOS version.

Requires Windows 10/11 and the `winrt-Windows.Devices.Bluetooth.Advertisement`
and `winrt-Windows.Storage.Streams` packages (see requirements.txt).
"""
import sys
import time

APPLE_COMPANY_ID = 0x004C
AIRDROP_TYPE = 0x05


def _build_payload() -> bytes:
    """AirDrop BLE advertisement payload (Type 0x05, 18-byte body).

    Layout, per furiousMAC/continuity's documented structure:
      [0]     AirDrop sub-type (0x05)
      [1]     length of the body that follows (0x12 = 18)
      [2-9]   8-byte prefix, zero
      [10]    version (0x01)
      [11-18] four 2-byte truncated contact-identifier hashes (AppleID,
              phone, email, email2); all-zero here since this receiver has
              no real contacts to hash — matches AirDrop's "Everyone" mode
              rather than "Contacts Only", which is all this tool supports
              anyway (see certs.py).
      [19]    1-byte suffix, zero
    """
    prefix = bytes(8)
    version = bytes([0x01])
    contact_hashes = bytes(8)  # 4 slots x 2 bytes, all zero
    suffix = bytes([0x00])
    body = prefix + version + contact_hashes + suffix
    return bytes([AIRDROP_TYPE, len(body)]) + body


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
        writer.write_bytes(_build_payload())

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

        print("[airdrop-ble] broadcasting experimental AirDrop BLE beacon")

        # publisher.start() can return before Windows has actually confirmed
        # advertising started (or silently failed, e.g. no BLE-capable
        # radio). Poll the plain `.status` property (NOT an event
        # subscription — registering a WinRT event callback here needs a
        # running message loop that a plain script doesn't have, and can
        # hang indefinitely) so we still catch a silent failure.
        time.sleep(1)
        print(f"[airdrop-ble] publisher status: {publisher.status}")

        self._publisher = publisher
        return True

    def stop(self):
        if self._publisher is not None:
            self._publisher.stop()
            self._publisher = None
