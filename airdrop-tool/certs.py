"""Self-signed TLS certificate for the AirDrop HTTPS endpoint.

Real AirDrop uses a certificate tied to the sender/receiver's Apple ID
push-notification identity. We can't obtain one of those, so we generate
a plain self-signed cert instead. This is enough for "Everyone" AirDrop
discovery mode, where the receiving device does not verify the sender's
identity against a contact.
"""
import datetime
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

CERT_PATH = Path(__file__).parent / ".cert.pem"
KEY_PATH = Path(__file__).parent / ".key.pem"


def _generate(common_name: str) -> tuple[bytes, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, common_name)]
    )
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName(common_name), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return cert_pem, key_pem


def ensure_cert(common_name: str) -> tuple[Path, Path]:
    """Return (cert_path, key_path), generating a cached self-signed pair if needed."""
    if not CERT_PATH.exists() or not KEY_PATH.exists():
        cert_pem, key_pem = _generate(common_name)
        CERT_PATH.write_bytes(cert_pem)
        KEY_PATH.write_bytes(key_pem)
    return CERT_PATH, KEY_PATH
