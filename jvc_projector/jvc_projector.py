"""
Implements the JVC protocol
"""

import logging
from typing import Final, Union, Awaitable, Callable
import asyncio
from jvc_projector.optimal_settings import hdr_film, hdr_game, sdr_film, sdr_game
from jvc_projector.commands import ACKs, Footer, Header, Commands, PowerStates, Enum


class JVCProjector:
    """JVC Projector Control"""

    def __init__(
        self,
        host: str,
        password: str = "",
        # Can supply a logger object. It can hook into the HA logger
        logger: logging.Logger = logging.getLogger(__name__),
        connection_lost_callback: Callable[[], Awaitable[None]] = None,
        loop: asyncio.AbstractEventLoop = None,
        update_callback: Callable[[str], None] = None,
        port: int = 20554,
        connect_timeout: int = 10,
    ):
        self.host = host
        self.port = port
        # NZ models have password authentication
        self.password = password
        self.connect_timeout: int = connect_timeout
        self.logger = logger
        self._update_callback = update_callback
        # use the provided loop or get current one. Otherwise make one
        try:
            self._loop = loop or asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.new_event_loop()
        self._lock = asyncio.Lock()
        # Const values
        self.PJ_OK: Final = ACKs.greeting.value
        self.PJ_ACK: Final = ACKs.pj_ack.value
        self.PJ_REQ: Final = ACKs.pj_req.value
        self._connection_lost_callback = connection_lost_callback
        self._closed = False
        self._retry_interval = 1
        self._closing = False
        self._halted = False
        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None

    async def async_open_connection(self) -> bool:
        """Open a connection"""
        assert self.port >= 0, f"Port must be greater than 0: {self.port}"
        assert self.host != "", f"Host must not be empty: {self.host}"
        assert (
            self.connect_timeout >= 2
        ), f"connect_timeout must be over 1: {self.connect_timeout}"

        msg, success = await self.reconnect()
        if not success:
            self.logger.error(msg)

        return success

    async def reconnect(self):
        """Initiate keep-alive connection"""
        while True:
            try:
                if self._halted:
                    await asyncio.sleep(2)

                self.logger.debug(
                    "Connecting to JVC Projector: %s:%s", self.host, self.port
                )
                async with self._lock:
                    # transport, protocol = await self._loop.create_connection(
                    #     lambda: self.protocol, self.host, self.port
                    # )
                    self.reader, self.writer = await asyncio.open_connection(
                        self.host, self.port, loop=self._loop
                    )
                    self.logger.debug("Connected to JVC Projector")
                    # create a reader and writer to do handshake
                async with self._lock:
                    self.logger.debug("Handshaking")
                    result, success = await self._async_handshake()
                    if not success:
                        return result, success
                    self.logger.debug("Handshake complete and we are connected")
                self._reset_retry_interval()
                return "Connection done", True

            # includes conn refused
            except OSError as err:
                self._increase_retry_interval()
                interval = self._get_retry_interval()
                self.logger.warning(
                    "Connecting failed, retrying in %i seconds", interval
                )
                if not self._closing:
                    return f"Connection failed: {err}", False
                await asyncio.sleep(interval)
            except asyncio.TimeoutError:
                self._increase_retry_interval()
                interval = self._get_retry_interval()
                self.logger.warning(
                    "Connection timed out, retrying in %i seconds", interval
                )
                if not self._closing:
                    return "Connection timed out", False
                await asyncio.sleep(interval)

    async def _async_handshake(self) -> tuple[str, bool]:
        """
        Do the 3 way handshake

        Projector sends PJ_OK, client sends PJREQ (with optional password) within 5 seconds, projector replies with PJACK
        first, after connecting, see if we receive PJ_OK. If not, raise exception
        """
        if self.password:
            pj_req = self.PJ_REQ + f"_{self.password}".encode()
        else:
            pj_req = self.PJ_REQ

        # 3 step handshake
        msg_pjok = await self.reader.read(len(self.PJ_OK))
        self.logger.debug(msg_pjok)
        if msg_pjok != self.PJ_OK:
            result = f"Projector did not reply with correct PJ_OK greeting: {msg_pjok}"
            success = False

            return result, success

        # try sending PJREQ, if there's an error, raise exception
        try:
            self.writer.write(pj_req)
            await self.writer.drain()
        except asyncio.TimeoutError as err:
            return f"Timeout sending PJREQ {err}", False

        # see if we receive PJACK, if not, raise exception
        msg_pjack = await self.reader.read(len(self.PJ_ACK))
        if msg_pjack != self.PJ_ACK:
            return f"Exception with PJACK: {msg_pjack}", False

        return "ok", True

    async def connection_lost(self):
        """restart connection"""
        if not self._closing:
            await self.reconnect()

    def _get_retry_interval(self):
        return self._retry_interval

    def _reset_retry_interval(self):
        self._retry_interval = 1

    def _increase_retry_interval(self):
        self._retry_interval = min(300, 1.5 * self._retry_interval)

    def close(self):
        # TODO: maybe implement these
        """Close the AVR device connection and don't try to reconnect."""
        self.logger.debug("Closing connection to AVR")
        self._closing = True

    def halt(self):
        """Close the AVR device connection and wait for a resume() request."""
        self.logger.warning("Halting connection to AVR")
        self._halted = True

    def resume(self):
        """Resume the AVR device connection if we have been halted."""
        self.logger.warning("Resuming connection to AVR")
        self._halted = False

    async def _async_send_command(
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
        if command_type == Header.reference.value:
            result, success = await self._async_do_command(
                send_command, ack, command_type
            )

            return result, success

        if isinstance(send_command, list):

            for cmd in send_command:
                cons_command, ack = await self._async_construct_command(
                    cmd, command_type
                )
                if not ack:
                    return cons_command, ack
                # need a delay otherwise it kills connection
                await asyncio.sleep(0.1)
                result, success = await self._async_do_command(
                    cons_command, ack.value, command_type
                )
                if not success:
                    return result, success
        else:
            try:
                cons_command, ack = await self._async_construct_command(
                    send_command, command_type
                )
            except TypeError:
                cons_command = send_command

            if not ack:
                return cons_command, ack
            result, success = await self._async_do_command(
                cons_command, ack.value, command_type
            )
            if not success:
                return result, success

        self.logger.debug("send command result: %s", result)
        return "ok", True

    async def _async_do_command(
        self,
        command: bytes,
        ack: bytes,
        command_type: bytes = b"!",
    ) -> tuple[str, bool]:
        async with self._lock:
            self.logger.debug("_do_command sending command: %s", command)
            # send the command
            self.writer.write(command)
            try:
                await self.writer.drain()
            except ConnectionError as err:
                # reaching this means the writer was closed somewhere
                self.logger.error(err)
                # restart the connection
                await self.connection_lost()
                self.writer.write(command)
                await self.writer.drain()

            # if we send a command that returns info, the projector will send
            # an ack, followed by the actual message. Check to see if the ack sent by
            # projector is correct, then return the message.
            ack_value = (
                Header.ack.value + Header.pj_unit.value + ack + Footer.close.value
            )
            self.logger.debug("ack_value: %s", ack_value)

            # Receive the acknowledgement from PJ
            try:
                received_ack = await self.reader.read(len(ack_value))
            except asyncio.TimeoutError:
                # Sometimes if you send a command that is greyed out, the PJ will just hang
                result = "Connection timed out. Command is probably not allowed to run at this time."
                self.logger.error(result)
                return result, False
            except ConnectionRefusedError:
                self.logger.error("Connection Refused when getting ack")
                return "Connection Refused", False

            self.logger.debug("received_ack: %s", received_ack)

            # get the ack for operation
            if received_ack == ack_value and command_type == Header.operation.value:
                self.logger.debug("result: %s", received_ack)
                return received_ack, True

            # if we got what we expect and this is a reference,
            # receive the data we requested
            if received_ack == ack_value and command_type == Header.reference.value:
                message = await self.reader.read(1024)
                self.logger.debug("result: %s, %s", received_ack, message)

                return message, True

            # Otherwise, it failed
            # Because this now reuses a connection, reaching this stage means catastrophic failure, or HA running as usual :)
            result = "Unexpected ack received from PJ after sending a command. Perhaps a command got cancelled because a new connection was made."
            self.logger.error(result)
            self.logger.error("received_ack: %s", received_ack)
            self.logger.error("ack_value: %s", ack_value)

            return result, False

    async def _async_construct_command(
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
        Sync wrapper for async_exec_command
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
        return await self._async_send_command(command, command_type)

    async def async_info(self) -> tuple[str, bool]:
        """
        Bring up the Info screen
        """
        cmd = (
            Header.operation.value
            + Header.pj_unit.value
            + Commands.info.value
            + Footer.close.value
        )

        return await self._async_send_command(
            cmd,
            ack=ACKs.menu_ack,
            command_type=Header.operation.value,
        )

    def power_on(
        self,
    ) -> tuple[str, bool]:
        """
        sync wrapper for async_power_on
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
        sync wrapper for async_power_off
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
        # TODO: use Userx modes for this
        state = await self.async_get_low_latency_state()
        await asyncio.sleep(3)
        # If LL is on, we can turn it off first
        # TODO: make this more DRY
        if state:
            cmds = [
                "picture_mode, hdr",
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
                "picture_mode, hdr",
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
        # task = asyncio.create_task(self.async_get_low_latency_state())
        state = await self.async_get_low_latency_state()
        # todo: fix this, its a concurrency issue
        await asyncio.sleep(3)
        # If LL is on, we can turn it off first

        if state is None:
            return "Error getting low latency state"

        if state:
            cmds = [
                "enhance, seven",
                "motion_enhance, off",
                "graphic_mode, hires1",
            ]

            # ll_commands = self._build_mode_commands(cmds)
            # return ll_commands
            return await self.async_exec_command(cmds)
        elif state is False:
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
        await asyncio.sleep(3)
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
                "laser_dim, off",
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
        await asyncio.sleep(3)
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
        """
        Get the current state of LL

        None if there was an error
        """
        state, success = await self._async_do_reference_op(
            "low_latency", ACKs.picture_ack
        )
        # LL is off, could be disabled
        if not success:
            return None
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
