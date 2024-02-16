import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from jvc_projector.jvc_projector import JVCProjectorCoordinator, JVCInput

TEST_IP = "192.168.88.23"
TEST_PORT = 20554
TEST_PASSWORD = "123456789"

os.environ["LOG_LEVEL"] = "DEBUG"

class TestCoordinator(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        input = JVCInput(TEST_IP, TEST_PASSWORD, TEST_PORT, 5)
        self.coordinator = JVCProjectorCoordinator(input)
    async def asyncTearDown(self):
        await self.coordinator.close_connection()
    async def test_get_attribute(self):
        res = await self.coordinator.open_connection()
        assert res == True
        is_on = await self.coordinator.is_on()
        assert is_on == False


if __name__ == "__main__":
    unittest.main()