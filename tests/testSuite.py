import unittest
import os
from jvc_projector import JVCProjector
from dotenv import load_dotenv
from time import sleep
from datetime import datetime

# load .env
load_dotenv()

password = os.getenv("JVC_PASSWORD")
host = os.getenv("JVC_HOST")
test_power = True if os.getenv("JVC_TEST_POWER") == "true" else False

# JVC will drop connection without throttling in place
jvc = JVCProjector(host=host, delay_ms=1500, connect_timeout=60, password=password)

if jvc.is_on() and test_power:
    print("Projector should be off to ensure the tests work fully")
    print("Caution: Running power on/off tests more than once every few minutes is really bad for your PJ")

test_start = datetime.now()
minimum_test_time = 100

class TestFunctions(unittest.TestCase):
    def test_power_state(self):
        """
        The PJ should report False for is_on state
        """
        if jvc.is_on():
            self.assertEqual(jvc.is_on(), True)
        else:
            self.assertEqual(jvc.is_on(), False)

    def test_power_on(self):
        """
        PJ should turn on and report
        """
        if test_power and not jvc.is_on() :
            command = jvc.power_on()
            print(command)
            self.assertEqual(command, "PW")
        elif test_power:
            print("PJ is on, skipping power on test")
            pass

    def test_menu_buttons(self):
        menu_tests = ["menu_back", "menu", "menu_left", "menu_right", "menu_down", "menu_back", "menu_up", "menu_ok", "menu", "menu_back"]
        print("You should see menu pop up and change")
        for item in menu_tests:
            print(f"testing {item}")
            self.assertEqual(jvc.command(item), True)
        print("You should see menu disappear now")

    def test_power_off(self):
        """
        PJ should turn off
        """
        if test_power and jvc.is_on():
            # if test took less than 60, wait so PJ doesn't heat cycle
            test_now = datetime.now() 
            test_delta = (test_now-test_start).seconds
            if test_delta < minimum_test_time:
                sleep_time = minimum_test_time-test_delta
                print(f"sleeping for {sleep_time} to let PJ finish warming up")
                sleep(sleep_time)

            command = jvc.power_off()
            self.assertEqual(command, "PW")
        elif test_power:
            print("PJ is on, skipping power on test")
            pass
    
    def test_picture_hdr_modes(self):
        """
        PJ should switch between picture modes
        """
        pm_tests = ["pm_frame_adapt", "pm_hdr", "pm_frame_adapt"]
        for item in pm_tests:
            print(f"testing {item}")
            self.assertEqual(jvc.command(item), True)
            sleep(5)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(TestFunctions("test_power_state"))
    suite.addTest(TestFunctions("test_power_on"))
    suite.addTest(TestFunctions("test_picture_hdr_modes"))
    suite.addTest(TestFunctions("test_menu_buttons"))
    suite.addTest(TestFunctions("test_power_off"))

    return suite

if __name__ == '__main__':
    runner = unittest.TextTestRunner(failfast=True)
    runner.run(suite())