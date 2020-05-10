import asyncio
from io import BytesIO

import serial
from bitstring import BitArray


class Serial:
    _sepr = b'\x91'
    _delim = b'\x92'
    _term = b'\x23'

    def __init__(self, port: str, baud: int = 115200, loop: asyncio.AbstractEventLoop = None, debug: bool = False,
                 monitor: bool = True):
        self.executor = None
        if loop is None:
            self.loop = asyncio.get_event_loop()
        else:
            self.loop = loop
        self.loop.set_debug(enabled=debug)

        self._port = port
        self._baud = baud
        self._monitor = monitor

    async def _poller(self):
        with serial.Serial(self._port, self._baud) as port:
            buffer = BytesIO()
            while port.is_open:
                chunk = port.read()
                buffer.write(chunk)
                try:
                    if buffer.getvalue().endswith(self._term):
                        sensor_data = []
                        data = buffer.getvalue().replace(self._term, b'').rstrip(self._delim).split(self._delim)
                        for sensor_raw in data:
                            address, temp = sensor_raw.split(self._sepr)
                            address = "".join([char for char in ["%02X" % char for char in address] if char != '00'])
                            temp = BitArray(bytes([char for char in temp])).uint / 128
                            sensor_data.append({"sensor": address, "temp": round(temp, 2)})
                        for reading in sensor_data:
                            await self.on_reading(reading)
                        buffer.truncate(0)
                        buffer.seek(0)
                except ValueError:
                    buffer.truncate(0)
                    buffer.seek(0)
                await asyncio.sleep(0)

    async def on_start(self):
        return None

    async def on_reading(self, reading):
        return reading

    def run(self):
        self.loop.create_task(self.on_start())
        if self._monitor:
            self.loop.create_task(self._poller())
        self.loop.run_forever()
