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
jvc.open_connection()

class TestFunctions(unittest.TestCase):
    """
    Test projector
    """
    def test_mock_update(self):
        """Emulates how HA would run updates"""
        state = jvc.is_on()
        self.assertEqual(state, True)
        if state:
            lowlatency_enabled = jvc.is_ll_on()
            installation_mode = jvc.get_install_mode()
            input_mode = jvc.get_input_mode()
            laser_mode = jvc.get_laser_mode()
            eshift = jvc.get_eshift_mode()
            color_mode = jvc.get_color_mode()
            input_level = jvc.get_input_level()

        self.assertFalse(lowlatency_enabled)
        self.assertEqual(installation_mode, "mode3")
        self.assertEqual(input_mode, "hdmi2")
        self.assertEqual(laser_mode, "auto3")
        self.assertEqual(eshift, "off")
        self.assertEqual(color_mode, "auto")
        self.assertEqual(input_level, "standard")
    
    def test_send_command(self):
        """test a command"""
        # open menu
        ack, success = jvc.exec_command("menu, menu")

        self.assertEqual(ack, "ok")
        self.assertTrue(success)

        # close menu
        ack, success = jvc.exec_command("menu, menu")
        self.assertEqual(ack, "ok")
        self.assertTrue(success)