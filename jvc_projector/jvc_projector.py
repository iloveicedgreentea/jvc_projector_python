"""
Implements the JVC protocol
"""

import datetime
import logging
from typing import Union
import asyncio

# import the enums
from jvc_projector.commands import ACKs, Footer, Header, Commands, PowerStates, Enum


class JVCProjector:
    """JVC Projector Control"""

    # Const values
    PJ_OK = ACKs.greeting.value
    PJ_ACK = ACKs.pj_ack.value
    req = ACKs.pj_req.value

    def __init__(
        self,
        host: str,
        port: int = 20554,
        delay_ms: int = 1000,
        connect_timeout: int = 10,
        password: str = None,
        logger: logging.Logger = logging.getLogger(__name__),
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
        self.logger = logger
        self._lock = asyncio.Lock()

        if self.password:
            self.pj_req = self.req + f"_{self.password}".encode()
        else:
            self.pj_req = self.req

    async def _async_throttle(self):
        if self.delay == 0:
            return

        delta = datetime.datetime.now() - self.last_command_time

        if self.delay > delta:
            return await asyncio.sleep((self.delay - delta).total_seconds())

    async def _async_send_command(
        self,
        send_command: Union[list[bytes], bytes],
        ack: bytes,
        command_type: bytes = b"!",
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

        result = ""
        success = True

        # throttle command if too quick otherwise
        # JVC kills the connection
        await self._async_throttle()

        async with self._lock:
            # Try connecting
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port)
            except ConnectionRefusedError:
                return "Connection Refused", False
            except asyncio.TimeoutError:
                return "Connection timed out", False

        # 3 step handshake
        result, success = await self._async_handshake(reader, writer)
        if not success:
            return result, success

        # Check commands
        if isinstance(send_command, list):
            for cmd in send_command:
                result, success = await self._async_do_command(
                    reader, writer, cmd, ack, command_type
                )
                if not success:
                    return result, success
        else:
            result, success = await self._async_do_command(
                reader, writer, send_command, ack, command_type
            )
            if not success:
                return result, success

        self.last_command_time = datetime.datetime.now()
        self.logger.debug("send command result: %s", result)

        return result, success

    async def _async_handshake(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> tuple[str, bool]:
        """
        Do the 3 way handshake

        Projector sends PJ_OK, client sends PJREQ within 5 seconds, projector replies with PJACK
        first, after connecting, see if we receive PJ_OK. If not, raise exception
        """

        async with self._lock:
            msg_pjok = await reader.read(len(self.PJ_OK))
            if msg_pjok != self.PJ_OK:
                result = (
                    f"Projector did not reply with correct PJ_OK greeting: {msg_pjok}"
                )
                success = False

                return result, success

            # try sending PJREQ, if there's an error, raise exception
            try:
                writer.write(self.pj_req)
                await writer.drain()
            except asyncio.TimeoutError as err:
                result = f"Timeout sending PJREQ {err}"
                success = False
                writer.close()

                return result, success

            # see if we receive PJACK, if not, raise exception
            msg_pjack = await reader.read(len(self.PJ_ACK))
            if msg_pjack != self.PJ_ACK:
                result = f"Exception with PJACK: {msg_pjack}"
                success = False

                return result, success

            return "ok", True

    async def _async_do_command(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        command: bytes,
        ack: bytes,
        command_type: bytes = b"!",
    ) -> tuple[str, bool]:
        async with self._lock:
            self.logger.debug("_do_command sending command: %s", command)
            # send the command
            writer.write(command)
            await writer.drain()

            # if we send a command that returns info, the projector will send
            # an ack, followed by the message. Check to see if the ack sent by
            # projector is correct, then return the message.
            ack_value = (
                Header.ack.value + Header.pj_unit.value + ack + Footer.close.value
            )
            self.logger.debug("ack_value: %s", ack_value)

            # Receive the acknowledgement from PJ
            try:
                received_ack = await reader.read(len(ack_value))
            except asyncio.TimeoutError:
                result = "Connection timed out. Command is probably not allowed to run at this time."
                self.logger.error(result)
                writer.close()
                return result, False
            except ConnectionRefusedError:
                self.logger.error("Connection Refused when getting ack")
                return "Connection Refused", False

            self.logger.debug("received_ack: %s", received_ack)

            # if we got what we expect and this is a reference,
            # receive the data we requested
            if received_ack == ack_value and command_type == Header.operation.value:
                result = received_ack
                writer.close()

                return result, True
                
            if received_ack == ack_value and command_type == Header.reference.value:
                message = await reader.read(1024)
                self.logger.debug("result: %s, %s", received_ack, message)
                writer.close()
                result = message

                return result, True
            
            # Otherwise, it failed
            writer.close()
            result = "Unexpected ack received from PJ after sending a command. Perhaps a command got cancelled because a new connection was made."
            self.logger.error(result)
            self.logger.error("received_ack: %s", received_ack)
            self.logger.error("ack_value: %s", ack_value)

            return result, False

    async def _async_construct_command(
        self, raw_command: str, command_type: bytes
    ) -> tuple[bytes, ACKs]:
        """
        Transform commands into their byte values
        """
        command, value = raw_command.split(",")

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
        Sync version of async_exec_command
        """

        return asyncio.run(self.async_exec_command(command, command_type))

    async def async_exec_command(
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

        if isinstance(command, str):
            cons_command, ack = await self._async_construct_command(
                command, command_type
            )
            result, success = await self._async_send_command(
                cons_command, ack.value, command_type
            )

            return result, success
        elif isinstance(command, list):
            for cmd in command:
                # TODO: this may need a sleep to prevent the thing from dying
                # TODO: also maybe implement a retry mechanism
                cons_command, ack = await self._async_construct_command(
                    cmd, command_type
                )
                result, success = await self._async_send_command(
                    cons_command, ack.value, command_type
                )

                if not success:
                    return result, success
            return "ok", True
        else:
            return "Command is not valid type", False

    async def async_info(self) -> tuple[str, bool]:
        """
        Brings up the Info screen
        """
        cmd = (
            Header.operation.value
            + Header.pj_unit.value
            + Commands.info.value
            + Footer.close.value
        )

        return await self._async_send_command(
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
        return asyncio.run(self.async_power_on())

    async def async_power_on(
        self,
    ) -> tuple[str, bool]:
        """
        Turns on PJ
        """
        return await self.async_exec_command("power,on")

    def power_off(
        self,
    ) -> tuple[str, bool]:
        """
        Turns off PJ
        """
        return asyncio.run(self.async_power_off())

    async def async_power_off(self) -> tuple[str, bool]:
        """
        Turns off PJ
        """
        return await self.async_exec_command("power,off")

    async def async_gaming_mode_hdr(self) -> bool:
        """
        Sets (opinionated!) optimal HDR gaming settings
        """
        state = await self.async_get_low_latency_state()
        # If LL is on, we can turn it off first
        # TODO: make this more DRY
        if state:
            cmds = [
                "picture_mode, hdr10",
                "enhance, seven",
                "motion_enhance, off",
                "graphic_mode, hires1",
            ]

            # ll_commands = self._build_mode_commands(cmds)
            # return ll_commands
            return await self.async_exec_command(cmds)
        else:
            # If LL is off, we can enable these settings
            cmds = [
                "picture_mode, hdr10",
                "laser_dim, off",
                "low_latency, on",
                "enhance, seven",
                "motion_enhance, off",
                "graphic_mode, hires1",
            ]
        return await self.async_exec_command(cmds)

    async def async_gaming_mode_sdr(self) -> bool:
        """
        Sets (opinionated!) optimal gaming settings
        """
        state = await self.async_get_low_latency_state()
        # If LL is on, we can turn it off first
        # TODO: make this more DRY
        if state:
            cmds = [
                "enhance, seven",
                "motion_enhance, off",
                "graphic_mode, hires1",
            ]

            # ll_commands = self._build_mode_commands(cmds)
            # return ll_commands
            return await self.async_exec_command(cmds)
        else:
            # If LL is off, we can enable these settings
            cmds = [
                "laser_dim, off",
                "low_latency, on",
                "enhance, seven",
                "motion_enhance, off",
                "graphic_mode, hires1",
            ]
        return await self.async_exec_command(cmds)

    async def async_hdr_picture_mode(self) -> bool:
        """
        Sets (opinionated!) optimal HDR film settings

        fyi: With the API turn on or off LL first otherwise it will be greyed out in the menu
        so PJ socket will time out
        """
        state = await self.async_get_low_latency_state()
        # If LL is on, we can turn it off first
        # TODO: make this more DRY
        if state:
            cmds = [
                "low_latency, off",
                "picture_mode, frame_adapt_hdr",
                "laser_dim, auto1",
                "enhance, seven",
                "motion_enhance, low",
                "graphic_mode, hires1",
            ]

            # ll_commands = self._build_mode_commands(cmds)
            # return ll_commands
            return await self.async_exec_command(cmds)
        else:
            # If LL is off, we can enable these settings
            cmds = [
                "picture_mode, frame_adapt_hdr",
                "laser_dim, auto1",
                "enhance, seven",
                "motion_enhance, low",
                "graphic_mode, hires1",
            ]

        return await self.async_exec_command(cmds)

    async def async_sdr_picture_mode(self) -> bool:
        """
        Sets (opinionated) optimal sdr film settings
        """
        state = await self.async_get_low_latency_state()
        # If LL is on, we need to turn it off
        # TODO: make this more DRY
        if state:
            cmds = [
                "low_latency, off",
                "laser_dim, auto1",
                "enhance, seven",
                "motion_enhance, low",
                "graphic_mode, hires1",
            ]

            # ll_commands = self._build_mode_commands(cmds)
            # return ll_commands
            return await self.async_exec_command(cmds)
        else:
            # If LL is off, we can enable these settings
            cmds = [
                "laser_dim, auto1",
                "enhance, seven",
                "motion_enhance, low",
                "graphic_mode, hires1",
            ]
        return await self.async_exec_command(cmds)

    # def _build_mode_commands(self, commands: list) -> list[str]:
    #     modes = self._check_low_latency()
    #     if modes == []:
    #         return modes

    #     ll_cmds = []
    #     for mode in modes:
    #         if "laser_dim" in mode:
    #             ll_cmds.append("laser_dim, off")
    #         if "picture_mode" in mode:
    #             ll_cmds.append("picture_mode, hdr")

    #     ll_cmds.extend(commands)

    #     return ll_cmds

    async def _async_do_reference_op(self, command: str, ack: ACKs) -> tuple[str, bool]:
        cmd = (
            Header.reference.value
            + Header.pj_unit.value
            + Commands[command].value[0]
            + Footer.close.value
        )

        msg, success = await self._async_send_command(
            cmd,
            ack=ACKs[ack.name].value,
            command_type=Header.reference.value,
        )

        if success:
            msg = await self._async_replace_headers(msg)

        return msg, success

    def get_low_latency_state(self) -> bool:
        """Get the current state of LL"""

        return asyncio.run(self.async_get_low_latency_state())

    async def async_get_low_latency_state(self) -> bool:
        """Get the current state of LL"""
        state, _ = await self._async_do_reference_op("low_latency", ACKs.picture_ack)
        # LL is off, could be disabled
        if state == b"PM0":
            return False

        return True

    # async def _async_check_low_latency(self) -> list[str]:
    #     """
    #     Infer if Low Latency is disabled or not otherwise commands will hang

    #     Returns enabled modes that have to be disabled first
    #     """
    #     enabled_modes = []

    #     state = await self.get_low_latency_state()
    #     # LL is off, could be disabled
    #     if state:
    #         state, success = await self._async_do_reference_op(
    #             "laser_dim", ACKs.picture_ack
    #         )
    #         if success:
    #             if state != b"PM0":
    #                 self.logger.debug("Laser dimming is enabled")
    #                 enabled_modes.append("laser_dim")
    #         else:
    #             return "Error", state
    #         # see if its hdr10+ or frame adapt
    #         state, success = await self._async_do_reference_op(
    #             "picture_mode", ACKs.picture_ack
    #         )
    #         if success:
    #             if state in [b"PM0B", b"PM15"]:
    #                 self.logger.debug("Locked HDR is enabled")
    #                 enabled_modes.append("picture_mode")
    #         else:
    #             return "Error", state

    #     self.logger.debug("Low Latency check: %s", success)

    #     return enabled_modes

    async def _async_replace_headers(self, item: bytes) -> bytes:
        """
        Will strip all headers and returns the value itself
        """
        self.logger.debug("replacing headers for %s of type %s", item, type(item))
        headers = [x.value for x in Header] + [x.value for x in Footer]
        for header in headers:
            item = item.replace(header, b"")

        return item

    async def _async_get_power_state(self) -> str:
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
        msg, success = await self._async_send_command(
            cmd,
            ack=ACKs.power_ack.value,
            command_type=Header.reference.value,
        )

        # Handle error with unexpected acks
        if not success:
            self.logger.error("Error getting power state: %s", msg)
            return success

        # remove the headers
        state = await self._async_replace_headers(msg)

        return PowerStates(state.replace(ACKs.power_ack.value, b"")).name

    async def async_is_on(self) -> bool:
        """
        True if the current state is on|reserved
        """
        pw_status = [PowerStates.on.name, PowerStates.reserved.name]
        return await self._async_get_power_state() in pw_status

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
