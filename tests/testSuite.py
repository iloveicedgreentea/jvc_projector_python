import unittest
import os
from datetime import datetime
from dotenv import load_dotenv
from jvc_projector import JVCProjector
import asyncio

# load .env
load_dotenv()

password = os.getenv("JVC_PASSWORD")
host = os.getenv("JVC_HOST")
test_power = True if os.getenv("JVC_TEST_POWER") == "true" else False

# JVC will drop connection without throttling in place
jvc = JVCProjector(host=host, delay_ms=1500, connect_timeout=60, password=password)

test_start = datetime.now()
MIN_TEST_TIME = 100


def run(cmd):
    """
    Runs async commands in sync
    """
    return asyncio.run(cmd)


class TestFunctions(unittest.TestCase):
    """
    Test projector
    """

    def test_01power_state(self):
        """
        The PJ should report False for is_on state
        """
        state = run(jvc.async_is_on())
        if state:
            self.assertEqual(state, True)
        else:
            self.assertEqual(state, False)

    # def test_02power_on(self):
    #     """
    #     PJ should turn on and report
    #     """
    #     if test_power and not jvc.is_on():
    #         command = jvc.power_on()
    #         print(command)
    #         self.assertEqual(command, "PW")
    #     elif test_power:
    #         print("PJ is on, skipping power on test")
    #         pass

    # def test_04menu_buttons(self):
    #     """
    #     Should run menu functions and then exit
    #     """
    #     # TODO: add a test to run multiple menu commands with one connection
    #     # TODO: fix to use new way of sending command
    #     menu_tests = [
    #         "menu_back",
    #         "menu",
    #         "menu_left",
    #         "menu_right",
    #         "menu_down",
    #         "menu_back",
    #         "menu_up",
    #         "menu_ok",
    #         "menu",
    #         "menu_back",
    #     ]
    #     print("You should see menu pop up and change")
    #     for item in menu_tests:
    #         print(f"testing {item}")
    #         self.assertEqual(jvc.command(item), True)
    #     print("You should see menu disappear now")

    # def test_09power_off(self):
    #     """
    #     PJ should turn off
    #     """
    #     if test_power and jvc.is_on():
    #         # if test took less than 60, wait so PJ doesn't heat cycle
    #         test_now = datetime.now()
    #         test_delta = (test_now - test_start).seconds
    #         if test_delta < MIN_TEST_TIME:
    #             sleep_time = MIN_TEST_TIME - test_delta
    #             print(f"sleeping for {sleep_time} to let PJ finish warming up")
    #             sleep(sleep_time)

    #         command = jvc.power_off()
    #         self.assertEqual(command, "PW")
    #     elif test_power:
    #         print("PJ is on, skipping power on test")
    #         pass

    # def test_03picture_hdr_modes(self):
    #     """
    #     PJ should switch between picture modes
    #     """
    #     pm_tests = ["pm_frame_adapt", "pm_hdr", "pm_frame_adapt"]
    #     for item in pm_tests:
    #         print(f"testing {item}")
    #         self.assertEqual(jvc.command(item), True)
    #         sleep(5)

    # def test_05replace_headers(self):
    #     """
    #     Should strip all expected headers
    #     """
    #     pass

    # def test_06print_commands(self):
    #     """
    #     print_commands() should run
    #     """
    #     pass


if __name__ == "__main__":
    runner = unittest.main()
