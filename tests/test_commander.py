import asyncio
import os
import unittest
from jvc_projector.jvc_projector import JVCProjectorCoordinator, JVCInput
from jvc_projector.commands import (
    AspectRatioModes,
    ColorSpaceModes,
    ContentTypes,
    ContentTypeTrans,
    EshiftModes,
    InputLevel,
    AnamorphicModes,
    InputModes,
    InstallationModes,
    LampPowerModes,
    LaserDimModes,
    LaserPowerModes,
    ResolutionModes,
    LowLatencyModes,
    MaskModes,
    PictureModes,
    SourceStatuses,
)

TEST_IP = "192.168.88.23"
TEST_PORT = 20554
TEST_PASSWORD = "123456789"

os.environ["LOG_LEVEL"] = "DEBUG"

# Note these tests assume projector is on because most commands will time out. Not fail, but time out because JVC can't even bother
# to return a response when a command is not successful


class TestCoordinator(unittest.IsolatedAsyncioTestCase):
    """Test running commands"""

    async def asyncSetUp(self):
        # set up connection
        options = JVCInput(TEST_IP, TEST_PASSWORD, TEST_PORT, 5)
        self.coordinator = JVCProjectorCoordinator(options)

        # connect to PJ
        res = await self.coordinator.open_connection()
        assert res is True

        # Ensure projector is on
        is_on = await self.coordinator.is_on()
        # turn on if not already
        if not is_on:
            _, res = await self.coordinator.power_on()
            assert res is True

        # wait for projector to turn on
        timeout = 120  # units technically, not really seconds but who cares
        while timeout > 0:
            await asyncio.sleep(1)
            is_on = await self.coordinator.is_on()
            if is_on:
                break
            timeout -= 1

    async def asyncTearDown(self):
        """clean up connection between tests otherwise error"""
        await self.coordinator.close_connection()

    async def test_send_command(self):
        """Test sending a command"""
        res = await self.coordinator.commander.send_command("laser_value", b"?")
        print(res)
        assert res, "failed to send command"

    async def turn_off(self):
        """unskip to turn off pj after tests"""
        self.skipTest("not turning off")
        _, res = await self.coordinator.exec_command("power, off")
        assert res, "failed to turn off"


if __name__ == "__main__":
    unittest.main()
