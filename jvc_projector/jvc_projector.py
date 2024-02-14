"""
Implements the JVC protocol
"""
from dataclasses import dataclass
import logging
from typing import Union
import socket
import time
from jvc_projector.command_runner import JVCCommander
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
    PJ_ACK,
    PJ_OK,
    PJ_REQ,
    model_map
)

@dataclass
class JVCInput:
    """JVC Projector Input"""
    host: str
    password: str
    port: int
    connect_timeout: int


class JVCProjectorCoordinator:
    """JVC Projector Control"""
    
    # Const values
    client = None
    # NZ or NX (NP5 is classified as NX because bulb)
    model_family = ""
    
    def __init__(
        self,
        options: JVCInput,
        # Can supply a logger object. It can hook into the HA logger
        logger: logging.Logger = logging.getLogger(__name__),
    ):
        self.host = options.host
        self.port = options.port
        # NZ models have password authentication
        self.password = options.password
        self.connect_timeout: int = options.connect_timeout
        self.logger = logger
        self.commander = JVCCommander(options, logger, self.client)

    def _handshake(self) -> tuple[str, bool]:
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
        msg_pjok = self.client.recv(len(PJ_OK))
        self.logger.debug(msg_pjok)
        if msg_pjok != PJ_OK:
            result = f"Projector did not reply with correct PJ_OK greeting: {msg_pjok}"
            self.logger.error(result)
            return result, False

        # try sending PJREQ, if there's an error, raise exception
        try:
            self.client.sendall(pj_req)

            # see if we receive PJACK, if not, raise exception
            msg_pjack = self.client.recv(len(PJ_ACK))
            if msg_pjack != PJ_ACK:
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

        res, _ = self.commander.send_command(
            cmd,
            command_type=Header.reference.value,
            ack=ACKs.model.value,
        )

        model_res = self.commander.replace_headers(res).decode()
        self.logger.debug(model_res)

        # get last 4 char of response and look up value
        return model_map.get(model_res[-4:], "Unsupported")

    def _check_closed(self) -> bool:
        """
        Check if the socket is closed

        Returns bool: True if closed
        """
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

    def open_connection(self) -> bool:
        """
        Open a connection, try forever
        """
        while True:
            try:
                self.logger.info(
                    "Connecting to JVC Projector: %s:%s", self.host, self.port
                )
                self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client.settimeout(self.connect_timeout)

                self.client.connect((self.host, self.port))
                self.commander.client = self.client
                self.logger.info("Connected to JVC Projector")

                # create a reader and writer to do handshake
                self.logger.debug("Handshaking")
                result, success = self._handshake()
                if not success:
                    return result, success
                self.logger.info("Handshake and connection completed")
                return True

            # includes conn refused
            except TimeoutError:
                self.logger.warning("Connection timed out, retrying in 2 seconds")
                time.sleep(2)
                continue
            except OSError as err:
                self.logger.warning("Connecting failed, retrying in 2 seconds")
                self.logger.debug(err)
                time.sleep(2)
                continue


    def close_connection(self):
        """
        Only useful for testing
        """
        self.client.close()
        self.commander.client = self.client
        self.logger.info("Connection closed")

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
        self.logger.debug("exec_command Executing command: %s - %s", command, command_type)
        return self.commander.send_command(command, command_type)

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

        return self.commander.send_command(
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
    
    def _get_attribute(self, command: str, ack: Enum, state_enum: Enum) -> str:
        """
        Generic function to the current attribute
        """
        state, _ = self.commander.do_reference_op(command, ack.value)
        return state_enum(state.replace(ack.value, b"")).name
    
    def get_low_latency_state(self) -> str:
        """
        Get the current state of LL
        """
        return self._get_attribute("low_latency", ACKs.picture_ack, LowLatencyModes)

    def get_picture_mode(self) -> str:
        """
        Get the current picture mode as str -> user1, natural
        """
        return self._get_attribute("picture_mode", ACKs.picture_ack, PictureModes)

    def get_install_mode(self) -> str:
        """
        Get the current install mode as str
        """
        return self._get_attribute("installation_mode", ACKs.install_acks, InstallationModes)

    def get_input_mode(self) -> str:
        """
        Get the current input mode
        """
        return self._get_attribute("input_mode", ACKs.input_ack, InputModes)

    def get_mask_mode(self) -> str:
        """
        Get the current mask mode
        """
        return self._get_attribute("mask", ACKs.hdmi_ack, MaskModes)

    def get_laser_mode(self) -> str:
        """
        Get the current laser mode
        """
        return self._get_attribute("laser_mode", ACKs.picture_ack, LaserDimModes)

    def get_eshift_mode(self) -> str:
        """
        Get the current eshift mode
        """
        return self._get_attribute("eshift_mode", ACKs.picture_ack, EshiftModes)

    def get_color_mode(self) -> str:
        """
        Get the current color mode
        """
        return self._get_attribute("color_mode", ACKs.hdmi_ack, ColorSpaceModes)

    def get_input_level(self) -> str:
        """
        Get the current input level
        """
        return self._get_attribute("input_level", ACKs.hdmi_ack, InputLevel)

    def get_software_version(self) -> str:
        """
        Get the current software version
        """
        state, _ = self.commander.do_reference_op("get_software_version", ACKs.info_ack)
        return state.replace(ACKs.info_ack.value, b"")

    def get_content_type(self) -> str:
        """
        Get the current content type
        """
        return self._get_attribute("content_type", ACKs.picture_ack, ContentTypes)

    def get_content_type_trans(self) -> str:
        """
        Get the current auto content transition type
        """
        return self._get_attribute("content_type_trans", ACKs.picture_ack, ContentTypeTrans)

    def get_hdr_processing(self) -> str:
        """
        Get the current hdr processing setting like frame by frame. Will fail if not in HDR mode!
        """
        return self._get_attribute("hdr_processing", ACKs.picture_ack, HdrProcessing)

    def get_hdr_level(self) -> str:
        """
        Get the current hdr quantization level
        """
        return self._get_attribute("hdr_level", ACKs.picture_ack, HdrLevel)

    def get_hdr_data(self) -> str:
        """
        Get the current hdr mode -> sdr, hdr10_plus, etc
        """
        return self._get_attribute("hdr_data", ACKs.info_ack, HdrData)

    def get_lamp_power(self) -> str:
        """
        Get the current lamp power non-NZ only
        """
        return self._get_attribute("lamp_power", ACKs.picture_ack, LampPowerModes)

    def get_lamp_time(self) -> int:
        """
        Get the current lamp time
        """
        state, _ = self.commander.do_reference_op("lamp_time", ACKs.info_ack)
        return int(state.replace(ACKs.info_ack.value, b""), 16)

    def get_laser_power(self) -> str:
        """
        Get the current laser power NZ only
        """
        return self._get_attribute("laser_power", ACKs.picture_ack, LaserPowerModes)

    def get_theater_optimizer_state(self) -> str:
        """
        If theater optimizer is on/off Will fail if not in HDR mode!
        """
        return self._get_attribute("theater_optimizer", ACKs.picture_ack, TheaterOptimizer)

    def get_aspect_ratio(self) -> str:
        """
        Return aspect ratio
        """
        return self._get_attribute("aspect_ratio", ACKs.hdmi_ack, AspectRatioModes)

    def get_source_status(self) -> str:
        """
        Return source status
        """
        return self._get_attribute("source_status", ACKs.source_ack, SourceStatuses)
    
    
    def _get_power_state(self) -> str:
        """
        Return the current power state

        Returns str: values of PowerStates
        """
        # remove the headers
        state, _ = self.commander.do_reference_op("power", ACKs.power_ack)

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
