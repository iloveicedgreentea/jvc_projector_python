import unittest
import os
from datetime import datetime
from dotenv import load_dotenv
from jvc_projector.jvc_projector import JVCProjector
import asyncio

# load .env
load_dotenv()

password = os.getenv("JVC_PASSWORD")
host = os.getenv("JVC_HOST")
test_power = True if os.getenv("JVC_TEST_POWER") == "true" else False

# JVC will drop connection without throttling in place
loop = asyncio.get_event_loop()
jvc = JVCProjector(host=host, connect_timeout=60, password=password, loop=loop)


class TestFunctions(unittest.TestCase):
    """
    Test projector
    """
    # def test_01power_state(self):
    #     """
    #     The PJ should report True for is_on state
    #     """
    #     state = asyncio.run(jvc.async_is_on())
        
    #     self.assertEqual(state, True)

    def test_02lowlat(self):
        out = asyncio.run(jvc.async_get_eshift_mode())
        print(out)