"""
Creates jvc mock
"""

import asyncio
import sys

class JVCMock:
    """
    Mock
    """

    def __init__(
        self, host: str = "127.0.0.1", port: int = 20554, password: str = "12345678"
    ):
        if len(password) < 7 or len(password) > 10:
            raise ValueError("Password must be greater than 7 and less than 10")
        self.host = host
        self.port = port
        # NZ models have password authentication
        self.password = password

        self.pj_ok = b"PJ_OK"
        self.pj_ack = b"PJACK"
        self.pj_req = b"PJREQ"

        self.server = None

    async def async_listen(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """
        JVC server
        """
        # write pj ok first
        writer.write(self.pj_ok)
        await writer.drain()

        # wait to get pj_req + up to 10 char password and underscore
        pjreq_data = await reader.read(16)

        if isinstance(pjreq_data, str):
            pjreq_data = pjreq_data.encode()

        if self.pj_req not in pjreq_data:
            writer.write(b"PJNAK")
            print("bad PJ REQ")
            await writer.drain()
            writer.close()
            
            return

        # get the pw
        try:
            _, password = pjreq_data.split(b"_")
        except ValueError as err:
            print(err)
            password = None

        except TypeError as err:
            print(err)
            writer.close()

            return

        # return ack to client
        if password == self.password.encode() or password is None:
            writer.write(self.pj_ack)
            await writer.drain()
        else:
            writer.write(b"PJNAK")
            print(f"bad password {password}")
            await writer.drain()
            return


        # TODO: implement acks properly
        # TODO: make this loop
        return await self.get_command(reader, writer)

    async def get_command(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> bool:
        """
        receive a command
        """

        command_data = await reader.read(1024)
        print(f"Got command {command_data}")
        ack = b""
        if b"RC" in command_data:
            ack = b"\x06\x89\x01RC\n"
        if b"PW" in command_data:
            ack = b"\x06\x89\x01PW\n"
        if b"PM" in command_data:
            ack = b"\x06\x89\x01PM\n"

        writer.write(ack)
        await writer.drain()

        # write a reference response
        if b"?" in command_data:
            if b"PW" in command_data:
                print("Saying the power is on")
                writer.write(b"\x06\x89\x01PW1\n")
                await writer.drain()
            if b"PM" in command_data:
                print("Saying LL is on")
                writer.write(b"\x06\x89\x01PM1\n")
                await writer.drain()
        writer.close()

    async def main(self):
        """
        Start server
        """
        self.server = await asyncio.start_server(self.async_listen, self.host, self.port)

        async with self.server:
            await self.server.start_serving()
            await self.server.wait_closed()

    def run(self):
        """runs
        """
        try:
            asyncio.run(self.main())
        except KeyboardInterrupt:
            print("Exiting")
            sys.exit(0)

jvc = JVCMock()

jvc.run()