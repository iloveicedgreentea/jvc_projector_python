# JVC Projector Python Library

This implements JVC IP Control in Python specifically for Home Assistant. Otherwise, I would have written this in Go. Almost every function will work with all JVC models but I do not guarantee operability for models that are not NX or NZ.

This is designed to work with my Home Assistant plugin: https://github.com/iloveicedgreentea/jvc_homeassistant

## Installation

```
# Assuming you have a venv with >=python3.11
pip install pyjvc
```

## Quick Start

You must set your network password if you have an NZ model first.

Refer to `tests/test_coordinator.py` examples on how to use this library

Use `print_commands()` to get all the latest support commands. This is dynamically generated at runtime so it is always up to date.

## Supported Commands

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

## Gaming/Film Modes
I recommend setting up picture mode presets for each mode. Low latency toggle annoyingly will not work unless certain things are disabled first. Toggling low latency will not flip these switches so you have to make sure conflicting settings are not active. Do not set low latency directly, just set up picture modes and switch between them.

SDR Gaming: user1||natural, low latency on, etc
HDR Gaming: hdr10, low latency on, etc
SDR Film: natural||user1, low latency off, laser mode 3, motion enhance high
HDR Film: frame adapt HDR, low latency off, laser mode 3, hdr quantization to auto(wide)

Then use the commands to switch between picture modes.

## Supported Models

### Tested
- NZ7/NZ8/NZ9 (Network password is required)
- NX5/NX7/NX9

### User Reported
- All D-ILA projector
- Various older models such as X5000
- Generally anything with an ethernet port should work

## Home Assistant
Designed to work with my Home Assistant plugin.

Refer to [JVC Homeassistant](https://github.com/iloveicedgreentea/jvc_homeassistant)

## Development

```shell
make dev_install
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
        signal_3d
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
ThreeD
        auto
        sbs
        ou
        2d
```

### Adding new commands

All commands are stored in Enums within `commands.py` so simply adding them to that file in the proper Enum will automatically propagate to code. Add them using [this guide](http://pro.jvc.com/pro/attributes/PRESENT/manual/2018_ILA-FPJ_Ext_Command_List_v1.2.pdf) as a reference.

### Testing

Tests are located in `./tests`

```
make test```
