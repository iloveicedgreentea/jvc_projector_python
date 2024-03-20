import asyncio
import os
import unittest
import logging
import random
import time
from jvc_projector.jvc_projector import JVCProjectorCoordinator, JVCInput
from dataclasses import asdict

os.environ["LOG_LEVEL"] = "DEBUG"

# Note these tests assume projector is on because most commands will time out. Not fail, but time out because JVC can't even bother
# to return a response when a command is not successful

_LOGGER = logging.getLogger(__name__)


class JVCRemote:
    """Implements the interface for JVC Remote in HA."""

    def __init__(
        self,
        entry,
        name: str,
        options: JVCInput,
        jvc_client: JVCProjectorCoordinator = None,
    ) -> None:
        """JVC Init."""
        super().__init__()
        self._name = name
        self._host = options.host
        self.entry = entry

        self.jvc_client = jvc_client
        # attributes
        self._state = False

        # async queue
        self.tasks = []
        # use one queue for all commands
        self.command_queue = asyncio.PriorityQueue()
        self.attribute_queue = asyncio.Queue()

        self.stop_processing_commands = asyncio.Event()

        self._update_interval = None
        self.loop = asyncio.get_event_loop()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        # add the queue handler to the event loop
        # get updates in a set interval
        # open connection
        _LOGGER.debug("adding update task to loop")
        t = self.loop.create_task(self.async_update_state(now=None))
        self.tasks.append(t)

        # handle commands
        _LOGGER.debug("adding queue handler to loop")
        queue_handler = self.loop.create_task(self.handle_queue())
        self.tasks.append(queue_handler)

        # handle updates
        _LOGGER.debug("adding update handler to loop")
        update_handler = self.loop.create_task(self.update_worker())
        self.tasks.append(update_handler)

    async def generate_unique_id(self) -> str:
        timestamp = int(
            time.time() * 1000
        )  # Convert to milliseconds for more granularity
        random_value = random.randint(0, 999)  # Add a random value for uniqueness
        unique_id = f"{timestamp}-{random_value}"
        return unique_id

    async def handle_queue(self):
        """
        Handle items in command queue.
        This is run in an event loop
        """
        try:
            while True:
                # send all commands in queue
                # can be a command or a tuple[function, attribute]
                # first item is the priority
                priority, command = await self.command_queue.get()
                _LOGGER.debug("got queue item %s with priority %s", command, priority)
                # if its a tuple its an attribute update
                if isinstance(command, tuple) and self.jvc_client.connection_open:
                    _, getter, attribute = command
                    _LOGGER.debug(
                        "trying attribute %s with getter %s", attribute, getter
                    )
                    # simulate a command
                    await asyncio.sleep(random.randint(1, 2) - 0.3)
                else:
                    # run the command and set type to operation
                    # HA sends commands like ["power, on"] which is one item
                    _LOGGER.debug("executing command %s", command)
                    await asyncio.sleep(random.randint(1, 2) - 0.3)
                # except Exception as e:
                #     _LOGGER.error("Unexpected error in handle_queue: %s", e)
                try:
                    self.command_queue.task_done()
                except ValueError:
                    pass
                await asyncio.sleep(0.1)
                # if we are stopping and the queue is not empty, clear it
                # this is so it doesnt continuously print the stopped processing commands message
                if (
                    self.stop_processing_commands.is_set()
                    and not self.command_queue.empty()
                ):
                    await self.clear_queue()
                    _LOGGER.debug("Stopped processing commands")
                    # break to the outer loop so it can restart itself if needed
                    break
            # save cpu
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            _LOGGER.debug("handle_queue cancelled")
            return

    async def clear_queue(self):
        """Clear the queue"""

        # clear the queue
        while not self.command_queue.empty():
            self.command_queue.get_nowait()
            self.command_queue.task_done()

        while not self.attribute_queue.empty():
            self.attribute_queue.get_nowait()
            self.attribute_queue.task_done()

    async def update_worker(self):
        """Gets a function and attribute from a queue and adds it to the command interface"""
        while True:
            # this is just an async interface so the other processor doesnt become complicated

            # getter will be a Callable
            try:
                unique_id, getter, attribute = await self.attribute_queue.get()
                # add to the command queue with a single interface
                await self.command_queue.put((1, (unique_id, getter, attribute)))
                _LOGGER.debug("added %s to command queue from attribute q", attribute)
                self.attribute_queue.task_done()
            except asyncio.TimeoutError:
                _LOGGER.debug("Timeout in update_worker")
            except asyncio.CancelledError:
                _LOGGER.debug("update_worker cancelled")
                return
            await asyncio.sleep(0.1)

    async def make_updates(self, attribute_getters: list):
        """Add all the attribute getters to the queue."""
        for getter, name in attribute_getters:
            unique_id = await self.generate_unique_id()
            await self.attribute_queue.put((unique_id, getter, name))

        # get hdr attributes
        await self.attribute_queue.join()
        _LOGGER.debug("make_updates done attributes updated")
        # extra sleep to make sure all the updates are done
        await asyncio.sleep(0.5)

    async def async_update_state(self, now):
        while True:
            try:
                _LOGGER.debug("running update state")
                # mock running every 5 seconds
                await asyncio.sleep(5)
                """Retrieve latest state."""
                if True:
                    # certain commands can only run at certain times
                    # if they fail (i.e grayed out on menu) JVC will simply time out. Bad UX
                    # have to add specific commands in a precise order
                    # common stuff
                    attribute_getters = []
                    _LOGGER.debug("running update sync")
                    _LOGGER.debug(
                        "stop_processing_commands %s, connection_open %s",
                        self.stop_processing_commands.is_set(),
                        self.jvc_client.connection_open,
                    )
                    # get power
                    attribute_getters.append((self.jvc_client.is_on, "power_state"))
                    await self.make_updates(attribute_getters)

                    self._state = self.jvc_client.attributes.power_state
                    _LOGGER.debug("power state is : %s", self._state)

                    if True:
                        _LOGGER.debug("getting signal status and picture mode")
                        # takes a func and an attribute to write result into
                        attribute_getters.extend(
                            [
                                (self.jvc_client.get_source_status, "signal_status"),
                                (self.jvc_client.get_picture_mode, "picture_mode"),
                                (
                                    self.jvc_client.get_software_version,
                                    "software_version",
                                ),
                            ]
                        )
                        # determine how to proceed based on above
                        await self.make_updates(attribute_getters)
                        if True:
                            _LOGGER.debug("getting content type and input mode")
                            attribute_getters.extend(
                                [
                                    (self.jvc_client.get_content_type, "content_type"),
                                    (
                                        self.jvc_client.get_content_type_trans,
                                        "content_type_trans",
                                    ),
                                    (self.jvc_client.get_input_mode, "input_mode"),
                                    (self.jvc_client.get_anamorphic, "anamorphic_mode"),
                                    (self.jvc_client.get_source_display, "resolution"),
                                ]
                            )
                        if "Unsupported" not in self.jvc_client.model_family:
                            attribute_getters.extend(
                                [
                                    (
                                        self.jvc_client.get_install_mode,
                                        "installation_mode",
                                    ),
                                    (self.jvc_client.get_aspect_ratio, "aspect_ratio"),
                                    (self.jvc_client.get_color_mode, "color_mode"),
                                    (self.jvc_client.get_input_level, "input_level"),
                                    (self.jvc_client.get_mask_mode, "mask_mode"),
                                ]
                            )
                        if any(
                            x in self.jvc_client.model_family for x in ["NX9", "NZ"]
                        ):
                            attribute_getters.append(
                                (self.jvc_client.get_eshift_mode, "eshift"),
                            )
                        if "NZ" in self.jvc_client.model_family:
                            attribute_getters.extend(
                                [
                                    (self.jvc_client.get_laser_power, "laser_power"),
                                    (self.jvc_client.get_laser_mode, "laser_mode"),
                                    (self.jvc_client.is_ll_on, "low_latency"),
                                    (self.jvc_client.get_lamp_time, "laser_time"),
                                ]
                            )
                        else:
                            attribute_getters.extend(
                                [
                                    (self.jvc_client.get_lamp_power, "lamp_power"),
                                    (self.jvc_client.get_lamp_time, "lamp_time"),
                                ]
                            )

                        await self.make_updates(attribute_getters)

                        # get laser value if fw is a least 3.0
                        if "NZ" in self.jvc_client.model_family:
                            try:
                                if (
                                    float(self.jvc_client.attributes.software_version)
                                    >= 3.00
                                ):
                                    attribute_getters.extend(
                                        [
                                            (
                                                self.jvc_client.get_laser_value,
                                                "laser_value",
                                            ),
                                        ]
                                    )
                            except ValueError:
                                pass
                        # HDR stuff
                        if any(
                            x in self.jvc_client.attributes.content_type_trans
                            for x in ["hdr", "hlg"]
                        ):
                            if "NZ" in self.jvc_client.model_family:
                                attribute_getters.append(
                                    (
                                        self.jvc_client.get_theater_optimizer_state,
                                        "theater_optimizer",
                                    ),
                                )
                            attribute_getters.extend(
                                [
                                    (
                                        self.jvc_client.get_hdr_processing,
                                        "hdr_processing",
                                    ),
                                    (self.jvc_client.get_hdr_level, "hdr_level"),
                                    (self.jvc_client.get_hdr_data, "hdr_data"),
                                ]
                            )

                        # get all the updates
                        await self.make_updates(attribute_getters)
                        # _LOGGER.debug(asdict(self.jvc_client.attributes))
                        await asyncio.sleep(0.1)
                    else:
                        _LOGGER.debug("PJ is off")
                    # set the model and power
                    self.jvc_client.attributes.model = self.jvc_client.model_family
            except asyncio.CancelledError:
                _LOGGER.debug("update_worker cancelled")
                return

    async def async_send_command(self, command, **kwargs):
        """Send commands to a device."""
        _LOGGER.debug("adding command %s to queue", command)
        # add unique ID to command
        await self.command_queue.put((0, (time.time(), command)))
        _LOGGER.debug("command %s added to queue", command)


class TestCoordinator(unittest.IsolatedAsyncioTestCase):
    """Test running commands"""

    async def asyncSetUp(self):
        # set up connection
        options = JVCInput("192", "1234", 20554, 3)
        coord = JVCProjectorCoordinator(options=options)
        self.c = JVCRemote(None, "test", options, coord)
        # add the tasks to the loop
        await self.c.async_added_to_hass()

    async def testCmd(self):
        """Test command"""
        for _ in range(100):
            await self.c.async_send_command(["menu", "on"])
            await asyncio.sleep(0.5)

    async def asyncTearDown(self):
        """clean up connection between tests otherwise error"""
        pass


if __name__ == "__main__":
    unittest.main()
