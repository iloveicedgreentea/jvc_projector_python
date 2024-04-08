import asyncio
import os
import unittest
import logging
import random
import time
from jvc_projector.jvc_projector import JVCProjectorCoordinator, JVCInput
from dataclasses import asdict
import itertools
from typing import Iterable
from jvc_projector.commands import Header

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
        self.host = options.host
        self.entry = entry
        # tie the entity to the config flow
        self._attr_unique_id = "12"

        self.jvc_client = jvc_client
        self.jvc_client.logger = _LOGGER
        # attributes
        self._state = False

        # async queue
        self.tasks = []
        # use one queue for all commands
        self.command_queue = asyncio.PriorityQueue()
        self.attribute_queue = asyncio.Queue()

        self.stop_processing_commands = asyncio.Event()

        self._update_interval = None

        # counter for unique IDs
        self._counter = itertools.count()
        self.loop = asyncio.get_event_loop()
        self.attribute_getters = set()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        # add the queue handler to the event loop
        # get updates in a set interval

        # open connection
        conn = self.loop.create_task(self.open_conn())
        self.tasks.append(conn)

        # handle commands
        queue_handler = self.loop.create_task(self.handle_queue())
        self.tasks.append(queue_handler)

        # handle updates
        update_worker = self.loop.create_task(self.update_worker())
        self.tasks.append(update_worker)

        # handle sending attributes to queue
        update_handler = self.loop.create_task(self.make_updates())
        self.tasks.append(update_handler)
        # handle sending attributes to queue
        s = self.loop.create_task(self.async_update_state(""))
        self.tasks.append(s)

    async def open_conn(self):
        """Open the connection to the projector."""
        _LOGGER.debug("About to open connection with jvc_client: %s", self.jvc_client)
        try:
            _LOGGER.debug("Opening connection to %s", self.host)
            res = await asyncio.wait_for(self.jvc_client.open_connection(), timeout=3)
            if res:
                _LOGGER.debug("Connection to %s opened", self.host)
                return True
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout while trying to connect to %s", self._host)
        except asyncio.CancelledError:
            return
        # intentionally broad
        except TypeError as err:
            # this is benign, just means the PJ is not connected yet
            _LOGGER.debug("open_connection: %s", err)
            return
        except Exception as err:
            await self.reset_everything()
            _LOGGER.error("some error happened with open_connection: %s", err)
        await asyncio.sleep(5)

    async def generate_unique_id(self) -> int:
        """this is used to sort the queue because it contains non-comparable items"""
        return next(self._counter)

    async def wait_until_connected(self, wait_time: float = 0.1) -> bool:
        """Wait until the connection is open."""
        while not self.jvc_client.connection_open:
            await asyncio.sleep(wait_time)
        return True

    async def handle_queue(self):
        """
        Handle items in command queue.
        This is run in an event loop
        """
        while True:
            await self.wait_until_connected(5)
            try:
                _LOGGER.debug(
                    "queue size is %s - attribute size is %s",
                    self.command_queue.qsize(),
                    self.attribute_queue.qsize(),
                )
                # send all commands in queue
                # can be a command or a tuple[function, attribute]
                # first item is the priority
                try:
                    priority, item = await asyncio.wait_for(
                        self.command_queue.get(), timeout=5
                    )
                except asyncio.TimeoutError:
                    _LOGGER.debug("Timeout in command queue")
                    continue
                _LOGGER.debug("got queue item %s with priority %s", item, priority)
                # if its a 3 its an attribute tuple
                if len(item) == 3:
                    # discard the unique ID
                    _, getter, attribute = item
                    _LOGGER.debug(
                        "trying attribute %s with getter %s", attribute, getter
                    )
                    try:
                        value = await asyncio.wait_for(getter(), timeout=3)
                    except asyncio.TimeoutError:
                        _LOGGER.debug("Timeout with item %s", item)
                        try:
                            # if the above command times out, but we wrote to buffer, that means there is unread data in response
                            # this needs to clear the buffer if timeout
                            await self.jvc_client.reset_everything()
                            self.command_queue.task_done()
                        except ValueError:
                            pass
                        continue
                    _LOGGER.debug("got value %s for attribute %s", value, attribute)
                    setattr(self.jvc_client.attributes, attribute, value)
                elif len(item) == 2:
                    # run the item and set type to operation
                    # HA sends commands like ["power, on"] which is one item
                    _, command = item
                    _LOGGER.debug("executing command %s", command)
                    try:
                        await asyncio.wait_for(
                            self.jvc_client.exec_command(
                                command, Header.operation.value
                            ),
                            timeout=5,
                        )
                    except asyncio.TimeoutError:
                        _LOGGER.debug("Timeout with command %s", command)
                        try:
                            self.command_queue.task_done()
                        except ValueError:
                            pass
                        continue
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
            except TypeError as err:
                _LOGGER.debug(
                    "TypeError in handle_queue, moving on: %s -- %s", err, item
                )
                # in this case likely the queue priority is the same, lets just skip it
                self.command_queue.task_done()
                continue
            # catch wrong values
            except ValueError as err:
                _LOGGER.error("ValueError in handle_queue: %s", err)
                # Not sure what causes these but we can at least try to ignore them
                self.command_queue.task_done()
                continue
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.error("Unhandled exception in handle_queue: %s", err)
                await self.reset_everything()
                continue

    async def reset_everything(self) -> None:
        """resets EVERYTHING. Something with home assistant just doesnt play nice here"""

        _LOGGER.debug("RESETTING - clearing everything")

        try:
            self.stop_processing_commands.set()
            await self.clear_queue()
            await self.jvc_client.reset_everything()
        except Exception as err:
            _LOGGER.error("Error reseting: %s", err)
        finally:
            self.stop_processing_commands.clear()

    async def clear_queue(self):
        """Clear the queue"""
        try:
            # clear the queue
            _LOGGER.debug("Clearing command queue")
            while not self.command_queue.empty():
                self.command_queue.get_nowait()
                self.command_queue.task_done()

            _LOGGER.debug("Clearing attr queue")
            while not self.attribute_queue.empty():
                self.attribute_queue.get_nowait()
                self.attribute_queue.task_done()

            # reset the counter
            _LOGGER.debug("resetting counter")
            self._counter = itertools.count()

        except ValueError:
            pass

    async def update_worker(self):
        """Gets a function and attribute from a queue and adds it to the command interface"""
        while True:
            # this is just an async interface so the other processor doesnt become complicated

            # getter will be a Callable
            try:
                # queue backpressure
                if self.command_queue.qsize() > 10:
                    # this allows the queue to process stuff without filling up
                    _LOGGER.debug("Queue is full, waiting to add attributes")
                    await asyncio.sleep(2)
                    continue
                unique_id, getter, attribute = await self.attribute_queue.get()
                # add to the command queue with a single interface
                await self.command_queue.put((1, (unique_id, getter, attribute)))
                try:
                    self.attribute_queue.task_done()
                except ValueError:
                    pass
            except asyncio.TimeoutError:
                _LOGGER.debug("Timeout in update_worker")
            except asyncio.CancelledError:
                _LOGGER.debug("update_worker cancelled")
                return
            await asyncio.sleep(0.1)

    @property
    def is_on(self):
        """Return the last known state of the projector."""
        return self._state

    async def async_turn_on(self, **kwargs):  # pylint: disable=unused-argument
        """Send the power on command."""

        self._state = True
        await self.wait_until_connected()
        try:
            await self.jvc_client.power_on()
            self.stop_processing_commands.clear()
            # save state
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Error turning on projector: %s", err)
            await self.reset_everything()
            self._state = False

    async def async_turn_off(self, **kwargs):  # pylint: disable=unused-argument
        """Send the power off command."""
        await self.wait_until_connected()
        self._state = False

        try:
            await self.jvc_client.power_off()
            self.stop_processing_commands.set()
            await self.clear_queue()
            # save state
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Error turning off projector: %s", err)
            await self.reset_everything()
            self._state = False

    async def make_updates(self):
        """
        Runs as a background task
        Add all the attribute getters to the queue.
        """
        while True:
            # copy it so we can remove items from it
            attrs = self.attribute_getters.copy()
            for getter, name in attrs:
                # you might be thinking why is this here?
                # oh boy let me tell you
                # TLDR priority queues need a unique ID to sort and you need to just dump one in
                # otherwise you get a TypeError that home assistant HIDES from you and you spend a week figuring out
                # why this function deadlocks for no reason, and that HA hides error raises
                # because the underlying items are not sortable
                unique_id = await self.generate_unique_id()
                await self.attribute_queue.put((unique_id, getter, name))

                # remove the added item from the set
                self.attribute_getters.discard((getter, name))

            await asyncio.sleep(0.1)

    async def async_update_state(self, _):
        """
        Retrieve latest state.
        This will push the attributes to the queue and be processed by make_updates
        """
        while True:
            await asyncio.sleep(3)
            if await self.wait_until_connected():
                # certain commands can only run at certain times
                # if they fail (i.e grayed out on menu) JVC will simply time out. Bad UX
                # have to add specific commands in a precise order
                # get power
                self.attribute_getters.add((self.jvc_client.is_on, "power_state"))

                self._state = self.jvc_client.attributes.power_state
                _LOGGER.debug("power state is : %s", self._state)
                self.attribute_getters.add(
                    (self.jvc_client.get_test_command, "picture_mode")
                )
                if self._state:
                    # takes a func and an attribute to write result into
                    self.attribute_getters.update(
                        [
                            (self.jvc_client.get_source_status, "signal_status"),
                            (self.jvc_client.get_picture_mode, "picture_mode"),
                            (self.jvc_client.get_software_version, "software_version"),
                        ]
                    )
                    if self.jvc_client.attributes.signal_status is True:
                        self.attribute_getters.update(
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
                        self.attribute_getters.update(
                            [
                                (self.jvc_client.get_install_mode, "installation_mode"),
                                (self.jvc_client.get_aspect_ratio, "aspect_ratio"),
                                (self.jvc_client.get_color_mode, "color_mode"),
                                (self.jvc_client.get_input_level, "input_level"),
                                (self.jvc_client.get_mask_mode, "mask_mode"),
                            ]
                        )
                    if any(x in self.jvc_client.model_family for x in ["NX9", "NZ"]):
                        self.attribute_getters.add(
                            (self.jvc_client.get_eshift_mode, "eshift"),
                        )
                    if "NZ" in self.jvc_client.model_family:
                        self.attribute_getters.update(
                            [
                                (self.jvc_client.get_laser_power, "laser_power"),
                                (self.jvc_client.get_laser_mode, "laser_mode"),
                                (self.jvc_client.is_ll_on, "low_latency"),
                                (self.jvc_client.get_lamp_time, "laser_time"),
                            ]
                        )
                    else:
                        self.attribute_getters.update(
                            [
                                (self.jvc_client.get_lamp_power, "lamp_power"),
                                (self.jvc_client.get_lamp_time, "lamp_time"),
                            ]
                        )

                    # get laser value if fw is a least 3.0
                    if "NZ" in self.jvc_client.model_family:
                        try:
                            if (
                                float(self.jvc_client.attributes.software_version)
                                >= 3.00
                            ):
                                self.attribute_getters.update(
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
                            self.attribute_getters.add(
                                (
                                    self.jvc_client.get_theater_optimizer_state,
                                    "theater_optimizer",
                                ),
                            )
                        self.attribute_getters.update(
                            [
                                (self.jvc_client.get_hdr_processing, "hdr_processing"),
                                (self.jvc_client.get_hdr_level, "hdr_level"),
                                (self.jvc_client.get_hdr_data, "hdr_data"),
                            ]
                        )

                # set the model and power
                self.jvc_client.attributes.model = self.jvc_client.model_family

    async def async_send_command(self, command: Iterable[str], **kwargs):
        """Send commands to a device."""
        # add counter to preserve cmd order
        unique_id = await self.generate_unique_id()
        await self.command_queue.put((0, (unique_id, command)))
        _LOGGER.debug("command %s added to queue with counter %s", command, unique_id)


class TestCoordinator(unittest.IsolatedAsyncioTestCase):
    """Test running commands"""

    async def asyncSetUp(self):
        # set up connection
        options = JVCInput("192.168.88.23", "123456789", 20554, 3)
        coord = JVCProjectorCoordinator(options=options)
        self.c = JVCRemote(None, "test", options, coord)
        # add the tasks to the loop
        await self.c.async_added_to_hass()

    async def testCmd(self):
        """Test command"""

        if not self.c.jvc_client.is_on:
            await self.c.async_turn_on()
        await asyncio.sleep(30)
        # for _ in range(100):
        #     # await self.c.async_send_command(["menu", "on"])
        #     # print(self.c.is_on)
        #     await asyncio.sleep(0.5)

    async def asyncTearDown(self):
        """clean up connection between tests otherwise error"""
        await self.c.clear_queue()


if __name__ == "__main__":
    unittest.main()
