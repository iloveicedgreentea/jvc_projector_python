"""
All the enums for commands
"""
from enum import Enum


# pylint: disable=missing-class-docstring invalid-name
class Header(Enum):
    ack = b"\x06"
    pj_unit = b"\x89\x01"
    operation = b"!"
    reference = b"?"
    response = b"@"


class Footer(Enum):
    close = b"\x0a"


class ACKs(Enum):
    # PW
    power_ack = b"PW"
    input_ack = b"IP"
    menu_ack = b"RC"
    picture_ack = b"PM"
    lens_ack = b"IN"
    greeting = b"PJ_OK"
    pj_ack = b"PJACK"
    pj_req = b"PJREQ"


class InputModes(Enum):
    """
    HMDMI inputs 1 and 2
    """

    hdmi1 = b"6"
    hdmi2 = b"7"


class PowerModes(Enum):
    """
    Powermodes on/off: 1/0
    """

    off = b"0"
    on = b"1"


class PowerStates(Enum):
    # off
    standby = b"0"
    # aka lamp_on, PJ fully on
    on = b"1"
    cooling = b"2"
    # warming up
    reserved = b"3"
    # error state
    emergency = b"4"


class PictureModes(Enum):
    film = b"00"
    cinema = b"01"
    natural = b"03"
    hdr = b"04"
    # unsupported
    THX = b"06"
    frame_adapt_hdr = b"0B"
    user1 = b"0C"
    user2 = b"0D"
    user3 = b"0E"
    user4 = b"0F"
    user5 = b"10"
    user6 = b"11"
    hlg = b"14"
    hdr_plus = b"15"
    pana_pq = b"16"


class InstallationModes(Enum):
    mode1 = b"0"
    mode2 = b"1"
    mode3 = b"2"
    mode4 = b"3"
    mode5 = b"4"
    mode6 = b"5"
    mode7 = b"6"
    mode8 = b"7"
    mode9 = b"8"
    mode10 = b"9"


class LowLatencyModes(Enum):
    """
    Low latency requires certain options turned off first
    It is not a function. Will not work without disabling
    CMD, dynamic ctrl, others
    Use the low latency provided function instead
    """

    off = b"0"
    on = b"1"


class MotionEnhanceModes(Enum):

    off = b"0"
    low = b"1"
    high = b"2"


class GraphicModeModes(Enum):

    standard = b"0"
    hires1 = b"1"
    hires2 = b"2"


class MaskModes(Enum):
    on = b"1"
    off = b"2"
    # Custom1-3 does not seem to be in the official docs
    # custom2 = b"1"
    # custom3 = b"3"


class LaserPowerModes(Enum):
    """
    hi/med/low for NZ. Others are high/low
    """

    low = b"0"
    med = b"2"
    high = b"1"


class MenuModes(Enum):
    """
    Menu buttons. RC73
    Ack: \x06\x89\x01 + RC + \x0a
    """

    menu = b"2E"
    up = b"01"
    down = b"02"
    back = b"03"
    left = b"36"
    right = b"34"
    ok = b"2F"


class LaserDimModes(Enum):
    off = b"0"
    auto1 = b"1"
    auto2 = b"2"


class EnhanceModes(Enum):
    """
    JVC numeric values are the byte values of two complemented hex
    """

    zero = b"0000"
    one = b"0001"
    two = b"0002"
    three = b"0003"
    four = b"0004"
    five = b"0005"
    six = b"0006"
    seven = b"0007"
    eight = b"0008"
    nine = b"0009"
    ten = b"000A"


class ApertureModes(Enum):
    off = b"0"
    auto1 = b"1"
    auto2 = b"2"


class AnamorphicModes(Enum):
    off = b"0"
    a = b"1"
    b = b"2"
    c = b"3"


class EshiftModes(Enum):
    off = b"0"
    on = b"1"


# TODO: add check for model and modify commands for it
# command -> \x3F\x89\x01\x4D\x44\x0A
# ack -> \x06\x89\x01\x4D\x44\x0A
# response -> \x40\x89\x01\x4D\x44(the model code)\x0A


class Commands(Enum):
    # these use ! unless otherwise indicated
    # power commands
    power = b"PW", PowerModes, ACKs.power_ack

    # lens memory /installation mode commands
    installation_mode = b"INML", InstallationModes, ACKs.lens_ack

    # input commands
    input = b"IP", InputModes, ACKs.input_ack

    # status commands - Reference: ?
    # These should not be used directly
    power_status = b"PW"
    current_output = b"IP"
    info = b"RC7374"

    # picture mode commands
    picture_mode = b"PMPM", PictureModes, ACKs.picture_ack

    # low latency enable/disable
    low_latency = b"PMLL", LowLatencyModes, ACKs.picture_ack
    # enhance
    enhance = b"PMEN", EnhanceModes, ACKs.picture_ack
    # motion enhance
    motion_enhance = b"PMME", MotionEnhanceModes, ACKs.picture_ack
    # graphic mode
    graphic_mode = b"PMGM", GraphicModeModes, ACKs.picture_ack

    # mask commands
    mask = b"ISMA", MaskModes

    # laser power commands
    laser_power = b"PMLP", LaserPowerModes, ACKs.picture_ack

    # menu controls
    menu = b"RC73", MenuModes, ACKs.menu_ack

    # NZ Series Laser Dimming commands
    laser_dim = b"PMDC", LaserDimModes, ACKs.picture_ack

    # Lens Aperture commands
    aperture = b"PMDI", ApertureModes, ACKs.picture_ack

    # Anamorphic commands
    # I don't use this, untested
    anamorphic = b"INVS", AnamorphicModes, ACKs.lens_ack

    # e-shift
    eshift = b"PMUS", EshiftModes, ACKs.picture_ack
