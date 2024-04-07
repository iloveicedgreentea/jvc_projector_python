"""
All the enums for commands
"""

from enum import Enum
from typing import Final

model_map = {
    "B5A1": "NZ9",
    "B5A2": "NZ8",
    "B5A3": "NZ7",
    "A2B1": "NX9",
    "A2B2": "NX7",
    "A2B3": "NX5",
    "B2A1": "NX9",
    "B2A2": "NX7",
    "B2A3": "NX5",
    "B5B1": "NP5",
    "XHR1": "X570R",
    "XHR3": "X770R||X970R",
    "XHP1": "X5000",
    "XHP2": "XC6890",
    "XHP3": "X7000||X9000",
    "XHK1": "X500R",
    "XHK2": "RS4910",
    "XHK3": "X700R||X900R",
}


# pylint: disable=missing-class-docstring invalid-name
class Header(Enum):
    ack = b"\x06"
    pj_unit = b"\x89\x01"
    operation = b"!"
    reference = b"?"
    response = b"@"


class Footer(Enum):
    close = b"\x0A"


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
    install_acks = b"IN"
    hdmi_ack = b"IS"
    info_ack = b"IF"
    model = b"MD"
    source_ack = b"SC"


PJ_OK: Final = ACKs.greeting.value
PJ_ACK: Final = ACKs.pj_ack.value
PJ_REQ: Final = ACKs.pj_req.value


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
    cooling = b"2"
    warming = b"3"
    emergency = b"4"


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
    hdr10 = b"04"
    thx = b"06"  # unsupported
    frame_adapt_hdr = b"0B"
    frame_adapt_hdr1 = b"0B"
    user1 = b"0C"
    user2 = b"0D"
    user3 = b"0E"
    user4 = b"0F"
    user5 = b"10"
    user6 = b"11"
    hlg = b"14"
    hdr_plus = b"15"
    hdr10_plus = b"15"
    pana_pq = b"16"
    filmmaker = b"17"  # requires firmware 2.0
    frame_adapt_hdr2 = b"18"  # requires firmware 2.0
    frame_adapt_hdr3 = b"19"  # requires firmware 2.0


class PictureModes3D(Enum):
    natural = b"1"
    user1 = b"2"
    user2 = b"3"
    user3 = b"4"
    cinema = b"8"
    film = b"9"
    last = b"F"


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
    lens_control = b"30"
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
    auto3 = b"3"  # requires firmware 2.0


class Numeric(Enum):
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
    d = b"4"


class ColorSpaceModes(Enum):
    auto = b"0"
    YCbCr444 = b"1"
    YCbCr422 = b"2"
    RGB = b"3"


class InputLevel(Enum):
    standard = b"0"
    enhanced = b"1"
    superwhite = b"2"
    auto = b"3"


class EshiftModes(Enum):
    off = b"0"
    on = b"1"


class ContentTypes(Enum):
    # Auto Transition Values
    auto = b"0"
    sdr = b"1"
    hdr10_plus = b"2"
    hdr10 = b"3"
    hlg = b"4"


class ContentTypeTrans(Enum):
    # Auto Transition Values
    sdr = b"1"
    hdr10_plus = b"2"
    hdr10 = b"3"
    hlg = b"4"


class HdrProcessing(Enum):
    hdr10_plus = b"0"
    static = b"1"
    frame_by_frame = b"2"
    scene_by_scene = b"3"


class TheaterOptimizer(Enum):
    off = b"0"
    on = b"1"


class LampPowerModes(Enum):
    normal = b"0"
    high = b"1"


class HdrData(Enum):
    sdr = b"0"
    hdr = b"1"
    smpte = b"2"
    hybridlog = b"3"
    hdr10_plus = b"4"
    none = b"F"


class HdrLevel(Enum):
    auto = b"0"
    min2 = b"1"
    min1 = b"2"
    zero = b"3"
    plus1 = b"4"
    plus2 = b"5"


class AspectRatioModes(Enum):
    zoom = b"2"
    auto = b"3"
    native = b"4"


class SourceStatuses(Enum):
    logo = b"\x00"
    no_signal = b"0"
    signal = b"1"


class ThreeD(Enum):
    twoD = b"0"
    auto = b"1"
    sbs = b"3"
    tb = b"4"


