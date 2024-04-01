"""
Implements the JVC protocol
"""

import asyncio
from typing import Union
import logging
from dataclasses import dataclass
import math

from jvc_projector.command_runner import JVCCommander
from jvc_projector.commands import (
    PJ_ACK,
    PJ_OK,
    PJ_REQ,
    ACKs,
    Commands,
    Enum,
    Footer,
    Header,
    LowLatencyModes,
    PowerStates,
    model_map,
)
from jvc_projector.error_classes import (
    CommandTimeoutError,
    ConnectionClosedError,
)


@dataclass
class JVCInput:
    """JVC Projector Input"""

    host: str
    password: str
    port: int
    connect_timeout: int


@dataclass
class JVCAttributes:  # pylint: disable=too-many-instance-attributes
    """JVC Projector Attributes"""

    power_state: bool = False
    signal_status: bool = ""
    picture_mode: str = ""
    resolution: str = ""
    low_latency: bool = False
    laser_power: str = ""
    laser_value: int = 0
    laser_mode: str = ""
    lamp_power: str = ""
    model: str = ""
    installation_mode: str = ""
    content_type: str = ""
    content_type_trans: str = ""
    hdr_data: str = ""
    hdr_processing: str = ""
    hdr_level: str = ""
    theater_optimizer: str = ""
    input_mode: str = ""
    input_level: str = ""
    color_mode: str = ""
    eshift: bool = ""
    mask_mode: str = ""
    aspect_ratio: str = ""
    anamorphic_mode: str = ""
    software_version: float = ""
    laser_time: int = 0
    lamp_time: int = 0
    connection_active: bool = False


