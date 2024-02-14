import asyncio
import logging
from typing import Union, Tuple, Final
from enum import Enum

import logging
import time
from jvc_projector.commands import (
    InputLevel,
    ColorSpaceModes,
    EshiftModes,
    ACKs,
    Footer,
    Header,
    Commands,
    PowerStates,
    PictureModes,
    InstallationModes,
    InputModes,
    LaserDimModes,
    Enum,
    LowLatencyModes,
    ContentTypes,
    HdrProcessing,
    SourceStatuses,
    TheaterOptimizer,
    HdrData,
    LampPowerModes,
    LaserPowerModes,
    AspectRatioModes,
    MaskModes,
    HdrLevel,
    ContentTypeTrans,
)

# Assume imported Enums and Constants: Header, Commands, Footer, ACKs, Final
# As they were not part of the original code, I'm skipping their definitions.

class AsyncJVCProjector:
    """JVC Projector Control"""

    def __init__(
        self,
        host: str,
        password: str = "",
        logger: logging.Logger = logging.getLogger(__name__),
        port: int = 20554,
        connect_timeout: int = 3,
    ):
        self.host = host
        self.port = port
        self.password = password
        self.connect_timeout = connect_timeout
        self.logger = logger
        self.PJ_OK = ACKs.greeting.value
        self.PJ_ACK = ACKs.pj_ack.value
        self.PJ_REQ = ACKs.pj_req.value
        self.reader = None
        self.writer = None
        self.model_family = ""

    async def open_connection(self) -> bool:
        self.logger.debug("Starting open connection")
        msg, success = await self.reconnect()
        if not success:
            self.logger.error(msg)
        return success

    async def reconnect(self) -> Tuple[str, bool]:
        while True:
            try:
                self.logger.info(f"Connecting to JVC Projector: {self.host}:{self.port}")
                self.reader, self.writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=self.connect_timeout
                )
                self.logger.info("Connected to JVC Projector")
                self.logger.debug("Handshaking")
                result, success = await self._handshake()
                if not success:
                    return result, success
                self.logger.debug("Handshake complete and we are connected")
                return "Connection done", True

            except asyncio.TimeoutError:
                self.logger.warning("Connection timed out, retrying in 2 seconds")
                await asyncio.sleep(2)
            except OSError as err:
                self.logger.warning("Connecting failed, retrying in 2 seconds")
                self.logger.debug(err)
                await asyncio.sleep(2)

    async def _handshake(self) -> Tuple[str, bool]:
        if self.password:
            pj_req = self.PJ_REQ + f"_{self.password}".encode()
            self.logger.debug("connecting with password hunter2")
        else:
            pj_req = self.PJ_REQ

        try:
            msg_pjok = await self.reader.readexactly(len(self.PJ_OK))
            self.logger.debug(msg_pjok)
            if msg_pjok != self.PJ_OK:
                result = f"Projector did not reply with correct PJ_OK greeting: {msg_pjok}"
                self.logger.error(result)
                return result, False

            self.writer.write(pj_req)
            await self.writer.drain()

            msg_pjack = await self.reader.readexactly(len(self.PJ_ACK))
            if msg_pjack != self.PJ_ACK:
                result = f"Exception with PJACK: {msg_pjack}"
                self.logger.error(result)
                return result, False

            self.logger.debug("Handshake successful")
        except asyncio.IncompleteReadError:
            return "handshake incomplete read", False

        self.model_family = await self._get_modelfamily()
        self.logger.debug(f"Model code is {self.model_family}")
        return "ok", True

    async def _get_modelfamily(self) -> str:
        cmd = (
            Header.reference.value
            + Header.pj_unit.value
            + Commands.get_model.value
            + Footer.close.value
        )
        res, _ = await self._send_command(
            cmd,
            command_type=Header.reference.value,
            ack=ACKs.model.value,
        )
        models = {
            # Define your models here
        }
        model_res = self._replace_headers(res).decode()
        self.logger.debug(model_res)
        return models.get(model_res[-4:], "Unsupported")

    # You can add other functions like _send_command, _do_command, _check_received_msg, and exec_command
    # Just replace synchronous code with asynchronous code, using 'await' before asyncio related methods.

    # Don't forget to close the connection
    def close_connection(self):
        if self.writer:
            self.writer.close()
            self.writer = None
            self.reader = None
