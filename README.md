# JVC Projector Remote Improved

This fork implements new features, improvements, and optimizations.

Supported models:
NX5/NX7/NX9
NZ7/NZ8/NZ9 (Network password is required)

Most likely any other D-ILA projector, and possibly older. 

Funcs:
  command: False if command not found, True if command is found (not if its successful)

create venv

```shell
python3 -m venv .venv
source .venv/bin/activate
```

To test
```shell
cp .env.template .env
# edit .env with values
source .env
make test
```

For example, you can send pm_frame_adapt to switch to frame adapt hdr mode with your presets

New docs: http://pro.jvc.com/pro/attributes/PRESENT/Manual/External%20Command%20Spec%20for%20D-ILA%20projector_V3.0.pdf
## Testing
*Important*
Because this tests a physical device, I have to make assumptions about the state:
* PJ should be off (or on and JVC_TEST_POWER set to false)
* Your input should already have an HDR source playing/paused to test picture modes correctly

## Public functions
print_commands(): Returns a list of all supported command names






# Original Readme

This is a simple package to control JVC Projectors over IP. Created to be used with my [Homeassistant](https://www.home-assistant.io/) custom component: [bezmi/hass_custom_components](https://github.com/bezmi/hass_custom_components/tree/master/custom_components/jvcprojector). Works fine as a standalone module.

Currently supports:
* Power on/off
* Lens Memory
* Input (HDMI only)
* Power Status (Standby, Cooling, Emergency, Lamp On, Reserved)
* Low Latency Mode

Raise an issue if you would like any extra commands implemented. Alternatively pull requests are more than welcome and adding new commands is trivial. [See Below.](#adding-new-commands)

# Installation
## PyPi
Install [this package](https://pypi.org/project/jvc-projector-remote/) from PyPi
with:
~~~
pip install jvc_projector_remote
~~~
## From this repo
Install from this repo with:
~~~
pip install -e git+https://github.com/bezmi/jvc_projector.git#egg=jvc-projector-remote
~~~
# Usage
For usage with homeassistant, [see here](https://github.com/bezmi/hass_custom_components).

Here is am example for using this module standalone:
``` python
>>> from jvc_projector import JVCProjector

 # replace with your projector's local IP
>>> host = "192.168.1.12"

# initialise
>>> projector = JVCProjector(host)

# power on, power off
>>> projector.power_on()
# check status once it's on
>>> projector.is_on()
True

>>> projector.power_off()
# check if it's off
>>> projector.is_on()
False

# Send arbitrary command
# possibilities include:
#   - memory1, memory2, memory3, memory4, memory5
#   - hdmi1, hdmi2
#   - add new commands to the Commands class in __init__.py
>>> projector.command("hdmi2")
```

# Testing
I wrote this to interface my projector with homeassistant. The code to
send/receive commands is rough and the error checking could be more robust. It
has been tested on a DLA-X5900, but should work on most of the projectors
that use a similar IP control scheme. Let me know if it works with your
projector and I will add it to the list below.

## Confirmed Models
* DLA-X5900
* NX5

# Bugs
The main issue one might face is receiving ConnectionRefusedError when making a
request too soon after another. On my DLA-X5900, it takes about 600-700 ms
between commands.

# Improvements
- Currently I group all power states into either "on" or "off". I might separate
  these in future.
- ACK for all commands might be useful, but it's reliable enough without it.

# Adding New Commands
### Step 1
[Page 25](https://www.us.jvc.com/projectors/pdf/2018_ILA-FPJ_Ext_Command_List_v1.2.pdf#page=25) of this reference shows that the function is `PMPM`
 for "Picture Mode Switch". The hex representation of these ASCII characters in pythonic format is:
``` python
b"\x50\x4D\x50\x4D"
```
### Step 2
The relevant picture modes are presented in [Table 4-19 on Page 30](https://www.us.jvc.com/projectors/pdf/2018_ILA-FPJ_Ext_Command_List_v1.2.pdf#page=30). Let's take `01` for the "Cinema" preset:
``` python
b"\x30\x31"
```
### Step 3
Finally, the examples on [page 42](https://www.us.jvc.com/projectors/pdf/2018_ILA-FPJ_Ext_Command_List_v1.2.pdf#page=42) show what we need to append to the start and end of the command string. In the end, the final command added to the `Commands` `Enum` in `__init__.py` becomes:
``` python
class Commands(Enum):
    # ...
    # ALL THE OTHER COMMAND STRINGS...
    # ...
 
    pm_cinema = b"\x21\x89\x01\x50\x4D\x50\x4D\x30\x31\x0A"
``` 
### Step 5
Just change the value of step 2 for the remaining input modes you want. You should be able to use it like any of the other commands, with either the `JVCProjector.command()` function in this module or the `remote.send_command` service in Home Assistant using `"pm_cinema"` as the command string.

### Inconsistencies
One of the reasons I held off on this is that the commands from step 2 will be [slightly different](https://support.jvc.com/consumer/support/documents/DILAremoteControlGuide.pdf#page=5) for older projectors. The picture mode is represented by one byte/character. In this case, for the "Cinema" mode, we would use:
```python
b"\x31"
```
Instead of the two byte code in step 2.