class JVCProjectorCoordinator:  # pylint: disable=too-many-public-methods
    """JVC Projector Control"""

    def __init__(
        self,
        options: JVCInput,
        # Can supply a logger object. It can hook into the HA logger
        logger: logging.Logger = logging.getLogger(__name__),
    ):
        self.options = options
        self.logger = logger
        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None

        self.model_family = ""
        self.connection_open = False
        # attribute mapping
        self.attributes = JVCAttributes()
        self.lock = asyncio.Lock()

        self.commander = JVCCommander(
            options.host,
            options.port,
            options.password,
            options.connect_timeout,
            logger,
            self.reader,
            self.writer,
            self.lock,
        )

    async def _handshake(self) -> bool:
        """Perform an async 3-way handshake with the projector"""
        if self.options.password:
            pj_req = PJ_REQ + f"_{self.options.password}".encode()
            self.logger.debug("connecting with password hunter2")
        else:
            pj_req = PJ_REQ
        try:
            async with self.lock:
                self.logger.debug("Sending PJ_REQ")
                msg_pjok = await self.reader.read(len(PJ_OK))
            if msg_pjok != PJ_OK:
                result = (
                    f"Projector did not reply with correct PJ_OK greeting: {msg_pjok}"
                )
                self.logger.error(result)
                return False
            self.logger.debug("PJ_OK received")
            async with self.lock:
                self.writer.write(pj_req)
                await self.writer.drain()
                msg_pjack = await self.reader.read(len(PJ_ACK))
            self.logger.debug("PJ_ACK received")
            if msg_pjack != PJ_ACK:
                result = f"Exception with PJACK: {msg_pjack}"
                self.logger.error(result)
                return False
            self.logger.debug("Handshake successful")
        except asyncio.TimeoutError:
            return False

        self.model_family = await self._get_modelfamily()
        self.logger.debug("Model code is %s", self.model_family)
        return True

    async def _get_modelfamily(self) -> str:
        """Get the model family asynchronously"""

        res = await self.exec_command(
            command="get_model", command_type=Header.reference.value
        )
        if not res:
            self.logger.error("Failed to get model family")
            return "Unsupported"
        model_res = self.commander.replace_headers(res).decode()
        self.logger.debug("Model result is %s", model_res)

        return model_map.get(model_res[-4:], "Unsupported")

    async def reset_everything(self) -> None:
        """
        resets everything and tries to empty current jvc buffer. Used on error to just clear everything and start over
        """
        try:
            if not self.connection_open:
                await self.open_connection()

            # clear the buffer
            while not self.reader.at_eof():
                try:
                    await self.reader.read(1024)
                except asyncio.IncompleteReadError:
                    break

            return
        except Exception as e:
            self.logger.error("Error resetting everything: %s", e)
            return

    async def open_connection(self) -> bool:
        """Open a connection to the projector asynchronously"""
        # If the connection is already open, return True
        if self.writer is not None and not self.writer.is_closing():
            self.logger.info("Connection already open.")
            return True
        while True:
            try:
                self.logger.info(
                    "Connecting to JVC Projector: %s:%s",
                    self.options.host,
                    self.options.port,
                )
                try:
                    self.reader, self.writer = await asyncio.wait_for(
                        asyncio.open_connection(self.options.host, self.options.port),
                        timeout=10,
                    )
                except asyncio.TimeoutError:
                    self.logger.warning(
                        "open connection timed out, retrying in 2 seconds"
                    )
                    await asyncio.sleep(2)
                    continue
                # Set the reader and writer for the commander
                self.commander.reader = self.reader
                self.commander.writer = self.writer

                self.logger.info("Connected to JVC Projector")

                self.logger.debug("Handshaking...")
                success = await self._handshake()
                if not success:
                    return False
                self.logger.info("Handshake and connection completed")
                self.connection_open = True
                self.attributes.connection_active = True
                return True
            except asyncio.TimeoutError:
                self.logger.warning("Connection timed out, retrying in 2 seconds")
                await self.close_connection()
                await asyncio.sleep(2)
            except OSError as err:
                self.logger.warning("Connecting failed, retrying in 2 seconds: %s", err)
                await self.close_connection()
                await asyncio.sleep(2)

    async def exec_command(
        self, command: Union[list[str], str], command_type: bytes = b"!"
    ) -> str | None:
        """
        Wrapper for commander.send_command() externally to prevent circular imports

        Callers should catch ConnectionClosedError

        command: a str of the command and value, separated by a comma ("power,on").
            or a list of commands
        This is to make home assistant UI use easier



        command_type: which operation, like ! or ? (default = !)

        Returns
            value: str (to be cast into other types),
        """
        self.logger.debug(
            "exec_command Executing command: %s - %s", command, command_type
        )
        retries = 0
        while retries < 3:
            try:
                res = await self.commander.send_command(command, command_type)
                if not res:
                    self.logger.debug("Command failed. Retrying")
                    retries += 1
                    continue
                return res
            except (
                ConnectionClosedError,
                CommandTimeoutError,
                ConnectionRefusedError,
                BrokenPipeError,
            ):
                self.logger.debug(
                    "Connection closed. Opening new connection. Retry your command"
                )
                # open connection and try again
                await self.open_connection()
                await asyncio.sleep(1)
                continue

        return None

    async def close_connection(self):
        """Close the projector connection asynchronously"""
        try:
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()

            self.logger.info("Connection closed")
        except BrokenPipeError:
            self.logger.warning("Connection already closed - Broken pipe encountered")
        except Exception as e:
            self.logger.error("Error closing JVC Projector connection - %s", e)
        finally:
            self.commander.reader = self.reader
            self.commander.writer = self.writer
            self.connection_open = False
            self.attributes.connection_active = False

    async def power_on(
        self,
    ) -> tuple[str, bool]:
        """
        Turns on PJ
        """
        return await self.exec_command("power,on")

    async def power_off(self) -> tuple[str, bool]:
        """
        Turns off PJ
        """
        return await self.exec_command("power,off")

    async def _get_attribute(self, command: str, replace: bool = True) -> str:
        """
        Generic function to get the current attribute asynchronously
        """
        cmd_tup = Commands[command].value
        cmd_enum = cmd_tup[1]
        ack = cmd_tup[2]
        self.logger.debug("Getting attribute %s with tuple %s", command, cmd_tup)
        try:
            state = await self.exec_command(command, Header.reference.value)
            if not state:
                self.logger.debug("%s Command failed", command)
                return ""
            if replace:
                # remove the returned headers
                r = self.commander.replace_headers(state)
                if not isinstance(r, bytes):
                    self.logger.error("Attribute %s is not bytes", command)
                    return ""
                self.logger.debug("Attribute %s is %s", command, r)
                # look up the enum value like b"1" -> on in PowerModes
                return cmd_enum(r.replace(ack.value, b"")).name
            else:
                return state
        except ValueError as err:
            self.logger.error("Attribute not found - %s", err)
            raise
        except AttributeError as err:
            self.logger.error("tried to access name on non-enum: %s", err)
            return ""

    async def get_low_latency_state(self) -> str:
        """
        Get the current state of LL
        """
        return await self._get_attribute("low_latency") == LowLatencyModes.on.name

    async def get_picture_mode(self) -> str:
        """
        Get the current picture mode as str -> user1, natural
        """
        return await self._get_attribute("picture_mode")

    async def get_install_mode(self) -> str:
        """
        Get the current install mode as str
        """
        return await self._get_attribute("installation_mode")

    async def get_input_mode(self) -> str:
        """
        Get the current input mode
        """
        return await self._get_attribute("input_mode")

    async def get_mask_mode(self) -> str:
        """
        Get the current mask mode
        """
        return await self._get_attribute("mask")

    async def get_laser_mode(self) -> str:
        """
        Get the current laser mode
        """
        return await self._get_attribute("laser_mode")

    async def get_eshift_mode(self) -> bool:
        """
        Get the current eshift mode
        """
        res = await self._get_attribute("eshift_mode")
        return res == "on"

    async def get_color_mode(self) -> str:
        """
        Get the current color mode
        """
        return await self._get_attribute("color_mode")

    async def get_input_level(self) -> str:
        """
        Get the current input level
        """
        return await self._get_attribute("input_level")

    async def get_software_version(self) -> float:
        """
        Get the current software version
        """
        state = await self._get_attribute("get_software_version", replace=False)
        self.logger.debug("Software version is %s", state)
        # returns something like 0210PJ as bytes
        # b'@\x89\x01IF0300PJ\n'
        ver: str = (
            self.commander.replace_headers(state)
            .replace(ACKs.info_ack.value, b"")
            .replace(b"PJ", b"")
            .decode()
            # remove leading 0
            .lstrip("0")
        )
        # add a dot to the version
        return float(f"{ver[:1]}.{ver[1:]}")

    async def get_laser_value(self) -> int:
        """
        Get the current software version FW 3.0+ only
        """
        state = await self._get_attribute("laser_value", replace=False)
        raw = int(
            self.commander.replace_headers(state).replace(ACKs.picture_ack.value, b""),
            16,
        )
        # jvc returns a weird scale
        return math.floor(((raw - 109) / 1.1) + 0.5)

    async def get_content_type(self) -> str:
        """
        Get the current content type
        """
        return await self._get_attribute("content_type")

    async def get_content_type_trans(self) -> str:
        """
        Get the current auto content transition type
        """
        return await self._get_attribute("content_type_trans")

    async def get_hdr_processing(self) -> str:
        """
        Get the current hdr processing setting like frame by frame. Will fail if not in HDR mode!
        """
        return await self._get_attribute("hdr_processing")

    async def get_hdr_level(self) -> str:
        """
        Get the current hdr quantization level
        """
        return await self._get_attribute("hdr_level")

    async def get_hdr_data(self) -> str:
        """
        Get the current hdr mode -> sdr, hdr10_plus, etc
        """
        return await self._get_attribute("hdr_data")

    async def get_lamp_power(self) -> str:
        """
        Get the current lamp power non-NZ only
        """
        return await self._get_attribute("lamp_power")

    async def get_lamp_time(self) -> int:
        """
        Get the current lamp time
        """
        state = await self._get_attribute("lamp_time", replace=False)
        return int(
            self.commander.replace_headers(state).replace(ACKs.info_ack.value, b""), 16
        )

    async def get_laser_power(self) -> str:
        """
        Get the current laser power NZ only
        """
        return await self._get_attribute("laser_power")

    async def get_theater_optimizer_state(self) -> str:
        """
        If theater optimizer is on/off Will fail if not in HDR mode!
        """
        return await self._get_attribute("theater_optimizer")

    async def get_aspect_ratio(self) -> str:
        """
        Return aspect ratio
        """
        return await self._get_attribute("aspect_ratio")

    async def get_anamorphic(self) -> str:
        """
        Return anamorphic mode
        """
        return await self._get_attribute("anamorphic")

    async def get_source_status(self) -> bool:
        """
        Return source status True if it has a signal
        """
        res = await self._get_attribute("source_status")
        return res == "signal"

    async def get_source_display(self) -> str:
        """
        Return source display resolution like 4k_4096p60
        """
        res = await self._get_attribute("source_disaply")

        return res.replace("r_", "")

    async def _get_power_state(self) -> str:
        """
        Return the current power state

        Returns str: values of PowerStates
        """
        # remove the headers
        return await self._get_attribute("power_status")

    async def is_on(self) -> bool:
        """
        True if the current state is on|reserved
        """
        pw_status = [PowerStates.on.name]
        return await self._get_power_state() in pw_status

    async def is_ll_on(self) -> bool:
        """
        True if LL mode is on
        """
        return await self.get_low_latency_state() == LowLatencyModes.on.name

    def print_commands(self) -> str:
        """
        Print out all supported commands
        """
        print_commands = sorted(
            [
                command.name
                for command in Commands
                if command.name not in ["power_status", "current_output", "info"]
            ]
        )
        print("Currently Supported Commands:")
        for command in print_commands:
            print(f"\t{command}")

        print("\n")
        # Print all options
        print("Currently Supported Parameters:")
        import inspect

        from jvc_projector import commands

        for name, obj in inspect.getmembers(commands):
            if inspect.isclass(obj) and obj not in [
                Commands,
                ACKs,
                Footer,
                Enum,
                Header,
            ]:
                print(name)
                for option in obj:
                    print(f"\t{option.name}")
