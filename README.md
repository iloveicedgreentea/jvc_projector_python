# JVC Projector Remote Improved

This implements new features, improvements, and optimizations based on work in https://github.com/bezmi/jvc_projector. This was made with NZ models in mind. Almost every function will work with NX models but I do not guarantee operability for them.

This is designed to work with my Home Assistant plugin: https://github.com/iloveicedgreentea/jvc_homeassistant

## Installation

```
# Assuming you have a venv with >=python3.9
pip install jvc-projector-remote-improved
```

## Quick Start

Set your network password if you have an NZ model first.

```python
jvc = JVCProjector(host="ipaddr", connect_timeout=60, password="password")

# Commands are passed as a single string delimited by a comma
# Everything executes async in the background. Sync interfaces are provided
# open menu
cmd = jvc.exec_command("menu, menu")
# press left button
cmd = jvc.exec_command("menu, left")
# set picture mode to frame adapt HDR
cmd = jvc.exec_command("picture_mode, frame_adapt_hdr")
# turn on
cmd = jvc.power_on()
```

## Usage

See [quick-start](#quick-start) for importing

The commands are structured to use simple keywords and options:

```text
Command: low_latency
Option: off
code: jvc.exec_command("low_latency, off")
```

```text
Command: picture_mode
Option: hdr_plus
code: jvc.exec_command("picture_mode, hdr_plus")
```

You can also run multiple commands in a row by just giving it a list

```python
jvc.exec_command(["picture_mode, hdr_plus", "motion_enhance, off"])
```

Use `print_commands()` to get all the latest support commands. This is dynamically generated at runtime so it is always up to date.

## Currently Supported Commands

- Power on/off
- Lens Memory/Installation Modes
- Input HDMI 1 or 2
- Power and Low Latency Status
- Low Latency Mode on/off
- Menu and arrow buttons (Menu, LRUD, back)
- Masking
- Laser power low/med/high
- Laser Dimming off/auto1/auto2
- E-shift on/off
- Aperture off/auto1/auto2
- Anamorphic modes
- And many others

## Useful Meta functions

These are opinionated presets so you can have a one-click action to set your settings up for the desired task. This is also supported in home assistant as a service.

- async_gaming_mode_hdr()
- async_gaming_mode_sdr()
- async_hdr_picture_mode()
- async_sdr_picture_mode()
- async_is_on()
- async_get_low_latency_state()

## Supported Models

- NZ7/NZ8/NZ9 (Network password is required)
- NX5/NX7/NX9
- Most likely any other D-ILA projector, and possibly older models with ethernet cables.

## Home Assistant

```yaml
# configuration.yaml
remote:
  - platform: jvc_projectors
    name: nz7
    password: password
    host: 192.168.1.2
    scan_interval: 30
```

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

### Adding new commands

All commands are stored in Enums within `commands.py`. Add them using [this guide](http://pro.jvc.com/pro/attributes/PRESENT/manual/2018_ILA-FPJ_Ext_Command_List_v1.2.pdf) as a reference.

### Testing

JVC_TEST_POWER: true/false to test power functions
JVC_TEST_FUNCTIONS: true/false to test various button functions

You can run the test at the local device or run a mock server I made (WIP) to test commands

```shell
# Venv in one window
python mock/mochrie.py
```

```shell
# Run tests in other window
source .env
export JVC_HOST=127.0.0.1
make test
```
