import unittest
import os
from dotenv import load_dotenv
from jvc_projector.jvc_projector import JVCProjector

# load .env
load_dotenv()

password = os.getenv("JVC_PASSWORD")
host = os.getenv("JVC_HOST")

# JVC will drop connection without throttling in place
jvc = JVCProjector(host=host, connect_timeout=10, password=password)


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
        out = jvc.get_eshift_mode()
        print(out)
        out = jvc.get_input_level()
        print(out)
        out = jvc.get_install_mode()
        print(out)
        out = jvc.get_laser_mode()
        print(out)
        out = jvc.is_on()
        print(out)
        out = jvc.is_ll_on()
        print(out)
        out = jvc.info()
        print(out)