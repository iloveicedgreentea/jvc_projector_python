"""
Note laser dimming mode1|2 is currently really broken. It will destroy your contrast and highlights in HDR
e-shift can also cause artifacts so I am disabling that also
"""

# user1
hdr_film = [
    "eshift,off",
    "picture_mode, frame_adapt_hdr",
    "laser_dim, auto3",
    "low_latency, off",
    "enhance, six",
    "motion_enhance, high",
    "graphic_mode, hires1",
]
# user2
hdr_game = [
    "eshift,off",
    "picture_mode, hdr",
    "laser_dim, off",
    "low_latency, on",
    "enhance, six",
    "motion_enhance, off",
    "graphic_mode, hires1",
]
# user1
sdr_film = [
    "eshift,off",
    "low_latency, off",
    "laser_dim, auto3",
    "enhance, six",
    "motion_enhance, high",
    "graphic_mode, hires1",
]
# user2
sdr_game = [
    "eshift,off",
    "laser_dim, off",
    "low_latency, on",
    "enhance, six",
    "motion_enhance, off",
    "graphic_mode, hires1",
]
