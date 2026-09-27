#!/usr/bin/env python3
"""Diagnostic: confirm the _airdrop._tcp mDNS service is actually visible.

Run this in a SECOND terminal while airdrop_server.py is running (on the
same PC, or ideally from a different device on the network) to check
whether mDNS advertising is working at all, before troubleshooting the
iPhone/AirDrop side specifically.
"""
import time

from zeroconf import IPVersion, ServiceBrowser, Zeroconf


class Listener:
    def add_service(self, zc, service_type, name):
        info = zc.get_service_info(service_type, name)
        print(f"FOUND: {name}")
        if info:
            addresses = info.parsed_addresses(IPVersion.V4Only)
            print(f"       addresses={addresses} port={info.port} server={info.server}")

    def remove_service(self, zc, service_type, name):
        print(f"REMOVED: {name}")

    def update_service(self, zc, service_type, name):
        pass


def main():
    zc = Zeroconf()
    ServiceBrowser(zc, "_airdrop._tcp.local.", Listener())
    print("Browsing for _airdrop._tcp.local. services for 15 seconds...")
    print("(if nothing prints, the mDNS advertisement isn't reaching this machine)")
    try:
        time.sleep(15)
    finally:
        zc.close()


if __name__ == "__main__":
    main()
