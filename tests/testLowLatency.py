import unittest
import os
from dotenv import load_dotenv
from jvc_projector.jvc_projector import JVCProjector
import logging
import time

# Load .env
load_dotenv()

password = os.getenv("JVC_PASSWORD")
host = os.getenv("JVC_HOST")


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


if __name__ == "__main__":
    unittest.main()
