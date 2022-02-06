# JVC Projector Remote Improved

This fork implements new features, improvements, and optimizations. This was made with NZ models in mind. Almost every function will work with NX models but I do not guarantee operability for them.

This is designed to work with my Home Assistant plugin: (WIP)

## Installation
TODO: pypy

## Quick Start
Set your network password if you have an NZ model first.

```python
jvc = JVCProjector(host="ipaddr", connect_timeout=60, password="password")

# open menu
cmd = jvc.command("menu", "menu")
# press left button
cmd = jvc.command("menu", "left")
# set picture mode to frame adapt HDR
cmd = jvc.command("picture_mode", "frame_adapt_hdr")
# turn on
cmd = jvc.power_on()
```

Check `tests/testSuite.py` for more comprehensive way to use the module.

## Usage
See [quick-start](#quick-start) for importing 

The commands are structured to use simple keywords and options:

```text
Command: low_latency
Option: off
code: jvc.command("low_latency", "off")
```

```text
Command: picture_mode
Option: hdr_plus
code: jvc.command("picture_mode", "hdr_plus")
```

Use `print_commands()` to get all the latest support commands. This is dynamically generated at runtime.

## Useful premade functions
WIP, TBD

### Gaming Mode
// not implemented yet
jvc.gaming_mode() -> will turn on low latency and optimize settings for gaming
* CMD off
* HDR10 picture mode
* Hi-res 1
* Enhance 7
* NR, MNR, etc 0
* Low-latency on
* Motion enhance off

### Low Latency On
// not implemented yet

### HDR optimal mode
// not implemented yet

### SDR optimal mode
// not implemented yet

## Currently Supported Commands
* Power on/off
* Lens Memory 1-5
* Input HDMI 1 or 2
* Power Statuses
* Low Latency Mode on/off
* Menu and arrow buttons (Menu, LRUD, back)
* Masking
* Laser power low/med/high
* Laser Dimming off/auto1/auto2
* E-shift on/off
* Aperture off/auto1/auto2
* Anamorphic modes

## Supported Models
* NZ7/NZ8/NZ9 (Network password is required)
* NX5/NX7/NX9
* Most likely any other D-ILA projector, and possibly older models.

## Development

```shell
# Create venv
python3 -m venv .venv
source .venv/bin/activate
```

```shell
# Edit env
cp .env.template .env
# edit .env with values
```

*Important*
Because this tests a physical device, I have to make assumptions about the state:
* PJ should be off (or on and JVC_TEST_POWER set to false)
* Your input should already have an HDR source playing/paused to test picture modes correctly
* Do not repeatedly turn your PJ on and off. Testing supports flags for power testing.

```shell
# Run tests
source .env
make test
```


Protocol documentation: http://pro.jvc.com/pro/attributes/PRESENT/Manual/External%20Command%20Spec%20for%20D-ILA%20projector_V3.0.pdf

