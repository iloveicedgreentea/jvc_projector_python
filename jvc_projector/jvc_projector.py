import socket
from time import sleep
import datetime
import logging

# import the enums
from jvc_projector.commands import *

log = logging.getLogger(__name__)


class JVCProjector:
    """JVC Projector Control"""

    def __init__(
        self,
        host: str,
        port: int = 20554,
        delay_ms: int = 1000,
        connect_timeout: int = 60,
        password: str = None,
    ):
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.delay = datetime.timedelta(microseconds=(delay_ms * 1000))
        self.last_command_time = datetime.datetime.now() - datetime.timedelta(
            seconds=10
        )
        # NZ models have password authentication
        self.password = password

    def _throttle(self):
        if self.delay == 0:
            return

        delta = datetime.datetime.now() - self.last_command_time

        if self.delay > delta:
            sleep((self.delay - delta).total_seconds())

        return

    def _send_command(
        self,
        send_command: bytes,
        ack_expected: bytes = None,
        command_type: bytes = b"!",
    ) -> tuple:
        """
        Sends a command with a flag to expect an ack.
        send_command: the base command to use, like power
        ack_expected: value of the ack we expect, like PW
        command_type: which operation, like ! or ?

        Returns
            ack or error message: str
            success flag: bool
        """

        # Establish values
        PJ_OK = ACKs.greeting.value
        PJ_ACK = ACKs.pj_ack.value
        req = ACKs.pj_req.value
        # if using NZ, convert password to bytes and append to call
        if self.password:
            PJ_REQ = req + f"_{self.password}".encode()
        else:
            PJ_REQ = req

        result = None
        success = True
        running = True
        # Construct command based on required values
        command = (
            command_type + Header.pj_unit.value + send_command + Footer.close.value
        )
        log.debug(f"command: {command}")

        # Init the connection
        jvc_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        jvc_sock.settimeout(self.connect_timeout)
        try:
            jvc_sock.connect((self.host, self.port))
        except ConnectionRefusedError as e:
            return e, False
        except socket.timeout:
            return "Connection timed out", False

        # Cheap and simple context manager
        while running:
            # throttle command if too quick otherwise
            # JVC kills the connection
            self._throttle()

            # 3 step handshake:
            # Projector sends PJ_OK, client sends PJREQ within 5 seconds, projector replies with PJACK
            # first, after connecting, see if we receive PJ_OK. If not, raise exception
            msg_pjok = jvc_sock.recv(len(PJ_OK))
            if msg_pjok != PJ_OK:
                result = (
                    f"Projector did not reply with correct PJ_OK greeting: {msg_pjok}"
                )
                success = False
                running = False

            # try sending PJREQ, if there's an error, raise exception
            try:
                jvc_sock.sendall(PJ_REQ)
            except socket.error as e:
                result = "Socket exception when sending PJREQ"
                success = False
                running = False

            # see if we receive PJACK, if not, raise exception
            msg_pjack = jvc_sock.recv(len(PJ_ACK))
            if msg_pjack != PJ_ACK:
                result = f"Socket exception on PJACK: {msg_pjack}"
                success = False
                running = False

            # 3 step connection is verified, send the command
            jvc_sock.sendall(command)

            # if we send a command that returns info, the projector will send
            # an ack, followed by the message. Check to see if the ack sent by
            # projector is correct, then return the message.
            if ack_expected:
                ack_value = (
                    Header.ack.value
                    + Header.pj_unit.value
                    + ack_expected
                    + Footer.close.value
                )
                log.debug(f"ack_value: {ack_value}")
                ack = jvc_sock.recv(len(ack_value))

                if ack == ack_value:
                    message = jvc_sock.recv(1024)
                    log.debug(f"result: {ack}, {message}")
                    result = message
                else:
                    success = False
                    result = (
                        f"Unexpected ack received from PJ after sending command{ack}"
                    )
                    running = False

            # finish execution
            running = False

        jvc_sock.close()

        self.last_command_time = datetime.datetime.now()

        return result, success

    def info(self) -> tuple:
        """
        Brings up the Info screen
        """
        return self._send_command(send_command=Commands.info.value, ack_expected=None)

    def power_on(self) -> tuple:
        """
        Turns on PJ
        """
        return self.command("power", "on", ack=ACKs.power_ack.value)

    def power_off(self) -> tuple:
        """
        Turns off PJ
        """
        return self.command("power", "off", ack=ACKs.power_ack.value)

    def gaming_mode(self) -> tuple:
        """
        Sets (opinionated) optimal gaming settings
        """
        # TODO:
        # LL on
        # hi-res 1
        # HDR mode
        # enhance 7
        # NR, etc 0
        # Motion enhance off

        pass

    def hdr_picture_mode(self) -> tuple:
        """
        Sets (opinionated) optimal HDR film settings
        """
        # TODO:
        # LL off
        # hi-res 1
        # frame adapt hdr
        # enhance 6
        # NR, etc 0
        # Motion enhance low
        # others

        pass

    def sdr_picture_mode(self) -> tuple:
        """
        Sets (opinionated) optimal sdr film settings
        """
        # TODO:
        # LL off
        # hi-res 1
        # sdr
        # enhance 6
        # NR, etc 0
        # Motion enhance low
        # others

        pass

    def low_latency_on(self) -> tuple:
        """
        NZ and up require certain params to be disabled first
        This function sets all those to be true and then enables low latency
        """
        # TODO:
        # picture mode to HDR
        # turn off laser dimming
        # turn off CMD
        # turn on low latency

    def command(
        self, command: str, value: str, ack: bytes = None, command_type: bytes = b"!"
    ) -> tuple:
        """
        Wrapper for _send_command()
        command: the base command to use, like power
        value: the value to send, like on/off/film per command
        ack_expected: value of the ack we expect, like PW
        command_type: which operation, like ! or ?

        Returns
            self._send_command()
        """
        if not hasattr(Commands, command):
            log.error(f"Command not implemented: {command}")
            return False
        else:
            # construct the command with nested Enum
            name, val = Commands[command].value
            command = name + val[value].value
            return self._send_command(command, ack, command_type)
    
    def _replace_headers(self, item: bytes) -> bytes:
        """
        Will strip all headers and returns the value itself
        """
        headers = [x.value for x in Header] + [x.value for x in Footer]
        for header in headers:
            item = item.replace(header, b'')

        return item
    def _power_state(self) -> str:
        """
        Return the current power state
        """
        msg: bytes = self._send_command(
            Commands.power_status.value,
            ack_expected=ACKs.power_ack.value,
            command_type=Header.reference.value,
        )[0]
        # remove the headers 
        state = self._replace_headers(msg)

        return PowerStates(state.replace(ACKs.power_ack.value, b'')).name

    def is_on(self) -> bool:
        """
        True/False is the current state is on or reserved
        """
        on = [PowerStates.on.name, PowerStates.reserved.name]
        return self._power_state() in on

    def print_commands(self) -> str:
        print_commands = sorted([command.name for command in Commands if command.name not in ["power_status", "current_output", "info"]])
        print("Currently Supported Commands:")
        for command in print_commands:
            print(f"\t{command}")

        print("\n")
        # Print all options
        print("Currently Supported Parameters:")
        from jvc_projector import commands
        import inspect

        for name, obj in inspect.getmembers(commands):
            if inspect.isclass(obj) and obj not in [Commands, ACKs, Footer, Enum, Header] :
                print(name)
                for option in obj:
                    print(f"\t{option.name}")

