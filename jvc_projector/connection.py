"""Maintains persistant connection"""

import logging
from typing import Callable, Final, Union
import asyncio
from typing_extensions import Self

from jvc_projector.commands import ACKs, Footer, Header, Commands, PowerStates, Enum
from jvc_projector.jvc_projector import JVCProjector

class Connection:
    """Handle network connection stuff"""

    def __init__(self) -> None:
        """init connection"""

        self.host = ""
        self.port = 0
        self.connect_timeout = 0
        # NZ models have password authentication
        self.password = ""
        self.logger: logging.Logger = (logging.getLogger(__name__))
        self._lock = asyncio.Lock()
        self._closed = False
        self._retry_interval = 1
        self._closing = False
        self._halted = False
        self._loop: asyncio.AbstractEventLoop = None
        self.protocol: asyncio.Protocol = None
        # Const values
        self.PJ_OK: Final = ACKs.greeting.value
        self.PJ_ACK: Final = ACKs.pj_ack.value
        self.PJ_REQ: Final = ACKs.pj_req.value


    @classmethod
    async def async_open_connection(
        cls,  # IP
        host: str,
        port: int = 20554,
        # Connection timeout before it will drop
        connect_timeout: int = 10,
        # NZ models need password
        password: str = None,
        loop: asyncio.AbstractEventLoop = None,
        # the protocol
        protocol_class: asyncio.Protocol = JVCProjector,
        # called when state changes
        update_callback: Callable[[str], None] = None,
        
    ) -> Union[Self, tuple[str, bool]]:
        """Create a persistant connection"""

        assert port >= 0, f"Port must be greater than 0: {port}"
        assert host != "", f"Host must not be empty: {host}"
        assert connect_timeout >= 2, f"connect_timeout must be over 1: {connect_timeout}"
        
        connection = cls()
        connection.host = host
        connection.port = port
        connection.connect_timeout = connect_timeout
        connection.password = password
        connection._loop = loop or asyncio.get_event_loop()
        connection._closed = False
        connection._closing = False
        connection._halted = False

        async def connection_lost():
            """Function callback for Protocol class when connection is lost."""
            if not connection._closing:
                await connection.reconnect()
                # TODO: implement reconnect

        connection.protocol = protocol_class(
            connection_lost_callback=connection_lost,
            loop=connection._loop,
            update_callback=update_callback,
        )

        # Init the connection
        msg, success = await connection.reconnect()
        if not success:
            raise Exception(msg)

        return connection
        
    def _get_retry_interval(self):
        return self._retry_interval

    def _reset_retry_interval(self):
        self._retry_interval = 1

    def _increase_retry_interval(self):
        self._retry_interval = min(300, 1.5 * self._retry_interval)
    
    def close(self):
        """Close the AVR device connection and don't try to reconnect."""
        self.logger.debug("Closing connection to AVR")
        self._closing = True
        if self.protocol.transport:
            self.protocol.transport.close()

    def halt(self):
        """Close the AVR device connection and wait for a resume() request."""
        self.logger.warning("Halting connection to AVR")
        self._halted = True
        if self.protocol.transport:
            self.protocol.transport.close()

    def resume(self):
        """Resume the AVR device connection if we have been halted."""
        self.logger.warning("Resuming connection to AVR")
        self._halted = False

    async def reconnect(self):
        """Initiate keep-alive connection"""
        while True:
            try:
                if self._halted:
                    await asyncio.sleep(2)

                self.logger.debug("Connecting to JVC Projector: %s:%s", self.host, self.port)
                async with self._lock:
                    # transport, protocol = await self._loop.create_connection(
                    #     lambda: self.protocol, self.host, self.port
                    # )
                    reader, writer = await asyncio.open_connection(self.host, self.port, loop=self._loop)
                    self.logger.debug("Connected to JVC Projector")
                    # create a reader and writer to do handshake
                    
                async with self._lock:
                    self.logger.debug("Handshaking")
                    result, success = await self._async_handshake(reader, writer)
                    if not success:
                        return result, success
                    self.logger.debug("Handshake complete")
                self._reset_retry_interval()
                return "Connection done", True

            # includes conn refused
            except OSError as err:
                self._increase_retry_interval()
                interval = self._get_retry_interval()
                self.logger.warning("Connecting failed, retrying in %i seconds", interval)
                if not self._closing:
                    return f"Connection failed: {err}", False
                await asyncio.sleep(interval)
            except asyncio.TimeoutError:
                self._increase_retry_interval()
                interval = self._get_retry_interval()
                self.logger.warning("Connection timed out, retrying in %i seconds", interval)
                if not self._closing:
                    return "Connection timedout", False
                await asyncio.sleep(interval)

    async def _async_handshake(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> tuple[str, bool]:
        """
        Do the 3 way handshake

        Projector sends PJ_OK, client sends PJREQ within 5 seconds, projector replies with PJACK
        first, after connecting, see if we receive PJ_OK. If not, raise exception
        """
        if self.password:
            pj_req = self.PJ_REQ + f"_{self.password}".encode()
        else:
            pj_req = self.PJ_REQ
        # 3 step handshake
        msg_pjok = await reader.read(len(self.PJ_OK))
        print(msg_pjok)
        if msg_pjok != self.PJ_OK:
            result = (
                f"Projector did not reply with correct PJ_OK greeting: {msg_pjok}"
            )
            success = False

            return result, success

        # try sending PJREQ, if there's an error, raise exception
        try:
            writer.write(pj_req)
            await writer.drain()
        except asyncio.TimeoutError as err:
            result = f"Timeout sending PJREQ {err}"
            success = False
            writer.close()

            return result, success

        # see if we receive PJACK, if not, raise exception
        msg_pjack = await reader.read(len(self.PJ_ACK))
        if msg_pjack != self.PJ_ACK:
            result = f"Exception with PJACK: {msg_pjack}"
            success = False

            return result, success

        return "ok", True