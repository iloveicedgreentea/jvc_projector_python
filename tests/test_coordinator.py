import asyncio
import os
import unittest
from jvc_projector.jvc_projector import JVCProjectorCoordinator, JVCInput
from jvc_projector.commands import (
    AspectRatioModes,
    ColorSpaceModes,
    ContentTypes,
    ContentTypeTrans,
    InputLevel,
    AnamorphicModes,
    InputModes,
    InstallationModes,
    LampPowerModes,
    LaserDimModes,
    LaserPowerModes,
    MaskModes,
    PictureModes,
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
            self.fail("PJ is off, turn on to run tests")
            msg = await self.coordinator.power_on()
            print(msg)

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

    async def assert_modes(self):  # pylint: disable=too-many-locals
        """helper function for attr"""
        # in one test so it doesnt constantly open and close connection
        # check return value against eunm __members__
        low_latency_state = await self.coordinator.get_low_latency_state()
        self.assertIn(
            low_latency_state, [False, True], "Low latency state not on or off"
        )
        _, res = await self.coordinator.exec_command(["laser_power, low"])
        self.assertTrue(res, "failed to set laser power to low")

        # test getting resolution
        res = await self.coordinator.get_source_display()
        self.assertIn(res, ["4K_4096p24", "NoSignal"], "Source display not as expected")

        res = await self.coordinator.get_anamorphic()
        self.assertIn(res, AnamorphicModes.__members__, "Anamorphic not as expected")

        picture_mode = await self.coordinator.get_picture_mode()
        self.assertIn(
            picture_mode, PictureModes.__members__, "Picture mode not as expected."
        )

        install_mode = await self.coordinator.get_install_mode()
        self.assertIn(
            install_mode,
            InstallationModes.__members__,
            f"Unexpected install mode: {install_mode}",
        )
        print(install_mode)
        # Testing input mode

        input_mode = await self.coordinator.get_input_mode()
        self.assertIn(
            input_mode, InputModes.__members__, f"Unexpected input mode: {input_mode}"
        )

        # Testing mask mode
        mask_mode = await self.coordinator.get_mask_mode()
        self.assertIn(
            mask_mode, MaskModes.__members__, f"Unexpected mask mode: {mask_mode}"
        )

        # Testing laser mode
        laser_mode = await self.coordinator.get_laser_mode()
        self.assertIn(
            laser_mode,
            LaserDimModes.__members__,
            f"Unexpected laser mode: {laser_mode}",
        )

        # Testing eshift mode
        eshift_mode = await self.coordinator.get_eshift_mode()
        self.assertIn(
            eshift_mode,
            [True, False],
            f"Unexpected eshift mode: {eshift_mode}",
        )

        # Testing color mode
        color_mode = await self.coordinator.get_color_mode()
        self.assertIn(
            color_mode,
            ColorSpaceModes.__members__,
            f"Unexpected color mode: {color_mode}",
        )

        # Testing input level
        input_level = await self.coordinator.get_input_level()
        self.assertIn(
            input_level,
            InputLevel.__members__,
            f"Unexpected input level: {input_level}",
        )

        # Testing software version
        software_version = await self.coordinator.get_software_version()
        self.assertIsInstance(
            software_version, float, "Software version is not a float"
        )
        self.assertGreater(
            software_version, 0, "Software version is not greater than 0"
        )
        print(software_version)
        # fw 3.0 and above
        if software_version > 2.10:
            res = await self.coordinator.get_laser_value()
            print("laser value", res)
            self.assertIsInstance(res, int)
            self.assertEqual(res, 0, "Laser value is over 100")

        # Testing content type
        content_type = await self.coordinator.get_content_type()
        self.assertIn(
            content_type,
            ContentTypes.__members__,
            f"Unexpected content type: {content_type}",
        )

        # Testing content type transition
        content_type_trans = await self.coordinator.get_content_type_trans()
        self.assertIn(
            content_type_trans,
            ContentTypeTrans.__members__,
            f"Unexpected content type transition: {content_type_trans}",
        )

        # Testing lamp power
        lamp_power = await self.coordinator.get_lamp_power()
        # unknown would mean it worked but returned an unmapped value, thats fine
        self.assertTrue(
            lamp_power in LampPowerModes.__members__ or lamp_power == "unknown",
            f"Unexpected lamp power: {lamp_power}",
        )

        # Testing lamp time
        lamp_time = await self.coordinator.get_lamp_time()
        self.assertIsInstance(lamp_time, int, "Lamp time is not an integer")

        # Testing laser power
        laser_power = await self.coordinator.get_laser_power()
        self.assertIn(
            laser_power,
            LaserPowerModes.__members__,
            f"Unexpected laser power: {laser_power}",
        )
        print("laser power", laser_power)

        # Testing aspect ratio
        aspect_ratio = await self.coordinator.get_aspect_ratio()
        self.assertIn(
            aspect_ratio,
            AspectRatioModes.__members__,
            f"Unexpected aspect ratio: {aspect_ratio}",
        )

        # Testing source status
        source_status = await self.coordinator.get_source_status()
        self.assertIn(
            source_status,
            [True, False],
            f"Unexpected source status: {source_status}",
        )
        self.assertIsInstance(source_status, bool)
        print("source status", source_status)

        # Testing is_on
        is_on = await self.coordinator.is_on()
        self.assertIsInstance(is_on, bool, "is_on is not a boolean")

        # Testing is_ll_on
        is_ll_on = await self.coordinator.is_ll_on()
        self.assertIsInstance(is_ll_on, bool, "is_ll_on is not a boolean")

        res = await self.coordinator.exec_command(["laser_value, 35"])
        print("laser value set to", res)
        if software_version > 2.10:
            res = await self.coordinator.get_laser_value()
            print("laser value", res)

            self.assertEqual(res, 35, "Laser value is not 35")

    async def test_exec_commands(self):
        """test executing commands"""
        # get attr
        await self.assert_modes()

        # test commands
        _, res = await self.coordinator.exec_command(["menu, menu"])
        print(res)
        assert res is True
        # close menu
        if res:
            _, res = await self.coordinator.exec_command(["menu, menu"])

    async def test_turn_off(self):
        """unskip to turn off pj after tests"""
        # self.skipTest("not turning off")
        _, res = await self.coordinator.exec_command(["power, off"])
        assert res, "failed to turn off"


if __name__ == "__main__":
    unittest.main()
