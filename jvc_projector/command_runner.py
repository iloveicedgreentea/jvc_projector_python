from jvc_projector.jvc_projector import JVCInput
import logging
from typing import Union
import socket
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
from jvc_projector.error_classes import (
    ConnectionClosedError,
    CommandTimeoutError,
    CommandRetryExceededError,
    BlankMessageError
)


class JVCCommander:
    """
    JVC Projector Commander

    Handles sending commands to the projector
    """

    def __init__(self, options: JVCInput, logger: logging.Logger = logging.getLogger(__name__), client: socket.socket = None) -> None:
        self.host = options.host
        self.port = options.port
        # NZ models have password authentication
        self.password = options.password
        self.connect_timeout: int = options.connect_timeout
        self.logger = logger

        self.client = client

    def replace_headers(self, item: bytes) -> bytes:
        """
        Will strip all headers and returns the value itself
        """
        headers = [x.value for x in Header] + [x.value for x in Footer]
        for header in headers:
            item = item.replace(header, b"")

        return item
    def send_command(
        self,
        send_command: Union[list[str], str],
        command_type: bytes = b"!",
        ack: bytes = None,
    ) -> tuple[str, bool]:
        """
        Sends a command with a flag to expect an ack.

        The PJ API returns nothing if a command is in flight
        or if a command is not successful

        send_command: Can be a command or a list of commands
        ack: value of the ack we expect, like PW
        command_type: which operation, like ! or ?

        Returns:
            (
                ack or error message: str,
                success flag: bool
            )
        """
        # Check commands
        self.logger.debug("Command_type: %s", command_type)
        self.logger.debug(
            "Send command: %s is of type %s", send_command, type(send_command)
        )
        self.logger.debug("Send ack: %s", ack)
        if command_type == Header.reference.value:
            return self._do_command(send_command, ack, command_type)

        if isinstance(send_command, list):
            # check emulate remote first
            if "remote" in send_command[0]:
                try:
                    _, value = send_command[0].split(",")
                    return self.emulate_remote(value)
                except ValueError:
                    return f"No value for command provided {send_command}", False

            for cmd in send_command:
                cons_command, ack = self._construct_command(cmd, command_type)
                if not ack:
                    return cons_command, ack
                # need a delay otherwise it kills connection
                time.sleep(0.1)
                return self._do_command(cons_command, ack.value, command_type)

        else:
            try:
                cons_command, ack = self._construct_command(send_command, command_type)
            except TypeError:
                cons_command = send_command

            if not ack:
                return cons_command, ack
            return self._do_command(cons_command, ack.value, command_type)
    def emulate_remote(self, remote_code: str) -> tuple[str, bool]:
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

        return self.send_command(
            cmd,
            ack=ACKs.menu_ack,
            command_type=Header.operation.value,
        )

    def _do_command(
        self,
        command: bytes,
        ack: bytes,
        command_type: bytes = b"!",
    ) -> tuple[Union[str, bytes], bool]:

        # ensure this doesnt run with dead client
        if self.client is None:
            self.logger.warning("Client is none. Reforming connection")
            # TODO: have coordinator reconnect if raise
            raise ConnectionClosedError("Client is none")

        # max retries
        retry_count = 0
        # use this to store error if retry count exceeded
        error = ""

        # retry once in case connection is dead
        # TODO: move retry to coordinator
        while retry_count < 2:
            self.logger.debug("do_command sending command: %s", command)
            # send the command
            try:
                self.client.sendall(command)
            except ConnectionError as err:
                # reaching this means the writer was closed somewhere
                self.logger.error(err)
                # restart the connection
                self.client.close()
                # TODO: have coordinator reconnect
                raise ConnectionClosedError(err) from err

            # if we send a command that returns info, the projector will send
            # an ack, followed by the actual message. Check to see if the ack sent by
            # projector is correct, then return the message.
            ack_value = (
                Header.ack.value + Header.pj_unit.value + ack + Footer.close.value
            )
            self.logger.debug("constructed ack_value: %s", ack_value)

            # Receive the acknowledgement from PJ
            try:
                # most commands timeout when PJ is off
                received_msg = self.client.recv(len(ack_value))
            except socket.timeout as err:
                error = f"Timed out. Command {command} may grayed out or cmd is running already."
                self.logger.debug(err)
                self.client.close()
                # TODO: have coordinator reconnect
                raise CommandTimeoutError(error) from err

            except ConnectionRefusedError as err:
                self.logger.debug(err)
                self.client.close()
                # TODO: have coordinator reconnect
                raise ConnectionRefusedError(error) from err

            self.logger.debug("received msg from PJ: %s", received_msg)

            msg = self._check_received_msg(received_msg, ack_value, command_type)
            if msg == b"":
                self.logger.error("Got a blank msg. Restarting connection")
                self.client.close()
                # TODO: have coordinator reconnect
                raise BlankMessageError("Got a blank msg")

            # if all fine, return the value
            return msg, True

        self.logger.error("retry count for running commands exceeded")

        raise CommandRetryExceededError("retry count for running commands exceeded")

    def _check_received_msg(
        self, received_msg: bytes, ack_value: bytes, command_type: bytes
    ) -> bytes:
        # This is unlikely to happen unless we read blank response
        if received_msg == b"":
            return received_msg

        # get the ack for operation
        if received_msg == ack_value and command_type == Header.operation.value:
            return received_msg

        # if we got what we expect and this is a reference,
        # receive the data we requested
        if received_msg == ack_value and command_type == Header.reference.value:
            message = self.client.recv(1000)
            self.logger.debug("received message from PJ: %s", message)

            return message

        self.logger.error(
            "Received ack: %s != expected ack: %s",
            received_msg,
            ack_value,
        )

        # return blank will force it to retry
        return b""

    def _construct_command(
        self, raw_command: str, command_type: bytes
    ) -> tuple[bytes, ACKs]:
        """
        Transform commands into their byte values from the string value
        """
        # split command into the base and the action like menu: left
        try:
            command, value = raw_command.split(",")
        except ValueError:
            return "No value for command provided", False

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
        self.logger.debug("command: %s", command)

        return command, ack

    def do_reference_op(self, command: str, ack: ACKs) -> tuple[str, bool]:
        cmd = (
            Header.reference.value
            + Header.pj_unit.value
            + Commands[command].value[0]
            + Footer.close.value
        )

        msg, success = self.send_command(
            cmd,
            ack=ACKs[ack.name].value,
            command_type=Header.reference.value,
        )

        if success:
            msg = self.replace_headers(msg)

        return msg, success     
