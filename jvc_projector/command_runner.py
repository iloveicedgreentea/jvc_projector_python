import asyncio
import logging
import socket
from typing import Union

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
    ) -> None:
        self.host = host
        self.port = port
        # NZ models have password authentication
        self.password = password
        self.connect_timeout: int = timeout
        self.logger = logger

        self.reader = reader
        self.writer = writer
        self.lock = asyncio.Lock()
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
    # TODO: something else must decode the commands from HA like [menu, menu]
    # TODO: support remote
    # _, value = send_command[0].split(",")
    #                     return await self.emulate_remote(value)
    # TODO: run this in a loop and send commands from a queue
    async def send_command(self, command: str, command_type: bytes) -> str:
        """
        Sends a command with a flag to expect an ack.

        The PJ API returns nothing if a command is in flight
        or if a command is not successful

        command: the Command to send like laser_value
        command_type: bytes - ! or ?

        Returns:
            (
                value: str (to be cast into other types)
            )
        """
        cmd, ack = self.construct_command(command, command_type)
        # cmd_tup = Commands[command].value
        # cmd = cmd_tup[0]  # laser_value
        # cmd_enum = cmd_tup[1]  # LaserDimModes
        # ack = cmd_tup[2].value  # ACKs.whatever

        # Check commands
        self.logger.debug("command: %s", cmd)
        # make header based on command type - ensure we only get expected value
        # header = (
        #     Header.reference.value
        #     if command_type == Header.reference.value
        #     else Header.operation.value
        # )
        # final_cmd: bytes = (
        #     header
        #     + Header.pj_unit.value
        #     + Commands[command].value[0]
        #     + Footer.close.value
        # )
        try:
            return await self._do_command(cmd, ack, command_type)
            # try:
            #     cons_command, ack = self._construct_command(send_command, command_type)
            # except TypeError:
            #     cons_command = send_command

            # if not ack:
            #     return cons_command, ack
            # return await self._do_command(cons_command, ack.value, command_type)
        # raise connectionclosed error to be handled by callers
        except (
            # TODO: handle ConnectionClosedError outside this function, in a loop
            CommandTimeoutError,
            BlankMessageError,
            ConnectionRefusedError,
        ) as err:
            return str(err), False

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
            ack=ACKs.menu_ack,
            command_type=Header.operation.value,
        )

    # TODO: must catch broken pipe
    # what does this always return
    async def _do_command(
        self,
        final_cmd: bytes,
        ack: bytes,
        command_type: bytes,
    ) -> tuple[Union[str, bytes]]:
        self.logger.debug("final_cmd: %s with ack %s", final_cmd, ack)
        # ensure this doesnt run with dead client
        if self.writer is None:
            self.logger.warning("Writer is closed")
            raise ConnectionClosedError("writer is none")

        self.logger.debug("do_command sending command: %s", final_cmd)
        # send the command
        try:
            self.writer.write(final_cmd)
            await self.writer.drain()
        except BrokenPipeError as err:
            self.logger.error("BrokenPipeError in _do_command: %s", err)
            # Attempt to reconnect or handle the broken pipe scenario
            # reconnect_to_projector() # This is a placeholder for your reconnection logic
            raise ConnectionClosedError("Broken pipe") from err
        except ConnectionResetError as err:
            self.logger.error("ConnectionResetError in _do_command: %s", err)
            # Handle connection reset specifically, if different from broken pipe
            # reconnect_to_projector() # Similarly, placeholder for reconnection logic
            raise ConnectionClosedError("Connection reset") from err
        except ConnectionError as err:
            # reaching this means the writer was closed somewhere
            self.logger.debug("ConnectionError in _do_command: %s", err)
            raise ConnectionClosedError(err) from err
        # if we send a command that returns info, the projector will send
        # an ack, followed by the actual message. Check to see if the ack sent by
        # projector is correct, then return the message.

        # TODO: why not read it all and then remove the ack value after
        ack_value = Header.ack.value + Header.pj_unit.value + ack + Footer.close.value
        self.logger.debug("constructed ack_value: %s", ack_value)

        # Receive the acknowledgement from PJ
        try:
            # read everything
            msg = await self.reader.read(len(ack_value))
            self.logger.debug("received msg in _do_command: %s", msg)

            # read the actual message, if any
            if msg == b"":  # if we got a blank response
                self.logger.error("Got a blank response")
                raise BlankMessageError("Got a blank response")
            if command_type == Header.operation.value:
                return msg, True
            else:
                ref_msg = await self.reader.read(1000)
                self.logger.debug("received ref_msg in _do_command: %s", ref_msg)
                # msg = await self._check_received_msg(received_ack, ack_value, command_type)
                return ref_msg.replace(ack_value, b"")
        except socket.timeout as err:
            error = f"Timed out. Command {final_cmd} may grayed out or cmd is running already."
            self.logger.debug(err)
            raise CommandTimeoutError(error) from err

        except ConnectionRefusedError as err:
            self.logger.debug(err)
            raise ConnectionRefusedError(error) from err

    # async def _check_received_msg(
    #     self, received_ack: bytes, ack_value: bytes, command_type: bytes
    # ) -> bytes:
    #     self.logger.debug(
    #         "received msg is: %s and ack value is %s and type %s",
    #         received_ack,
    #         ack_value,
    #         command_type,
    #     )
    #     # get the ack for operation
    #     if command_type == Header.operation.value:
    #         # operations dont have return values beyond this
    #         # read the rest of the msg to clear the buffer e.g PW/n
    #         message = await self.reader.read(1000)
    #         self.logger.debug("received operation message from PJ: %s", message)
    #         return message

    #     # if we got what we expect and this is a reference,
    #     # receive the data we requested
    #     if command_type == Header.reference.value:
    #         message = await self.reader.read(1000)
    #         self.logger.debug("received message from PJ: %s", message)

    #         return message

    #     self.logger.error(
    #         "Received ack: %s != expected ack: %s",
    #         received_ack,
    #         ack_value,
    #     )

    #     # return blank will force it to retry
    #     return b""

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
            command, value = raw_command.split(",")
        except ValueError:
            # support single commands like get_model
            command: bytes = (
                command_type + Header.pj_unit.value + Commands[raw_command].value[0] + Footer.close.value
            )
            return command, Commands[raw_command].value[2].value

        # Check if command is implemented
        if not hasattr(Commands, command):
            self.logger.error("Command not implemented: %s", command)
            return "Not Implemented", False

        # construct the command with nested Enums
        command_name, val, ack = Commands[command].value
        command_base: bytes = command_name + val[value.lstrip(" ")].value
        # Construct command based on required values
        command: bytes = (
            command_type + Header.pj_unit.value + command_base + Footer.close.value
        )

        return command, ack.value

    async def do_reference_op(self, command: str, ack: ACKs) -> tuple[str, bool]:
        """Make a reference call"""
        # Ensure the command value is retrieved correctly as bytes
        msg = await self.send_command(
            command,
            command_type=Header.reference.value,
        )
        self.logger.debug("do_reference_op msg: %s", msg)


        msg = self.replace_headers(msg)

        return msg
