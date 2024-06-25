# JVC Projector Python Library

This implements new features, improvements, and optimizations inspired by https://github.com/bezmi/jvc_projector. This was made with NZ models in mind. Almost every function will work with NX models but I do not guarantee operability for them.

This is designed to work with my Home Assistant plugin: https://github.com/iloveicedgreentea/jvc_homeassistant

## Installation

```
# Assuming you have a venv with >=python3.11
pip install pyjvc
```

## Quick Start

Set your network password if you have an NZ model first.

```python
jvc = JVCProjector(host="ipaddr", connect_timeout=10, password="password")

# Commands are passed as a single string delimited by a comma
# open menu
cmd = jvc.exec_command(["menu, menu"])
# press left button
cmd = jvc.exec_command(["menu, left"])
# set picture mode to frame adapt HDR
cmd = jvc.exec_command(["picture_mode, frame_adapt_hdr"])
# turn on
cmd = jvc.power_on()
```

## Usage

See [quick-start](#quick-start) for importing

The commands are structured to use simple command keywords and parameters. This makes it simple to remember commands. All names with spaces will have an underscore instead.

```python
Command: low_latency
Parameter: off
code: jvc.exec_command(["low_latency, off"])
```

```python
Command: picture_mode
Parameter: hdr_plus
code: jvc.exec_command(["picture_mode, hdr_plus"])
```

You can also run multiple commands in a row by just giving it a list of commands

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
## Supported Commands

`$command,$parameter`
example: "anamorphic,off"
example: "anamorphic,d"
example: "laser_mode,auto3"

It also supports using remote codes as ASCII [found here](https://support.jvc.com/consumer/support/documents/DILAremoteControlGuide.pdf) (Code A only)

`jvc.emulate_remote("23")`

```
Currently Supported Commands:
        anamorphic
        aperture
        aspect_ratio
        color_mode
        content_type
        content_type_trans
        enhance
        eshift_mode
        get_model
        get_software_version
        graphic_mode
        hdr_data
        hdr_level
        hdr_processing
        input_level
        input_mode
        installation_mode
        lamp_power
        lamp_time
        laser_mode
        laser_power
        low_latency
        mask
        menu
        motion_enhance
        picture_mode
        power
        remote
        source_status
        theater_optimizer


Currently Supported Parameters:
AnamorphicModes
        off
        a
        b
        c
        d
ApertureModes
        off
        auto1
        auto2
AspectRatioModes
        zoom
        auto
        native
ColorSpaceModes
        auto
        YCbCr444
        YCbCr422
        RGB
ContentTypeTrans
        sdr
        hdr10_plus
        hdr10
        hlg
ContentTypes
        auto
        sdr
        hdr10_plus
        hdr10
        hlg
EnhanceModes
        zero
        one
        two
        three
        four
        five
        six
        seven
        eight
        nine
        ten
EshiftModes
        off
        on
GraphicModeModes
        standard
        hires1
        hires2
HdrData
        sdr
        hdr
        smpte
        hybridlog
        hdr10_plus
        none
HdrLevel
        auto
        min2
        min1
        zero
        plus1
        plus2
HdrProcessing
        hdr10_plus
        static
        frame_by_frame
        scene_by_scene
InputLevel
        standard
        enhanced
        superwhite
        auto
InputModes
        hdmi1
        hdmi2
InstallationModes
        mode1
        mode2
        mode3
        mode4
        mode5
        mode6
        mode7
        mode8
        mode9
        mode10
LampPowerModes
        normal
        high
LaserModes
        off
        auto1
        auto2
        auto3
LaserPowerModes
        low
        med
        high
LowLatencyModes
        off
        on
MaskModes
        on
        off
MenuModes
        menu
        lens_control
        up
        down
        back
        left
        right
        ok
MotionEnhanceModes
        off
        low
        high
PictureModes
        film
        cinema
        natural
        hdr
        thx
        frame_adapt_hdr
        user1
        user2
        user3
        user4
        user5
        user6
        hlg
        hdr_plus
        pana_pq
        filmmaker
        frame_adapt_hdr2
        frame_adapt_hdr3
PowerModes
        off
        on
PowerStates
        standby
        on
        cooling
        reserved
        emergency
SourceStatuses
        logo
        no_signal
        signal
TheaterOptimizer
        off
        on
```
