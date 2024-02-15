"""
Implements the JVC protocol
"""
import asyncio
from typing import Union
import logging
from dataclasses import dataclass

from jvc_projector.command_runner import JVCCommander
from jvc_projector.commands import (PJ_ACK, PJ_OK, PJ_REQ, ACKs,
                                    AspectRatioModes, ColorSpaceModes,
                                    Commands, ContentTypes, ContentTypeTrans,
                                    Enum, EshiftModes, Footer, HdrData,
                                    HdrLevel, HdrProcessing, Header,
                                    InputLevel, InputModes, InstallationModes,
                                    LampPowerModes, LaserDimModes,
                                    LaserPowerModes, LowLatencyModes,
                                    MaskModes, PictureModes, PowerStates,
                                    SourceStatuses, TheaterOptimizer,
                                    model_map)


@dataclass
class JVCInput:
    """JVC Projector Input"""
    host: str
    password: str
    port: int
    connect_timeout: int

@dataclass
class JVCAttributes: # pylint: disable=too-many-instance-attributes
    """JVC Projector Attributes"""
    power_state: bool = False
    signal_status: str = ""
    picture_mode: str = "" 
    installation_mode: str = ""
    laser_power: str = ""
    laser_mode: str = ""
    lamp_power: str = ""
    model: str = ""
    content_type: str = ""
    content_type_trans: str = ""
    hdr_data: str = ""
    hdr_processing: str = ""
    hdr_level: str = ""
    theater_optimizer: str = ""
    low_latency: bool = False
    input_mode: str = ""
    input_level: str = ""
    color_mode: str = ""
    aspect_ratio: str = ""
    eshift: str = ""
    mask_mode: str = ""
    software_version: str = ""
    lamp_time: int = 0


