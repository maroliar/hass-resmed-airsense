"""SRP-6a key exchange used by the ResMed "FIG" stack for first-time pairing.

Reverse-engineered from libpacific-figlib.so (fig::detail::SrpKeyExchange):
  group  = RFC 5054 2048-bit, g = 2, H = SHA-256, PAD() = left-pad to 256 bytes
  no identity (I) anywhere; the password is the passKey shown on the device screen (ASCII)
  a      = 32 random bytes,           A = g^a mod N
  u      = H(PAD(A) | PAD(B))
  k      = H(PAD(N) | PAD(g))
  x      = H(salt | H(passKey))
  S      = (B - k*g^x) ^ (a + u*x) mod N
  K      = H(PAD(S))                                   -> masterPairKey
  M1     = H(H(PAD(N)) xor H(PAD(g)) | salt | PAD(A) | PAD(B) | K)   -> clientConfirmation
  M2     = H(PAD(A) | M1 | K)                          -> serverConfirmation
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

N = int(
    "AC6BDB41324A9A9BF166DE5E1389582FAF72B6651987EE07FC3192943DB56050A37329CB"
    "B4A099ED8193E0757767A13DD52312AB4B03310DCD7F48A9DA04FD50E8083969EDB767B0"
    "CF6095179A163AB3661A05FBD5FAAAE82918A9962F0B93B855F97993EC975EEAA80D740A"
    "DBF4FF747359D041D5C33EA71D281E446B14773BCA97B43A23FB801676BD207A436C6481"
    "F1D2B9078717461A5B9D32E688F87748544523B524B0D57D5EA77A2775D2ECFA032CFBDB"
    "F52FB3786160279004E57AE6AF874E7303CE53299CCC041C7BC308D82A5698F3A8D0C382"
    "71AE35F8E9DBFBB694B5C803D89F7AE435DE236D525F54759B65E372FCD68EF20FA7111F"
    "9E4AFF73",
    16,
)
G = 2
N_BYTES = 256


class SrpError(Exception):
    """Key exchange failed (bad server values or wrong passKey)."""


def _h(*parts: bytes) -> bytes:
    return hashlib.sha256(b"".join(parts)).digest()


def _pad(n: int) -> bytes:
    return n.to_bytes(N_BYTES, "big")


def _int(b: bytes) -> int:
    return int.from_bytes(b, "big")


_K = _int(_h(_pad(N), _pad(G)))
_HNG = bytes(a ^ b for a, b in zip(_h(_pad(N)), _h(_pad(G))))


def _x(salt: bytes, passkey: str) -> int:
    return _int(_h(salt, _h(passkey.encode("ascii"))))


def client_proof(A: bytes, B: bytes, salt: bytes, key: bytes) -> bytes:
    return _h(_HNG, salt, A, B, key)


def server_proof(A: bytes, m1: bytes, key: bytes) -> bytes:
    return _h(A, m1, key)


class SrpClient:
    """Client side of the pairing PAKE. One instance per pairing attempt."""

    def __init__(self, passkey: str, *, _a: bytes | None = None) -> None:
        self._passkey = passkey
        self._a = _int(_a if _a is not None else secrets.token_bytes(32))
        self.A = _pad(pow(G, self._a, N))
        self.key: bytes | None = None
        self._m1: bytes | None = None

    @property
    def public_key_hex(self) -> str:
        return self.A.hex().upper()

    def process_challenge(self, server_pk_hex: str, salt_hex: str) -> str:
        """Takes the StartKeyExchange result; returns clientConfirmation (hex)."""
        b_int = int(server_pk_hex, 16)
        B = _pad(b_int)
        salt = bytes.fromhex(salt_hex)
        u = _int(_h(self.A, B))
        if b_int % N == 0 or u % N == 0:
            raise SrpError("invalid server public key")
        x = _x(salt, self._passkey)
        S = pow((b_int - _K * pow(G, x, N)) % N, self._a + u * x, N)
        self.key = _h(_pad(S))
        self._m1 = client_proof(self.A, B, salt, self.key)
        return self._m1.hex().upper()

    def verify_server(self, server_confirmation_hex: str) -> bytes:
        """Checks M2; returns the masterPairKey (32 bytes)."""
        if self.key is None or self._m1 is None:
            raise SrpError("process_challenge() not called")
        expected = server_proof(self.A, self._m1, self.key)
        if not hmac.compare_digest(expected, bytes.fromhex(server_confirmation_hex)):
            raise SrpError("server confirmation mismatch")
        return self.key


class SrpServer:
    """Device side, for tests only (mirrors what the AirSense does)."""

    def __init__(self, passkey: str, *, salt: bytes | None = None, _b: bytes | None = None) -> None:
        self.salt = salt if salt is not None else secrets.token_bytes(32)
        self._v = pow(G, _x(self.salt, passkey), N)
        self._b = _int(_b if _b is not None else secrets.token_bytes(32))
        self.B = _pad((_K * self._v + pow(G, self._b, N)) % N)
        self.key: bytes | None = None

    def process_client(self, client_pk_hex: str, m1_hex: str) -> str:
        a_int = int(client_pk_hex, 16)
        A = _pad(a_int)
        u = _int(_h(A, self.B))
        S = pow(a_int * pow(self._v, u, N) % N, self._b, N)
        key = _h(_pad(S))
        m1 = client_proof(A, self.B, self.salt, key)
        if not hmac.compare_digest(m1, bytes.fromhex(m1_hex)):
            raise SrpError("client confirmation mismatch (wrong passKey)")
        self.key = key
        return server_proof(A, m1, key).hex().upper()
