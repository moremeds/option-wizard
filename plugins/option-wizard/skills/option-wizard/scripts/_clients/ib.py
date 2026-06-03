"""Thin ib_insync wrapper used by option-wizard for read+write IB access.

Defaults match the trader's IB Gateway live: 127.0.0.1:4001. The skill
shifts the base client_id by PID modulo 100 so a cron job and a
SessionStart hook firing on the same morning get distinct IDs.
"""

from __future__ import annotations

import os as _os
from dataclasses import dataclass, field
from typing import Any

from ib_insync import IB, Option, Stock, util  # noqa: F401  (used downstream)


def _default_client_id() -> int:
    """Avoid collision between concurrent processes.

    Caller can override via OPTION_WIZARD_IB_CLIENT_ID env var; otherwise
    we shift the base 99 by PID modulo 100.
    """
    override = _os.environ.get("OPTION_WIZARD_IB_CLIENT_ID")
    if override is not None:
        return int(override)
    return 99 + (_os.getpid() % 100)


@dataclass
class IBClient:
    host: str = "127.0.0.1"
    port: int = 4001
    client_id: int = field(default_factory=_default_client_id)
    timeout: int = 10

    def __post_init__(self) -> None:
        self._ib = IB()

    def connect(self) -> None:
        if not self._ib.isConnected():
            self._ib.connect(
                self.host, self.port, clientId=self.client_id, timeout=self.timeout
            )

    def disconnect(self) -> None:
        if self._ib.isConnected():
            self._ib.disconnect()

    def __enter__(self) -> "IBClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.disconnect()

    # read --------------------------------------------------------

    def get_positions(self) -> list[Any]:
        self.connect()
        return list(self._ib.positions())

    def get_account_summary(self) -> dict[str, Any]:
        self.connect()
        rows = self._ib.accountSummary()
        return {r.tag: r.value for r in rows}

    def get_open_orders(self) -> list[Any]:
        self.connect()
        return list(self._ib.openTrades())

    # write -------------------------------------------------------

    def place_order(self, contract: Any, order: Any) -> Any:
        """Place an order through ib_insync. Returns the Trade object.

        Caller is responsible for confirming the order intent before
        calling this (see scripts.ib_order.build_preflight).
        """
        self.connect()
        return self._ib.placeOrder(contract, order)
