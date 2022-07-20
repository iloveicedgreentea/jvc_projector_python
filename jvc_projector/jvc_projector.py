"""
Implements the JVC protocol
"""

import logging
from typing import Final, Union
import asyncio
from jvc_projector.commands import ACKs, Footer, Header, Commands, PowerStates, Enum


class JVCProjector:
    """JVC Projector Control"""

    def __init__(
        self,
        host: str,
        password: str = "",
        # Can supply a logger object. It can hook into the HA logger
        logger: logging.Logger = logging.getLogger(__name__),
        loop: asyncio.AbstractEventLoop = None,
        port: int = 20554,
        connect_timeout: int = 10,
    ):
        self.host = host
        self.port = port
        # NZ models have password authentication
        self.password = password
        self.connect_timeout: int = connect_timeout
        self.logger = logger
        self._lock = asyncio.Lock()
        # Const values
        self.PJ_OK: Final = ACKs.greeting.value
        self.PJ_ACK: Final = ACKs.pj_ack.value
        self.PJ_REQ: Final = ACKs.pj_req.value
        self.reader: asyncio.StreamReader = None
        self.writer: asyncio.StreamWriter = None
        self.command_read_timeout = 3

    async def async_open_connection(self) -> bool:
        """Open a connection"""
        self.logger.debug("Starting open connection")
        msg, success = await self.reconnect()

        if not success:
            self.logger.error(msg)

        return success

    async def reconnect(self):
        """Initiate keep-alive connection"""
        while True:
            try:
                if self.writer is not None:
                    self.logger.debug("Closing writer")
                    self.writer.close()
                    await self.writer.wait_closed()
                self.logger.debug(
                    "Connecting to JVC Projector: %s:%s", self.host, self.port
                )
                cor = asyncio.open_connection(self.host, self.port)
                # wait for 10 sec to connect
                self.reader, self.writer = await asyncio.wait_for(cor, 10)
                self.logger.debug("Connected to JVC Projector")
                # create a reader and writer to do handshake
                self.logger.debug("Handshaking")
                result, success = await self._async_handshake()
                if not success:
                    return result, success
                self.logger.debug("Handshake complete and we are connected")
                return "Connection done", True

            # includes conn refused
            except OSError as err:
                self.logger.warning("Connecting failed, retrying in %i seconds", 2)
                self.logger.debug(err)
                await asyncio.sleep(2)
            except asyncio.TimeoutError:
                self.logger.warning("Connection timed out, retrying in %i seconds", 2)
                await asyncio.sleep(2)

    async def _async_handshake(self) -> tuple[str, bool]:
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
        msg_pjok = await self.reader.read(len(self.PJ_OK))
        self.logger.debug(msg_pjok)
        if msg_pjok != self.PJ_OK:
            result = f"Projector did not reply with correct PJ_OK greeting: {msg_pjok}"
            self.logger.error(result)
            return result, False

        # try sending PJREQ, if there's an error, raise exception
        try:
            self.writer.write(pj_req)
            await self.writer.drain()
        except asyncio.TimeoutError as err:
            result = f"Timeout sending PJREQ {err}"
            self.logger.error(result)
            return result, False

        # see if we receive PJACK, if not, raise exception
        msg_pjack = await self.reader.read(len(self.PJ_ACK))
        if msg_pjack != self.PJ_ACK:
            result = f"Exception with PJACK: {msg_pjack}"
            self.logger.error(result)
            return result, False
        self.logger.debug("Handshake successful")
        return "ok", True

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

        if self.writer is None:
            self.logger.error("Connection lost. Restarting")

            await self.reconnect()

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
        retry_count = 0
        while retry_count < 5:
            self.logger.debug("do_command sending command: %s", command)
            # send the command
            self.writer.write(command)
            try:
                await self.writer.drain()
            except ConnectionError as err:
                # reaching this means the writer was closed somewhere
                self.logger.error(err)
                self.logger.debug("Restarting connection")
                # restart the connection

                await self.reconnect()
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
                # seems like certain commands timeout when PJ is off
                received_ack = await asyncio.wait_for(
                    self.reader.readline(), timeout=self.command_read_timeout
                )
            except asyncio.TimeoutError:
                # LL is used in async_update() and I don't want to spam HA logs so we skip
                # if not command == b"?\x89\x01PMLL\n":
                # Sometimes if you send a command that is greyed out, the PJ will just hang
                self.logger.error(
                    "Connection timed out. Command %s is probably not allowed to run at this time.",
                    command,
                )
                self.logger.debug("restarting connection")

                await self.reconnect()
                retry_count += 1
                continue

            except ConnectionRefusedError:
                self.logger.error("Connection Refused when getting ack")
                self.logger.debug("restarting connection")

                await self.reconnect()
                retry_count += 1
                continue

            self.logger.debug("received ack from PJ: %s", received_ack)

            # This will probably never happen since we are handling timeouts now
            if received_ack == b"":
                self.logger.error("Got a blank ack. Restarting connection")

                await self.reconnect()
                retry_count += 1
                continue

            # get the ack for operation
            if received_ack == ack_value and command_type == Header.operation.value:
                return received_ack, True

            # if we got what we expect and this is a reference,
            # receive the data we requested
            if received_ack == ack_value and command_type == Header.reference.value:
                message = await self.reader.readline()
                self.logger.debug("received message from PJ: %s", message)

                return message, True

            # Otherwise, it failed
            # Because this now reuses a connection, reaching this stage means catastrophic failure, or HA running as usual :)
            self.logger.error(
                "Recieved ack did not match expected ack: %s != %s",
                received_ack,
                ack_value,
            )
            # Try to restart connection, if we got here somethihng is out of sync

            await self.reconnect()
            retry_count += 1
            continue

        self.logger.error("retry count for running commands exceeded")
        return "retry count exceeded", False

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
