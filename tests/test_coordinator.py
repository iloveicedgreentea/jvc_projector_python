import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from jvc_projector.jvc_projector import JVCProjectorCoordinator, JVCInput
from jvc_projector.commands import (
    PJ_ACK,
    PJ_OK,
    PJ_REQ,
    ACKs,
    AspectRatioModes,
    ColorSpaceModes,
    Commands,
    ContentTypes,
    ContentTypeTrans,
    Enum,
    EshiftModes,
    Footer,
    HdrData,
    HdrLevel,
    HdrProcessing,
    Header,
    InputLevel,
    InputModes,
    InstallationModes,
    LampPowerModes,
    LaserDimModes,
    LaserPowerModes,
    LowLatencyModes,
    MaskModes,
    PictureModes,
    PowerStates,
    SourceStatuses,
    TheaterOptimizer,
    model_map,
)

TEST_IP = "192.168.88.23"
TEST_PORT = 20554
TEST_PASSWORD = "123456789"

os.environ["LOG_LEVEL"] = "DEBUG"

# Note these tests assume projector is on because most commands will time out. Not fail, but time out because JVC can't even bother
# to return a response when a command is not successful


class TestCoordinator(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        options = JVCInput(TEST_IP, TEST_PASSWORD, TEST_PORT, 5)
        self.coordinator = JVCProjectorCoordinator(options)
        res = await self.coordinator.open_connection()
        assert res is True
        # Ensure projector is on
        is_on = await self.coordinator.is_on()
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
        await self.coordinator.close_connection()

    async def test_get_attribute(self):
        """ensure we can get all attributes"""
        # check return value against eunm __members__
        low_latency_state = await self.coordinator.get_low_latency_state()
        assert (
            low_latency_state in LowLatencyModes.__members__
        ), f"Unexpected low latency state: {low_latency_state}"

        res = await self.coordinator.get_software_version()
        assert isinstance(res, str)  # sw can change, but should be str

        picture_mode = await self.coordinator.get_picture_mode()
        assert picture_mode in PictureModes.__members__, "Picture mode not as expected."

        install_mode = await self.coordinator.get_install_mode()
        assert (
            install_mode in InstallationModes.__members__
        ), f"Unexpected install mode: {install_mode}"
        # Testing input mode

        input_mode = await self.coordinator.get_input_mode()
        assert (
            input_mode in InputModes.__members__
        ), f"Unexpected input mode: {input_mode}"

        # Testing mask mode
        mask_mode = await self.coordinator.get_mask_mode()
        assert mask_mode in MaskModes.__members__, f"Unexpected mask mode: {mask_mode}"

        # Testing laser mode
        laser_mode = await self.coordinator.get_laser_mode()
        assert (
            laser_mode in LaserDimModes.__members__
        ), f"Unexpected laser mode: {laser_mode}"

        # Testing eshift mode
        eshift_mode = await self.coordinator.get_eshift_mode()
        assert (
            eshift_mode in EshiftModes.__members__
        ), f"Unexpected eshift mode: {eshift_mode}"

        # Testing color mode
        color_mode = await self.coordinator.get_color_mode()
        assert (
            color_mode in ColorSpaceModes.__members__
        ), f"Unexpected color mode: {color_mode}"

        # Testing input level
        input_level = await self.coordinator.get_input_level()
        assert (
            input_level in InputLevel.__members__
        ), f"Unexpected input level: {input_level}"

        # Testing software version
        software_version = await self.coordinator.get_software_version()
        assert isinstance(software_version, str), "Software version is not a string"

        # Testing content type
        content_type = await self.coordinator.get_content_type()
        assert (
            content_type in ContentTypes.__members__
        ), f"Unexpected content type: {content_type}"

        # Testing content type transition
        content_type_trans = await self.coordinator.get_content_type_trans()
        assert (
            content_type_trans in ContentTypeTrans.__members__
        ), f"Unexpected content type transition: {content_type_trans}"

        # Cant test this without signal because again, JVC can't be bothered to return a failure these just time out
        # # Testing HDR processing
        # hdr_processing = await self.coordinator.get_hdr_processing()
        # assert hdr_processing in HdrProcessing.__members__, f"Unexpected HDR processing: {hdr_processing}"

        # # Testing HDR level
        # hdr_level = await self.coordinator.get_hdr_level()
        # assert hdr_level in HdrLevel.__members__, f"Unexpected HDR level: {hdr_level}"

        # # Testing HDR data
        # hdr_data = await self.coordinator.get_hdr_data()
        # assert hdr_data in HdrData.__members__, f"Unexpected HDR data: {hdr_data}"

        # Testing lamp power
        lamp_power = await self.coordinator.get_lamp_power()
        # unknown would mean it worked but returned an unmapped value, thats fine
        assert (
            lamp_power in LampPowerModes.__members__ or lamp_power == "unknown"
        ), f"Unexpected lamp power: {lamp_power}"

        # Testing lamp time
        lamp_time = await self.coordinator.get_lamp_time()
        assert isinstance(lamp_time, int), "Lamp time is not an integer"

        # Testing laser power
        laser_power = await self.coordinator.get_laser_power()
        assert (
            laser_power in LaserPowerModes.__members__
        ), f"Unexpected laser power: {laser_power}"

        # Testing theater optimizer state
        # theater_optimizer_state = await self.coordinator.get_theater_optimizer_state()
        # assert theater_optimizer_state in TheaterOptimizer.__members__, f"Unexpected theater optimizer state: {theater_optimizer_state}"

        # Testing aspect ratio
        aspect_ratio = await self.coordinator.get_aspect_ratio()
        assert (
            aspect_ratio in AspectRatioModes.__members__
        ), f"Unexpected aspect ratio: {aspect_ratio}"

        # Testing source status
        source_status = await self.coordinator.get_source_status()
        assert (
            source_status in SourceStatuses.__members__
        ), f"Unexpected source status: {source_status}"

        # Testing is_on
        is_on = await self.coordinator.is_on()
        assert isinstance(is_on, bool), "is_on is not a boolean"

        # Testing is_ll_on
        is_ll_on = await self.coordinator.is_ll_on()
        assert isinstance(is_ll_on, bool), "is_ll_on is not a boolean"

        # test commands
        _, res = await self.coordinator.exec_command(["menu, menu"])
        print(res)
        assert res is True
        # close menu
        if res:
            _, res = await self.coordinator.exec_command(["menu, menu"])


if __name__ == "__main__":
    unittest.main()
