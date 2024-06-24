import unittest
import os
from dotenv import load_dotenv
from jvc_projector.jvc_projector import JVCProjector, Header
import logging
import time

# Load .env
load_dotenv()

password = os.getenv("JVC_PASSWORD")
host = os.getenv("JVC_HOST")


# Test _construct_command
class TestUnits(unittest.TestCase):
    """
    Test projector
    """

    @classmethod
    def setUpClass(cls):
        # Configure the logger for the test class
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s [Line: %(lineno)d]",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Create a logger instance
        cls.logger = logging.getLogger(__name__)
        cls.logger.propagate = False

        # Ensure the logger prints to the console
        if not cls.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s [Line: %(lineno)d]"
                )
            )
            cls.logger.addHandler(console_handler)

        # JVC will drop connection without throttling in place
        cls.jvc = JVCProjector(
            host=host, connect_timeout=10, password=password, logger=cls.logger
        )

    def test_make_num(self):
        """Test _make_num"""
        num = self.jvc._decimal_to_signed_hex(20)
        self.assertEqual(num, b"0014")

    # test int
    def test_construct_command(self):
        """Test _construct_command"""
        command, _ = self.jvc._construct_command(
            "laser_value, 50", Header.operation.value
        )
        self.assertEqual(command, b"!\x89\x01PMCV00A4\n")

    # test str
    def test_construct_command1(self):
        """Test _construct_command"""
        command, _ = self.jvc._construct_command("power, on", Header.operation.value)
        self.assertEqual(command, b"!\x89\x01PW1\n")

    def test_construct_command2(self):
        """Test _construct_command"""
        command, _ = self.jvc._construct_command("power, off", Header.operation.value)
        self.assertEqual(command, b"!\x89\x01PW0\n")

    # test command not found
    def test_construct_command3(self):
        """Test _construct_command"""
        self.assertRaises(
            NotImplementedError,
            self.jvc._construct_command,
            "power, sideways",
            Header.operation.value,
        )


class TestFunctions(unittest.TestCase):
    """
    Test projector
    """

    @classmethod
    def setUpClass(cls):
        # Configure the logger for the test class
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s [Line: %(lineno)d]",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Create a logger instance
        cls.logger = logging.getLogger(__name__)
        cls.logger.propagate = False

        # Ensure the logger prints to the console
        if not cls.logger.handlers:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s [Line: %(lineno)d]"
                )
            )
            cls.logger.addHandler(console_handler)

        # JVC will drop connection without throttling in place
        cls.jvc = JVCProjector(
            host=host, connect_timeout=10, password=password, logger=cls.logger
        )
        s = cls.jvc.open_connection()
        assert s, "Failed to connect to the projector"

    def test_mock_update(self):
        """Emulates how HA would run updates"""
        state = self.jvc.is_on()
        self.assertEqual(self.jvc.model_family, "NZ7")
        if not state:
            self.jvc.power_on()
            while not self.jvc.is_on():
                time.sleep(1)
        if state:
            print(self.jvc.get_software_version())
            print(self.jvc.get_lamp_time())
            print(self.jvc.get_laser_value())
            print(self.jvc.get_laser_mode())
            time.sleep(1)
            self.jvc.exec_command("laser_value, 10")
            print(self.jvc.get_laser_value())
            time.sleep(1)
            self.jvc.exec_command("laser_value, 0")
            print(self.jvc.get_laser_value())


if __name__ == "__main__":
    unittest.main()
