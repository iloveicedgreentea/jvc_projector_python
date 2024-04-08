import asyncio
import logging
import socket
from typing import Union
import math

from jvc_projector.commands import ACKs, Commands, Footer, Header
from jvc_projector.error_classes import (
    BlankMessageError,
    CommandTimeoutError,
    ConnectionClosedError,
)


class JVCCommander:
    """
    JVC Projector Commander

    Handles sending commands to the projector
    """

    def __init__(
        self,
        host="",
        port=0,
        password="",
        timeout="",
        logger: logging.Logger = logging.getLogger(__name__),
        reader: asyncio.StreamReader = None,
        writer: asyncio.StreamWriter = None,
        lock: asyncio.Lock = None,
    ) -> None:
        self.host = host
        self.port = port
        # NZ models have password authentication
        self.password = password
        self.connect_timeout: int = timeout
        self.logger = logger

        self.reader = reader
        self.writer = writer
        self.lock = lock
        self.command_queue = asyncio.Queue()

    def replace_headers(self, item: bytes) -> bytes:
        """
        Will strip all headers and returns the value itself
        """
        headers = [x.value for x in Header] + [x.value for x in Footer]
        for header in headers:
            item = item.replace(header, b"")

        return item

    async def add_cmd_to_queue(
        self,
        send_command: Union[list[str], str],
        command_type: bytes = b"!",
        ack: bytes = None,
    ):
        pass

    # TODO: must catch broken pipe
    # TODO: support remote
    async def send_command(self, command: str, command_type: bytes) -> str:
        """
        Sends a command with a flag to expect an ack.

        The PJ API returns nothing if a command is in flight
        or if a command is not successful

        command: the Command to send like laser_value
        command_type: bytes - ! or ?

        Returns:
            value: str (to be cast into other types)
        """
        cmd, ack = self.construct_command(command, command_type)

        # Check commands
        self.logger.debug("command: %s", cmd)

        try:
            return await self._do_command(cmd, ack, command_type)

        # raise connectionclosed error to be handled by callers
        except BlankMessageError as err:
            self.logger.debug("error in send_command: %s", err)
            return ""

    async def emulate_remote(self, remote_code: str) -> tuple[str, bool]:
        """
        Send a cmd via remote emulation

        remote_code: str- ASCII of the remote code like 23 or D4 https://support.jvc.com/consumer/support/documents/DILAremoteControlGuide.pdf
        """
        cmd = (
            Header.operation.value
            + Header.pj_unit.value
            + Commands.remote.value
            + remote_code.encode()
            + Footer.close.value
        )

        return await self.send_command(
            cmd,
            command_type=Header.operation.value,
        )

    async def _do_command(
        self,
        final_cmd: bytes,
        ack: bytes,
        command_type: bytes,
    ) -> tuple[Union[str, bytes]]:
        async with self.lock:
            self.logger.debug("final_cmd: %s with ack %s", final_cmd, ack)
            # ensure this doesnt run with dead client
            if self.writer is None:
                self.logger.debug("Writer is closed")
                raise ConnectionClosedError("writer is none")

            self.logger.debug("do_command sending command: %s", final_cmd)
            # send the command
            try:
                self.logger.debug("acquiring command lock")
                self.writer.write(final_cmd)
                await self.writer.drain()
                self.logger.debug("released command lock")
            except BrokenPipeError as err:
                self.logger.error(
                    "BrokenPipeError in _do_command restarting connection: %s", err
                )
                # Attempt to reconnect or handle the broken pipe scenario
                raise ConnectionClosedError("Broken pipe") from err
            except ConnectionResetError as err:
                self.logger.debug("ConnectionResetError in _do_command: %s", err)
                # Handle connection reset specifically, if different from broken pipe
                raise ConnectionClosedError("Connection reset") from err
            except ConnectionError as err:
                # reaching this means the writer was closed somewhere
                self.logger.debug("ConnectionError in _do_command: %s", err)
                raise ConnectionClosedError(err) from err
            # if we send a command that returns info, the projector will send
            # an ack, followed by the actual message. Check to see if the ack sent by
            # projector is correct, then return the message.

            ack_value = Header.ack.value + Header.pj_unit.value + ack + Footer.close.value
            self.logger.debug("constructed ack_value: %s", ack_value)

            # Receive the acknowledgement from PJ
            try:
                # read everything
                self.logger.debug("acquiring command read lock")
                # TODO: its probably way more reliable to read everything and just search for the data we want
                msg = await self.reader.read(len(ack_value))
                self.logger.debug("received msg in _do_command: %s", msg)

                # read the actual message, if any
                if msg == b"":  # if we got a blank response
                    self.logger.debug("Got a blank response")
                    raise BlankMessageError("Got a blank response")
                if command_type == Header.operation.value:
                    return msg, True
                else:
                    ref_msg = await self.reader.read(1000)
                    self.logger.debug("received ref_msg in _do_command: %s", ref_msg)
                    # msg = await self._check_received_msg(received_ack, ack_value, command_type)
                    self.logger.debug("finished reading ref_msg")
                    return ref_msg.replace(ack_value, b"")
            except socket.timeout as err:
                error = f"Timed out. Command {final_cmd} may grayed out or cmd is running already."
                self.logger.debug(err)
                raise CommandTimeoutError(error) from err

            except ConnectionRefusedError as err:
                self.logger.debug(err)
                raise ConnectionRefusedError(error) from err

    # TODO: use this to construct commands from a list that is a str like ["menu,menu"]
    def construct_command(
        self, raw_command: str, command_type: bytes
    ) -> tuple[bytes, ACKs]:
        """
        Transform commands into their byte values from the string value
        """
        # split command into the base and the action like menu: left
        self.logger.debug("raw_command: %s", raw_command)
        try:
            if isinstance(raw_command, list):
                raw_command = raw_command[0]
            command, value = raw_command.split(",")
        except ValueError:
            # support single commands like get_model
            command: bytes = (
                command_type
                + Header.pj_unit.value
                + Commands[raw_command].value[0]
                + Footer.close.value
            )
            return command, Commands[raw_command].value[2].value

        # Check if command is implemented
        if not hasattr(Commands, command):
            self.logger.error("Command not implemented: %s", command)
            return "Not Implemented", False

        # construct the command with nested Enums
        command_name, val, ack = Commands[command].value
        try:
            command_base: bytes = command_name + val[value.lstrip(" ")].value
        # assume its int
        except TypeError:
            # if the Enum is int instead of an Enum
            if val is int:
                # remove spaces and cast as int
                value = int(value.strip())
                # laser value in has stupid math
                if command == "laser_value":
                    value = (
                        math.floor(1.1 * value + 0.5) + 109
                    )  # 109 is the offset for some reason 109 = 0
                # Convert decimal value to a 4-character hexadecimal string
                hex_value = format(value, "04x")

                # Convert each hexadecimal character to its ASCII representation
                ascii_representation = "".join(
                    f"{ord(char):02x}" for char in hex_value
                ).upper()

                # Convert the ASCII representation to bytes
                command_base: bytes = command_name + bytes.fromhex(ascii_representation)
        # Construct command based on required values
        self.logger.debug("command_base: %s", command_base)
        command: bytes = (
            command_type + Header.pj_unit.value + command_base + Footer.close.value
        )

        return command, ack.value