class ResolutionModes(Enum):
    r_480p = b"02"
    r_576p = b"03"
    r_720p50 = b"04"
    r_720p60 = b"05"
    r_1080i50 = b"06"
    r_1080i60 = b"07"
    r_1080p24 = b"08"
    r_1080p50 = b"09"
    r_1080p60 = b"0A"
    NoSignal = b"0B"
    r_720p_3D = b"0C"
    r_1080i_3D = b"0D"
    r_1080p_3D = b"0E"
    OutofRange = b"0F"
    r_4K_4096p60 = b"10"
    r_4K_4096p50 = b"11"
    r_4K_4096p30 = b"12"
    r_4K_4096p25 = b"13"
    r_4K_4096p24 = b"14"
    r_4K_3840p60 = b"15"
    r_4K_3840p50 = b"16"
    r_4K_3840p30 = b"17"
    r_4K_3840p25 = b"18"
    r_4K_3840p24 = b"19"
    r_1080p25 = b"1C"
    r_1080p30 = b"1D"
    r_2048x1080p24 = b"1E"
    r_2048x1080p25 = b"1F"
    r_2048x1080p30 = b"20"
    r_2048x1080p50 = b"21"
    r_2048x1080p60 = b"22"
    r_3840x2160p120 = b"23"
    r_4096x2160p120 = b"24"
    VGA_640x480 = b"25"
    SVGA_800x600 = b"26"
    XGA_1024x768 = b"27"
    SXGA_1280x1024 = b"28"
    WXGA_1280x768 = b"29"
    WXGAplus_1440x900 = b"2A"
    WSXGAplus_1680x1050 = b"2B"
    WUXGA_1920x1200 = b"2C"
    WXGA_1280x800 = b"2D"
    FWXGA_1366x768 = b"2E"
    WXGAplus_1600x900 = b"2F"
    UXGA_1600x1200 = b"30"
    QXGA = b"31"
    WOXGA = b"32"
    r_4096x2160_100Hz = b"34"
    r_3840x2160_100Hz = b"35"
    r_1080p100 = b"36"
    r_1080p120 = b"37"
    r_8K_7680x4320p60 = b"38"
    r_8K_7680x4320p50 = b"39"
    r_8K_7680x4320p30 = b"3A"
    r_8K_7680x4320p25 = b"3B"
    r_8K_7680x4320p24 = b"3C"
    WQHD60 = b"3D"
    WOQHD120 = b"3E"
    r_8K_7680x4320p48 = b"3F"


class Commands(Enum):

    # these use ! unless otherwise indicated
    # power commands
    power = b"PW", PowerModes, ACKs.power_ack
    power_status = b"PW", PowerModes, ACKs.power_ack
    # lens memory /installation mode commands
    installation_mode = b"INML", InstallationModes, ACKs.lens_ack

    # input commands
    input_mode = b"IP", InputModes, ACKs.input_ack

    # status commands - Reference: ?
    # These should not be used directly

    current_output = b"IP"
    info = b"RC7374"
    remote = b"RC73"

    # Checking for model code
    # response -> \x40\x89\x01\x4D\x44(the model code)\x0A
    get_model = b"MD", str, ACKs.model

    # software version
    get_software_version = b"IFSV", str, ACKs.info_ack

    # content type
    content_type = b"PMCT", ContentTypes, ACKs.picture_ack
    content_type_trans = b"PMAT", ContentTypeTrans, ACKs.picture_ack

    # hdr processing (like frame by frame)
    hdr_processing = b"PMHP", HdrProcessing, ACKs.picture_ack
    hdr_level = b"PMHL", HdrLevel, ACKs.picture_ack

    # hdr data
    hdr_data = b"IFHR", HdrData, ACKs.info_ack

    # theater optimizer on/off
    theater_optimizer = b"PMNM", TheaterOptimizer, ACKs.picture_ack

    # picture mode commands
    picture_mode = b"PMPM", PictureModes, ACKs.picture_ack

    # Color modes
    color_mode = b"ISHS", ColorSpaceModes, ACKs.hdmi_ack

    # Aspect ratio
    aspect_ratio = b"ISAS", AspectRatioModes, ACKs.hdmi_ack

    # input_level like 0-255
    input_level = b"ISIL", InputLevel, ACKs.hdmi_ack

    # low latency enable/disable
    low_latency = b"PMLL", LowLatencyModes, ACKs.picture_ack
    # enhance
    enhance = b"PMEN", Numeric, ACKs.picture_ack
    # motion enhance
    motion_enhance = b"PMME", MotionEnhanceModes, ACKs.picture_ack
    # graphic mode
    graphic_mode = b"PMGM", GraphicModeModes, ACKs.picture_ack

    # mask commands
    mask = b"ISMA", MaskModes, ACKs.hdmi_ack

    # laser power commands
    laser_power = b"PMLP", LaserPowerModes, ACKs.picture_ack

    # menu controls
    menu = b"RC73", MenuModes, ACKs.menu_ack

    # NZ Series Laser Dimming commands
    laser_mode = b"PMDC", LaserDimModes, ACKs.picture_ack
    # fw 3.0 and up
    laser_value = b"PMCV", int, ACKs.picture_ack

    # Lamp power
    lamp_power = b"PMLP", LampPowerModes, ACKs.picture_ack

    # Lamp time
    lamp_time = b"IFLT", int, ACKs.info_ack

    # Lens Aperture commands
    aperture = b"PMDI", ApertureModes, ACKs.picture_ack

    # Anamorphic commands
    anamorphic = b"INVS", AnamorphicModes, ACKs.lens_ack

    # e-shift
    eshift_mode = b"PMUS", EshiftModes, ACKs.picture_ack

    # source status
    source_status = b"SC", SourceStatuses, ACKs.source_ack
    source_disaply = b"IFIS", ResolutionModes, ACKs.info_ack

    # 3d
    signal_3d = b"IS3D", ThreeD, ACKs.hdmi_ack
    # hdmi phase alignment
    signal_3d_phase = b"IS3P", Numeric, ACKs.hdmi_ack
    # 3d parallax (-8 to 8)
    signal_3d_parallax = b"ISLV", Numeric, ACKs.hdmi_ack
    # 3d crosstalk cancel (-8 to 8)
    signal_3d_crosstalk = b"ISCA", Numeric, ACKs.hdmi_ack
    # 3d pm
    signal_3d_pm = b"ISS3", PictureModes3D, ACKs.hdmi_ack
    # 2d signal
    signal_2d_pm = b"ISS2", PictureModes3D, ACKs.hdmi_ack