class JVCProjectorCoordinator: # pylint: disable=too-many-public-methods
    """JVC Projector Control"""

    def __init__(
        self,
        options: JVCInput,
        # Can supply a logger object. It can hook into the HA logger
        logger: logging.Logger = logging.getLogger(__name__),
    ):
        self.options = options
        self.logger = logger
        self.commander = JVCCommander(options, logger, self.reader, self.writer)
        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None
        self.model_family = ""
        # attribute mapping
        self.attributes = JVCAttributes()

    async def _handshake(self) -> bool:
        """Perform an async 3-way handshake with the projector"""
        if self.options.password:
            pj_req = PJ_REQ + f"_{self.options.password}".encode()
            self.logger.debug("connecting with password hunter2")
        else:
            pj_req = PJ_REQ

        try:
            msg_pjok = await self.reader.recv(len(PJ_OK))
            self.logger.debug(msg_pjok)
            if msg_pjok != PJ_OK:
                result = f"Projector did not reply with correct PJ_OK greeting: {msg_pjok}"
                self.logger.error(result)
                return False

            self.writer.write(pj_req)
            await self.writer.drain()
            msg_pjack = await self.reader.recv(len(PJ_ACK))
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
        cmd = (
            Header.reference.value
            + Header.pj_unit.value
            + Commands.get_model.value
            + Footer.close.value
        )

        res, _ = await self.commander.send_command(
            cmd,
            command_type=Header.reference.value,
            ack=ACKs.model.value,
        )

        model_res = self.commander.replace_headers(res).decode()
        self.logger.debug(model_res)
        return model_map.get(model_res[-4:], "Unsupported")

    async def open_connection(self) -> bool:
        """Open a connection to the projector asynchronously"""
        while True:
            try:
                self.logger.info("Connecting to JVC Projector: %s:%s", self.options.host, self.options.port)
                self.reader, self.writer = await asyncio.open_connection(self.options.host, self.options.port)
                # Set the reader and writer for the commander
                self.commander.reader = self.reader
                self.commander.writer = self.writer

                self.logger.info("Connected to JVC Projector")

                self.logger.debug("Handshaking...")
                success = await self._handshake()
                if not success:
                    return False
                self.logger.info("Handshake and connection completed")
                return True
            except asyncio.TimeoutError:
                self.logger.warning("Connection timed out, retrying in 2 seconds")
                await asyncio.sleep(2)
            except OSError as err:
                self.logger.warning("Connecting failed, retrying in 2 seconds")
                self.logger.debug(err)
                await asyncio.sleep(2)

    def exec_command(
         self, command: Union[list[str], str], command_type: bytes = b"!"
     ) -> tuple[str, bool]:
         """
         Wrapper for commander.send_command() externally
         command: a str of the command and value, separated by a comma ("power,on").
             or a list of commands
         This is to make home assistant UI use easier
         command_type: which operation, like ! or ? (default = !)
         Returns
             (
                 ack or error message: str,
                 success flag: bool
             )
         """
         self.logger.debug("exec_command Executing command: %s - %s", command, command_type)
         return self.commander.send_command(command, command_type)
    
    async def close_connection(self):
        """Close the projector connection asynchronously"""
        self.writer.close()
        await self.writer.wait_closed()
        self.commander.reader = self.reader
        self.commander.writer = self.writer
        self.logger.info("Connection closed")

    async def info(self) -> tuple[str, bool]:
        """
        Bring up the Info screen
        """
        cmd = (
            Header.operation.value
            + Header.pj_unit.value
            + Commands.info.value
            + Footer.close.value
        )

        return await self.commander.send_command(
            cmd,
            ack=ACKs.menu_ack,
            command_type=Header.operation.value,
        )

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

    async def _get_attribute(self, command: str, ack: Enum, state_enum: Enum) -> str:
        """
        Generic function to get the current attribute asynchronously
        """
        state, _ = await self.commander.do_reference_op(command, ack.value)
        return state_enum(state.replace(ack.value, b"")).name

    async def get_low_latency_state(self) -> str:
        """
        Get the current state of LL
        """
        return await self._get_attribute("low_latency", ACKs.picture_ack, LowLatencyModes)

    async def get_picture_mode(self) -> str:
        """
        Get the current picture mode as str -> user1, natural
        """
        return await self._get_attribute("picture_mode", ACKs.picture_ack, PictureModes)

    async def get_install_mode(self) -> str:
        """
        Get the current install mode as str
        """
        return await self._get_attribute("installation_mode", ACKs.install_acks, InstallationModes)

    async def get_input_mode(self) -> str:
        """
        Get the current input mode
        """
        return await self._get_attribute("input_mode", ACKs.input_ack, InputModes)

    async def get_mask_mode(self) -> str:
        """
        Get the current mask mode
        """
        return await self._get_attribute("mask", ACKs.hdmi_ack, MaskModes)

    async def get_laser_mode(self) -> str:
        """
        Get the current laser mode
        """
        return await self._get_attribute("laser_mode", ACKs.picture_ack, LaserDimModes)

    async def get_eshift_mode(self) -> str:
        """
        Get the current eshift mode
        """
        return await self._get_attribute("eshift_mode", ACKs.picture_ack, EshiftModes)

    async def get_color_mode(self) -> str:
        """
        Get the current color mode
        """
        return await self._get_attribute("color_mode", ACKs.hdmi_ack, ColorSpaceModes)

    async def get_input_level(self) -> str:
        """
        Get the current input level
        """
        return await self._get_attribute("input_level", ACKs.hdmi_ack, InputLevel)

    async def get_software_version(self) -> str:
        """
        Get the current software version
        """
        state, _ = self.commander.do_reference_op("get_software_version", ACKs.info_ack)
        return state.replace(ACKs.info_ack.value, b"")

    async def get_content_type(self) -> str:
        """
        Get the current content type
        """
        return await self._get_attribute("content_type", ACKs.picture_ack, ContentTypes)

    async def get_content_type_trans(self) -> str:
        """
        Get the current auto content transition type
        """
        return await self._get_attribute("content_type_trans", ACKs.picture_ack, ContentTypeTrans)

    async def get_hdr_processing(self) -> str:
        """
        Get the current hdr processing setting like frame by frame. Will fail if not in HDR mode!
        """
        return await self._get_attribute("hdr_processing", ACKs.picture_ack, HdrProcessing)

    async def get_hdr_level(self) -> str:
        """
        Get the current hdr quantization level
        """
        return await self._get_attribute("hdr_level", ACKs.picture_ack, HdrLevel)

    async def get_hdr_data(self) -> str:
        """
        Get the current hdr mode -> sdr, hdr10_plus, etc
        """
        return await self._get_attribute("hdr_data", ACKs.info_ack, HdrData)

    async def get_lamp_power(self) -> str:
        """
        Get the current lamp power non-NZ only
        """
        return await self._get_attribute("lamp_power", ACKs.picture_ack, LampPowerModes)

    async def get_lamp_time(self) -> int:
        """
        Get the current lamp time
        """
        state, _ = self.commander.do_reference_op("lamp_time", ACKs.info_ack)
        return int(state.replace(ACKs.info_ack.value, b""), 16)

    async def get_laser_power(self) -> str:
        """
        Get the current laser power NZ only
        """
        return await self._get_attribute("laser_power", ACKs.picture_ack, LaserPowerModes)

    async def get_theater_optimizer_state(self) -> str:
        """
        If theater optimizer is on/off Will fail if not in HDR mode!
        """
        return await self._get_attribute("theater_optimizer", ACKs.picture_ack, TheaterOptimizer)

    async def get_aspect_ratio(self) -> str:
        """
        Return aspect ratio
        """
        return await self._get_attribute("aspect_ratio", ACKs.hdmi_ack, AspectRatioModes)

    async def get_source_status(self) -> str:
        """
        Return source status
        """
        return await self._get_attribute("source_status", ACKs.source_ack, SourceStatuses)

    async def _get_power_state(self) -> str:
        """
        Return the current power state

        Returns str: values of PowerStates
        """
        # remove the headers
        return await self._get_attribute("power_status", ACKs.power_ack, PowerStates)

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
