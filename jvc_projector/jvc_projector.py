"""
Implements the JVC protocol
"""

import logging
import math
from typing import Union
import threading
import socket
from jvc_projector.commands import (
    ACKs,
    Footer,
    Header,
    Commands,
    PowerStates,
    Enum,
    LowLatencyModes,
    PJ_ACK,
    PJ_REQ,
    PJ_OK,
    model_map,
)
import jvc_projector.errors


class JVCProjector:
    """JVC Projector Control"""

    def __init__(
        self,
        host: str,
        password: str = "",
        # Can supply a logger object. It can hook into the HA logger
        logger: logging.Logger = logging.getLogger(__name__),
        port: int = 20554,
        connect_timeout: int = 3,
    ):
        self.host = host
        self.port = port
        # NZ models have password authentication
        self.password = password
        self.connect_timeout: int = connect_timeout
        self.logger = logger
        self.client = None
        # NZ or NX (NP5 is classified as NX)
        self.model_family = ""
        self.lock = threading.Lock()

        socket.setdefaulttimeout(3)

    def open_connection(self) -> bool:
        """Open a connection"""
        self.logger.debug("Starting open connection")
        success = self.reconnect()

        self.logger.debug("Connection status: %s", success)
        return success

    def reconnect(self) -> bool:
        """Initiate keep-alive connection. This should handle any error and reconnect eventually."""
        try:
            self.logger.info("Connecting to JVC Projector: %s:%s", self.host, self.port)
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.settimeout(self.connect_timeout)
            try:
                self.client.connect((self.host, self.port))
            except TypeError as err:
                self.logger.error("TypeError when connecting")
                raise TypeError(
                    f"Invalid port or host - {self.port}:{self.host}"
                ) from err
            except (ConnectionRefusedError, TimeoutError, OSError) as err:
                self.logger.error("Connection failed")
                raise ConnectionError from err

            self.logger.info("Connected to JVC Projector")

            # create a reader and writer to do handshake
            self.logger.debug("Handshaking")
            success = self._handshake()
            return success

        # includes conn refused
        except TimeoutError:
            self.logger.warning("Connection timed out")
        except OSError as err:
            self.logger.warning("Connecting failed")
            self.logger.debug(err)

        return False

    def _handshake(self) -> bool:
        """
        Do the 3 way handshake

        Projector sends PJ_OK, client sends PJREQ (with optional password) within 5 seconds, projector replies with PJACK
        first, after connecting, see if we receive PJ_OK. If not, raise exception
        """
        if self.password:
            pj_req = PJ_REQ + f"_{self.password}".encode()
            self.logger.debug("connecting with password hunter2")
        else:
            pj_req = PJ_REQ

        # 3 step handshake
        with self.lock:
            msg_pjok = self.client.recv(1000)
            if msg_pjok != PJ_OK:
                result = (
                    f"Projector did not reply with correct PJ_OK greeting: {msg_pjok}"
                )
                self.logger.error(result)
                return False

            # try sending PJREQ, if there's an error, raise exception
            self.client.sendall(pj_req)

            # see if we receive PJACK, if not, raise exception
            msg_pjack = self.client.recv(1000)
            if msg_pjack != PJ_ACK:
                result = f"Exception with PJACK: {msg_pjack}"
                self.logger.error(result)
                return False
            self.logger.debug("Handshake successful")

        # Get model family
        self.model_family = self._get_modelfamily()
        self.logger.debug("Model code is %s", self.model_family)
        return True

    def _get_modelfamily(self) -> str:
        self.logger.debug("Getting model family")
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
        model_res = self._replace_headers(res).decode()
        self.logger.debug(model_res)

        # get last 4 char of response and look up value
        return model_map.get(model_res[-4:], "Unsupported")

    def is_closed(self) -> bool:
        """Return False if the socket is open, True if it is closed."""
        try:
            self.logger.debug("Checking if socket is closed")
            # send null command
            self.client.sendall(b"\x00\x00")
        except BlockingIOError:
            self.logger.debug(
                "BlockingIOError: Socket would block, indicating it's still open."
            )
            return False  # Socket is open and reading from it would block
        except ConnectionResetError:
            self.logger.debug(
                "ConnectionResetError: Connection was reset, socket is closed."
            )
            return True  # Connection was reset, socket is closed
        except OSError as e:
            self.logger.warning("OSError: Socket not connected: %s", e)
            return True  # Treat any other OSError as a closed connection

        self.logger.debug(
            "Socket is open, no exceptions were raised, and data is present."
        )
        return False  # If no exceptions and data is present, the socket is open

    def close_connection(self):
        """
        close the connection
        """
        self.client.close()

    def _send_command(
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
        # try to reconnect if connection is closed
        # if self.is_closed():
        #     self.logger.warning("reconnecting")
        #     self.reconnect()

        # Check commands
        self.logger.debug("Command_type: %s", command_type)
        self.logger.debug(
            "Send command: %s is of type %s", send_command, type(send_command)
        )

        with self.lock:
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
                        self.logger.warning(
                            "Command not implemented: %s - %s", cmd, cons_command
                        )
                        return cons_command, ack
                    return self._do_command(cons_command, ack.value, command_type)

            else:
                return ("unsupported commands", False)

    def _do_command(
        self,
        command: bytes,
        ack: bytes,
        command_type: bytes = b"!",
    ) -> tuple[Union[str, bytes], bool]:

        # ensure this doesnt run with dead client
        if self.is_closed():
            self.logger.warning("reconnecting")
            self.reconnect()

        # retry once in case connection is dead
        self.logger.debug("do_command sending command: %s", command)
        # send the command
        try:
            self.client.sendall(command)

            # if we send a command that returns info, the projector will send
            # an ack, followed by the actual message. Check to see if the ack sent by
            # projector is correct, then return the message.
            ack_value = (
                Header.ack.value + Header.pj_unit.value + ack + Footer.close.value
            )
            self.logger.debug("constructed ack_value: %s", ack_value)

            # Receive the acknowledgement from PJ

            # most commands timeout when PJ is off
            received_msg = self.client.recv(len(ack_value))
            self.logger.debug("received msg from PJ: %s", received_msg)

            msg = self._check_received_msg(received_msg, ack_value, command_type)
            if msg == b"":
                self.logger.error("Got a blank msg")

            # if all fine, return the value
            return msg, True

        except TimeoutError as err:
            self.logger.error("TimeoutError when getting msg %s", err)

        except ConnectionRefusedError as err:
            self.logger.error("ConnectionRefusedError when getting msg %s", err)

        except OSError as err:
            self.logger.error("OSError when getting msg %s", err)

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

    def _decimal_to_signed_hex(self, number: int) -> bytes:
        # Convert input string to integer

        # Convert the decimal value to signed 2-byte hexadecimal
        hex_value = format(number & 0xFFFF, "04X")

        byte_values = bytes(hex_value, "ascii")

        return byte_values

    def _scale_laser_value(self, value: str) -> bytes:
        try:
            percent = int(value)
        except ValueError as exc:
            raise ValueError("Value must be an int") from exc

        if percent > 100:
            return ValueError("Value must be between 0 and 100")

        scaled = 109 + math.floor(1.1 * percent + 0.5)
        return self._decimal_to_signed_hex(
            scaled
        )  # Convert to hex string with 4 characters

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
            raise NotImplementedError(f"Command {command} not implemented")

        # construct the command with nested Enums
        command_name, val, ack = Commands[command].value

        if command == "laser_value":
            value = self._scale_laser_value(value)

        self.logger.debug("val is %s", val)
        self.logger.debug("type of val is %s", type(val))
        self.logger.debug("value is %s", value)

        # some commands use int values so we can just pass the value as byte
        if issubclass(val, int):
            try:
                command_base: bytes = command_name + value
            except ValueError as err:
                self.logger.error("Value %s is not an int", value)
                raise jvc_projector.errors.ValueIsNotIntError from err
        else:
            try:
                command_base: bytes = command_name + val[value.lstrip(" ")].value
            except KeyError as err:
                self.logger.error("Value %s is not in Enum", value)
                raise NotImplementedError(f"Value {value} not in Enum") from err
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

        return self._do_command(
            cmd,
            ack=ACKs.menu_ack.value,
            command_type=Header.operation.value,
        )

    def power_on(
        self,
    ) -> tuple[str, bool]:
        """
        Turns on PJ
        """
        return self.exec_command(["power,on"])

    def power_off(self) -> tuple[str, bool]:
        """
        Turns off PJ
        """
        return self.exec_command(["power,off"])

    def _replace_headers(self, item: bytes) -> bytes:
        """
        Will strip all headers and returns the value itself
        """
        headers = [x.value for x in Header] + [x.value for x in Footer]
        for header in headers:
            item = item.replace(header, b"")

        return item

    def _do_reference_op(self, command: str, ack: ACKs) -> str:
        cmd = (
            Header.reference.value
            + Header.pj_unit.value
            + Commands[command].value[0]
            + Footer.close.value
        )

        msg, _ = self._send_command(
            cmd,
            ack=ACKs[ack.name].value,
            command_type=Header.reference.value,
        )

        return msg

    def _get_attribute(self, command: str, replace: bool = True) -> str:
        """
        Generic function to get the current attribute asynchronously
        """
        cmd_tup = Commands[command].value
        self.logger.debug("Getting attribute %s with tuple %s", command, cmd_tup)
        cmd_enum = cmd_tup[1]
        ack = cmd_tup[2]
        self.logger.debug("Getting attribute %s with tuple %s", command, cmd_tup)
        try:
            try:
                state = self._do_reference_op(command, ack)
            except TypeError:
                return ""
            if not state:
                self.logger.debug("%s Command failed", command)
                return ""
            if replace:
                # remove the returned headers
                r = self._replace_headers(state)
                if not isinstance(r, bytes):
                    self.logger.error("Attribute %s is not bytes", command)
                    return ""
                self.logger.debug("Attribute %s is %s", command, r)
                # look up the enum value like b"1" -> on in PowerModes
                return cmd_enum(r.replace(ack.value, b"")).name

            return state
        except ValueError as err:
            self.logger.error("Attribute not found - %s", err)
            raise
        except AttributeError as err:
            self.logger.error("tried to access name on non-enum: %s", err)
            return ""

    def get_low_latency_state(self) -> str:
        """
        Get the current state of LL
        """
        return self._get_attribute("low_latency")

    def get_picture_mode(self) -> str:
        """
        Get the current picture mode as str -> user1, natural
        """
        return self._get_attribute("picture_mode")

    def get_install_mode(self) -> str:
        """
        Get the current install mode as str
        """
        return self._get_attribute("installation_mode")

    def get_input_mode(self) -> str:
        """
        Get the current input mode
        """
        return self._get_attribute("input_mode")

    def get_mask_mode(self) -> str:
        """
        Get the current mask mode
        """
        return self._get_attribute("mask")

    def get_laser_mode(self) -> str:
        """
        Get the current laser mode
        """
        return self._get_attribute("laser_mode")

    def get_eshift_mode(self) -> bool:
        """
        Get the current eshift mode
        """
        res = self._get_attribute("eshift_mode")
        return res == "on"

    def get_color_mode(self) -> str:
        """
        Get the current color mode
        """
        return self._get_attribute("color_mode")

    def get_input_level(self) -> str:
        """
        Get the current input level
        """
        return self._get_attribute("input_level")

    def get_software_version(self) -> float:
        """
        Get the current software version
        """
        state = self._get_attribute("get_software_version", replace=False)
        self.logger.debug("Software version is %s", state)
        # returns something like 0210PJ as bytes
        # b'@\x89\x01IF0300PJ\n'
        ver: str = (
            self._replace_headers(state)
            .replace(ACKs.info_ack.value, b"")
            .replace(b"PJ", b"")
            .decode()
            # remove leading 0
            .lstrip("0")
        )
        # add a dot to the version
        return float(f"{ver[:1]}.{ver[1:]}")

    def _translate_laser_value(self, state: str) -> int:
        raw = int(
            self._replace_headers(state).replace(ACKs.picture_ack.value, b""),
            16,
        )
        # jvc returns a weird scale
        return math.floor(((raw - 109) / 1.1) + 0.5)

    def get_laser_value(self) -> int:
        """
        Get the current software version FW 3.0+ only
        """
        state = self._get_attribute("laser_value", replace=False)

        return self._translate_laser_value(state)

    def get_content_type(self) -> str:
        """
        Get the current content type
        """
        return self._get_attribute("content_type")

    def get_content_type_trans(self) -> str:
        """
        Get the current auto content transition type
        """
        return self._get_attribute("content_type_trans")

    def get_hdr_processing(self) -> str:
        """
        Get the current hdr processing setting like frame by frame. Will fail if not in HDR mode!
        """
        return self._get_attribute("hdr_processing")

    def get_hdr_level(self) -> str:
        """
        Get the current hdr quantization level
        """
        return self._get_attribute("hdr_level")

    def get_hdr_data(self) -> str:
        """
        Get the current hdr mode -> sdr, hdr10_plus, etc
        """
        return self._get_attribute("hdr_data")

    def get_lamp_power(self) -> str:
        """
        Get the current lamp power non-NZ only
        """
        return self._get_attribute("lamp_power")

    def get_lamp_time(self) -> int:
        """
        Get the current lamp time
        """
        state = self._get_attribute("lamp_time", replace=False)
        return int(self._replace_headers(state).replace(ACKs.info_ack.value, b""), 16)

    def get_laser_power(self) -> str:
        """
        Get the current laser power NZ only
        """
        return self._get_attribute("laser_power")

    def get_theater_optimizer_state(self) -> str:
        """
        If theater optimizer is on/off Will fail if not in HDR mode!
        """
        return self._get_attribute("theater_optimizer")

    def get_aspect_ratio(self) -> str:
        """
        Return aspect ratio
        """
        return self._get_attribute("aspect_ratio")

    def get_anamorphic(self) -> str:
        """
        Return anamorphic mode
        """
        return self._get_attribute("anamorphic")

    def get_source_status(self) -> bool:
        """
        Return source status True if it has a signal
        """
        res = self._get_attribute("source_status")
        return res == "signal"

    def get_source_display(self) -> str:
        """
        Return source display resolution like 4k_4096p60
        """
        res = self._get_attribute("source_display")

        return res.replace("r_", "")

    def _get_power_state(self) -> str:
        """
        Return the current power state

        Returns str: values of PowerStates
        """
        # remove the headers
        return self._get_attribute("power")

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
                if command.name not in ["power", "current_output", "info"]
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
