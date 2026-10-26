"""DevBroker -- a pure-Python amqtt broker in a background thread.

Dev/test only. On the real board the broker is the Home Assistant Mosquitto
add-on; nothing here ships to hardware.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import warnings

from amqtt.broker import Broker

# amqtt is chatty and emits its own deprecation notices for the config format;
# keep dev/test output clean. (Dev-only module -- never ships to hardware.)
logging.getLogger("amqtt").setLevel(logging.WARNING)
logging.getLogger("transitions").setLevel(logging.WARNING)
warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"amqtt.*")


class DevBroker:
    def __init__(self, host: str = "127.0.0.1", port: int = 1883):
        self.config = {
            "listeners": {
                "default": {"type": "tcp", "bind": f"{host}:{port}", "max_connections": 50},
            },
            "sys_interval": 0,
            "auth": {"allow-anonymous": True, "plugins": ["auth_anonymous"]},
            "topic-check": {"enabled": False},
        }
        self._loop: asyncio.AbstractEventLoop | None = None
        self._broker: Broker | None = None
        self._thread: threading.Thread | None = None

    def start(self, timeout: float = 10.0) -> None:
        ready = threading.Event()

        def run():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

            async def _boot():
                # amqtt's Broker() grabs the running loop at construction, so it
                # must be built inside the loop, not before it.
                self._broker = Broker(self.config)
                await self._broker.start()

            self._loop.run_until_complete(_boot())
            ready.set()
            self._loop.run_forever()

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        if not ready.wait(timeout):
            raise RuntimeError("amqtt broker failed to start in time")

    def stop(self) -> None:
        if self._loop is None:
            return
        async def _shutdown():
            await self._broker.shutdown()
        try:
            fut = asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
            fut.result(timeout=5)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
