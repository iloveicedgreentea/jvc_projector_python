from enum import Enum


class Header(Enum):
    ack = b"\x06"
    pj_unit = b"\x89\x01"
    operation = b"!"
    reference = b"?"
    response = b"@"


class Footer(Enum):
    close = b"\x0a"


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


class MemoryModes(Enum):
    memory1 = b"0"
    memory2 = b"1"
    memory3 = b"2"
    memory4 = b"3"
    memory5 = b"4"

class LowLatencyModes(Enum):
    """
    Low latency requires certain options turned off first
    It is not a function. Will not work without disabling
    CMD, dynamic ctrl, others
    Use the low latency provided function instead
    """

    off = b"0"
    on = b"1"


class MaskModes(Enum):
    on = b"1"
    off = b"2"
    # Custom1-3 does not seem to be in the official docs
    # custom2 = b"1"
    # custom3 = b"3"


class LampModes(Enum):
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


class LaserModes(Enum):
    off = b"0"
    auto1 = b"1"
    auto2 = b"2"


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


class ACKs(Enum):
    # PW
    power_ack = b"PW"
    input_ack = b"IP"
    menu_ack = b"RC"
    greeting = b"PJ_OK"
    pj_ack = b"PJACK"
    pj_req = b"PJREQ"


# TODO: add check for model and modify commands for it
# command -> \x3F\x89\x01\x4D\x44\x0A
# ack -> \x06\x89\x01\x4D\x44\x0A
# response -> \x40\x89\x01\x4D\x44(the model code)\x0A


class Commands(Enum):
    # these use ! unless otherwise indicated
    # power commands
    power = b"PW", PowerModes

    # lens memory commands
    memory = b"INML", MemoryModes

    # input commands
    input = b"IP", InputModes

    # status commands - Reference: ?
    # These should not be used directly
    power_status = b"PW"
    current_output = b"IP"
    info = b"RC7374"

    # picture mode commands
    picture_mode = b"PMPM", PictureModes

    # low latency enable/disable
    low_latency = b"PMLL", LowLatencyModes

    # mask commands
    mask = b"ISMA", MaskModes

    # laser power commands
    laser_power = b"PMLP"

    # menu controls
    menu = b"RC73", MenuModes

    # NZ Series Laser Dimming commands
    laser_dim = b"PMDC", LaserModes

    # Lens Aperture commands
    aperture = b"PMDI", ApertureModes

    # Anamorphic commands
    # I don't use this, untested
    anamorphic = b"INVS", AnamorphicModes

    # e-shift
    eshift = b"PMUS", EshiftModes