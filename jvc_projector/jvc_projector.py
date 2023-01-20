"""
Implements the JVC protocol
"""

import logging
from typing import Final, Union
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
    TheaterOptimizer,
    HdrData,
    LampPowerModes
)


class JVCProjector:
    """JVC Projector Control"""

    def __init__(
        self,
        host: str,
        password: str = "",
        # Can supply a logger object. It can hook into the HA logger
        logger: logging.Logger = logging.getLogger(__name__),
        port: int = 20554,
        connect_timeout: int = 5,
    ):
        self.host = host
        self.port = port
        # NZ models have password authentication
        self.password = password
        self.connect_timeout: int = connect_timeout
        self.logger = logger
        # Const values
        self.PJ_OK: Final = ACKs.greeting.value
        self.PJ_ACK: Final = ACKs.pj_ack.value
        self.PJ_REQ: Final = ACKs.pj_req.value
        self.client = None
        self.command_read_timeout = 3
        # NZ or NX (NP5 is classified as NX)
        self.model_family = ""

    def open_connection(self) -> bool:
        """Open a connection"""
        self.logger.debug("Starting open connection")
        msg, success = self.reconnect()

        if not success:
            self.logger.error(msg)

        return success

    def reconnect(self):
        """Initiate keep-alive connection. This should handle any error and reconnect eventually."""
        while True:
            try:
                self.logger.info(
                    "Connecting to JVC Projector: %s:%s", self.host, self.port
                )
                self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client.settimeout(self.connect_timeout)

                self.client.connect((self.host, self.port))
                self.logger.info("Connected to JVC Projector")

                # create a reader and writer to do handshake
                self.logger.debug("Handshaking")
                result, success = self._handshake()
                if not success:
                    return result, success
                self.logger.debug("Handshake complete and we are connected")
                return "Connection done", True

            # includes conn refused
            except TimeoutError:
                self.logger.warning("Connection timed out, retrying in 2 seconds")
                time.sleep(2)
            except OSError as err:
                self.logger.warning("Connecting failed, retrying in 2 seconds")
                self.logger.debug(err)
                time.sleep(2)

    def _handshake(self) -> tuple[str, bool]:
        """
        Do the 3 way handshake

        Projector sends PJ_OK, client sends PJREQ (with optional password) within 5 seconds, projector replies with PJACK
        first, after connecting, see if we receive PJ_OK. If not, raise exception
        """
        if self.password:
            pj_req = self.PJ_REQ + f"_{self.password}".encode()
            self.logger.debug("connecting with password hunter2")
        else:
            pj_req = self.PJ_REQ

        # 3 step handshake
        msg_pjok = self.client.recv(len(self.PJ_OK))
        self.logger.debug(msg_pjok)
        if msg_pjok != self.PJ_OK:
            result = f"Projector did not reply with correct PJ_OK greeting: {msg_pjok}"
            self.logger.error(result)
            return result, False

        # try sending PJREQ, if there's an error, raise exception
        try:
            self.client.sendall(pj_req)

            # see if we receive PJACK, if not, raise exception
            msg_pjack = self.client.recv(len(self.PJ_ACK))
            if msg_pjack != self.PJ_ACK:
                result = f"Exception with PJACK: {msg_pjack}"
                self.logger.error(result)
                return result, False
            self.logger.debug("Handshake successful")
        except socket.timeout:
            return "handshake timeout", False
        # Get model family
        self.model_family = self._get_modelfamily()
        self.logger.debug("Model code is %s", self.model_family)
        return "ok", True

    def _get_modelfamily(self) -> str:
        cmd = (
            Header.reference.value
            + Header.pj_unit.value
            + Commands.get_model.value
            + Footer.close.value
        )

        res, _ = self._send_command(
            cmd,
            command_type=Header.reference.value,
            ack=ACKs.model.value,
        )
        models = {
            "B5A1": "NZ9",
            "B5A2": "NZ8",
            "B5A3": "NZ7",
            "A2B1": "NX9",
            "A2B2": "NX7",
            "A2B3": "NX5",
            "B5B1": "NP5"
        }
        model_res = self._replace_headers(res).decode()
        self.logger.debug(model_res)

        # get last 4 char of response and look up value
        return models.get(model_res[-4:])

    def _check_closed(self) -> bool:
        try:
            # this will try to read bytes without blocking and also without removing them from buffer (peek only)
            data = self.client.recv(16, socket.MSG_DONTWAIT | socket.MSG_PEEK)
            if len(data) == 0:
                return True
        except BlockingIOError:
            return False  # socket is open and reading from it would block
        except ConnectionResetError:
            return True  # socket was closed for some other reason
        except OSError:
            self.logger.warning("Socket not connected")
            return False

        return False

    def close_connection(self):
        """
        Only useful for testing
        """
        self.client.close()

    def _send_command(
        self,
        send_command: Union[list[bytes], bytes],
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
        self.logger.debug("Send command: %s", send_command)
        self.logger.debug("Send ack: %s", ack)
        if command_type == Header.reference.value:
            result, success = self._do_command(send_command, ack, command_type)

            return result, success

        if isinstance(send_command, list):
            for cmd in send_command:
                cons_command, ack = self._construct_command(cmd, command_type)
                if not ack:
                    return cons_command, ack
                # need a delay otherwise it kills connection
                time.sleep(0.1)
                result, success = self._do_command(
                    cons_command, ack.value, command_type
                )
                if not success:
                    return result, success
        else:
            try:
                cons_command, ack = self._construct_command(send_command, command_type)
            except TypeError:
                cons_command = send_command

            if not ack:
                return cons_command, ack
            result, success = self._do_command(cons_command, ack.value, command_type)
            if not success:
                return result, success

        self.logger.debug("send command result: %s", result)
        return "ok", True

    def _do_command(
        self,
        command: bytes,
        ack: bytes,
        command_type: bytes = b"!",
    ) -> tuple[Union[str, bytes], bool]:
        retry_count = 0
        if self.client is None:
            self.logger.debug("Forming connection")
            self.reconnect()

        while retry_count < 5:
            self.logger.debug("do_command sending command: %s", command)
            # send the command
            try:
                self.client.sendall(command)
            except ConnectionError as err:
                # reaching this means the writer was closed somewhere
                self.logger.error(err)
                # self.logger.debug("Restarting connection")
                # restart the connection
                self.client.close()
                self.reconnect()
                self.logger.debug("Sending command again")
                # restart the loop
                retry_count += 1
                continue

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
            except socket.timeout:
                self.logger.error(
                    # TODO: this may be happening because something else read the response?
                    "Connection timed out. Command %s may not be allowed to run at this time or something else is running already.",
                    command,
                )
                self.logger.debug("restarting connection")
                self.client.close()
                self.reconnect()
                retry_count += 1
                return

            except ConnectionRefusedError:
                self.logger.error("Connection Refused when getting msg")
                self.logger.debug("restarting connection")
                self.client.close()
                self.reconnect()
                retry_count += 1
                continue

            self.logger.debug("received msg from PJ: %s", received_msg)

            # This is unlikely to happen unless we read blank response
            if received_msg == b"":
                self.logger.error("Got a blank msg. Restarting connection")
                self.client.close()
                self.reconnect()
                retry_count += 1
                continue

            # get the ack for operation
            if received_msg == ack_value and command_type == Header.operation.value:
                return received_msg, True

            # if we got what we expect and this is a reference,
            # receive the data we requested
            if received_msg == ack_value and command_type == Header.reference.value:
                message = self.client.recv(1000)
                self.logger.debug("received message from PJ: %s", message)

                return message, True

            # Because this now reuses a connection, reaching this stage means catastrophic failure, or HA running as usual :)
            self.logger.error(
                "Received ack did not match expected ack: %s != %s",
                received_msg,
                ack_value,
            )
            # Try to restart connection, if we got here somethihng is out of sync
            self.client.close()
            self.reconnect()
            retry_count += 1
            continue

        self.logger.error("retry count for running commands exceeded")
        return "retry count exceeded", None

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

    def exec_command(
        self, command: Union[list[str], str], command_type: bytes = b"!"
    ) -> tuple[str, bool]:
        """
        Wrapper for _send_command()

        command: a str of the command and value, separated by a comma ("power,on").
            or a list of commands
        This is to make home assistant UI use easier
        command_type: which operation, like ! or ?

        Returns
            (
                ack or error message: str,
                success flag: bool
            )
        """
        self.logger.debug("exec_command Executing command: %s", command)
        return self._send_command(command, command_type)

    def info(self) -> tuple[str, bool]:
        """
        Bring up the Info screen
        """
        cmd = (
            Header.operation.value
            + Header.pj_unit.value
            + Commands.info.value
            + Footer.close.value
        )

        return self._send_command(
            cmd,
            ack=ACKs.menu_ack,
            command_type=Header.operation.value,
        )

    def power_on(
        self,
    ) -> tuple[str, bool]:
        """
        Turns on PJ
        """
        return self.exec_command("power,on")

    def power_off(self) -> tuple[str, bool]:
        """
        Turns off PJ
        """
        return self.exec_command("power,off")

    def _replace_headers(self, item: bytes) -> bytes:
        """
        Will strip all headers and returns the value itself
        """
        headers = [x.value for x in Header] + [x.value for x in Footer]
        for header in headers:
            item = item.replace(header, b"")

        return item

    def _do_reference_op(self, command: str, ack: ACKs) -> tuple[str, bool]:
        cmd = (
            Header.reference.value
            + Header.pj_unit.value
            + Commands[command].value[0]
            + Footer.close.value
        )

        msg, success = self._send_command(
            cmd,
            ack=ACKs[ack.name].value,
            command_type=Header.reference.value,
        )

        if success:
            msg = self._replace_headers(msg)

        return msg, success

    def get_low_latency_state(self) -> str:
        """
        Get the current state of LL
        """
        state, _ = self._do_reference_op("low_latency", ACKs.picture_ack)

        return LowLatencyModes(state.replace(ACKs.picture_ack.value, b"")).name

    def get_picture_mode(self) -> str:
        """
        Get the current picture mode as str -> user1, natural
        """
        state, _ = self._do_reference_op("picture_mode", ACKs.picture_ack)
        return PictureModes(state.replace(ACKs.picture_ack.value, b"")).name

    def get_install_mode(self) -> str:
        """
        Get the current install mode as str
        """
        state, _ = self._do_reference_op("installation_mode", ACKs.install_acks)
        return InstallationModes(state.replace(ACKs.install_acks.value, b"")).name

    def get_input_mode(self) -> str:
        """
        Get the current input mode
        """
        state, _ = self._do_reference_op("input_mode", ACKs.input_ack)
        return InputModes(state.replace(ACKs.input_ack.value, b"")).name

    def get_laser_mode(self) -> str:
        """
        Get the current laser mode
        """
        state, _ = self._do_reference_op("laser_mode", ACKs.picture_ack)
        return LaserDimModes(state.replace(ACKs.picture_ack.value, b"")).name

    def get_eshift_mode(self) -> str:
        """
        Get the current eshift mode
        """
        state, _ = self._do_reference_op("eshift_mode", ACKs.picture_ack)
        return EshiftModes(state.replace(ACKs.picture_ack.value, b"")).name

    def get_color_mode(self) -> str:
        """
        Get the current color mode
        """
        state, _ = self._do_reference_op("color_mode", ACKs.hdmi_ack)
        return ColorSpaceModes(state.replace(ACKs.hdmi_ack.value, b"")).name

    def get_input_level(self) -> str:
        """
        Get the current input level
        """
        state, _ = self._do_reference_op("input_level", ACKs.hdmi_ack)
        return InputLevel(state.replace(ACKs.hdmi_ack.value, b"")).name

    def get_content_type(self) -> str:
        """
        Get the current content type
        """
        state, _ = self._do_reference_op("content_type", ACKs.picture_ack)
        return ContentTypes(state.replace(ACKs.picture_ack.value, b"")).name

    def get_hdr_processing(self) -> str:
        """
        Get the current hdr processing setting like frame by frame. Will fail if not in HDR mode!
        """
        state, _ = self._do_reference_op("hdr_processing", ACKs.picture_ack)
        return HdrProcessing(state.replace(ACKs.picture_ack.value, b"")).name

    def get_hdr_data(self) -> str:
        """
        Get the current hdr mode -> sdr, hdr10_plus, etc
        """
        state, _ = self._do_reference_op("hdr_data", ACKs.hdr_ack)
        return HdrData(state.replace(ACKs.hdr_ack.value, b"")).name

    def get_lamp_power(self) -> str:
        """
        Get the current lamp power non-NZ only
        """
        state, _ = self._do_reference_op("lamp_power", ACKs.picture_ack)
        return LampPowerModes(state.replace(ACKs.picture_ack.value, b"")).name

    def get_theater_optimizer_state(self) -> str:
        """
        If theater optimizer is on/off Will fail if not in HDR mode!
        """
        state, _ = self._do_reference_op("theater_optimizer", ACKs.picture_ack)
        return TheaterOptimizer(state.replace(ACKs.picture_ack.value, b"")).name

    def _get_power_state(self) -> str:
        """
        Return the current power state

        Returns str: values of PowerStates
        """
        success = False

        cmd = (
            Header.reference.value
            + Header.pj_unit.value
            + Commands.power_status.value
            + Footer.close.value
        )
        # try in case we get conn refused
        # Try to prevent power state flapping
        msg, success = self._send_command(
            cmd,
            ack=ACKs.power_ack.value,
            command_type=Header.reference.value,
        )

        # Handle error with unexpected acks
        if not success:
            self.logger.error("Error getting power state: %s", msg)
            return success

        # remove the headers
        state = self._replace_headers(msg)

        return PowerStates(state.replace(ACKs.power_ack.value, b"")).name

    def is_on(self) -> bool:
        """
        True if the current state is on|reserved
        """
        pw_status = [PowerStates.on.name]
        return self._get_power_state() in pw_status

    def is_ll_on(self) -> bool:
        """
        True if LL mode is on
        """
        return self.get_low_latency_state() == LowLatencyModes.on.name

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
        from jvc_projector import commands
        import inspect

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
