"""Local BLE protocol for ResMed Air-family CPAPs (AirSense/AirCurve 11). No Home Assistant deps."""
from .client import AirSenseClient, AirSenseError, AuthError, RpcError
from .protocol import FG_THERAPY_STATES, NAME_PREFIX, SERVICE_UUID, Credentials
from .srp import SrpError

__all__ = [
    "AirSenseClient",
    "AirSenseError",
    "AuthError",
    "RpcError",
    "Credentials",
    "FG_THERAPY_STATES",
    "NAME_PREFIX",
    "SERVICE_UUID",
    "SrpError",
]
