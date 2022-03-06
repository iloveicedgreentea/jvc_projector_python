"""
Note laser dimming is currently really broken. It will destroy your contrast and highlights in HDR
Until they patch it I am disabling it
e-shift can also cause artifacts so I am disabling that also
Unless you need CMD, its actually best to just leave low latency (unless using frame adapt hdr) on since it creates a sharper image and
processes everything in 4:4:4
"""

# user1
hdr_film = [
    "eshift,off",
    "picture_mode, frame_adapt_hdr",
    "laser_dim, off",
    "low_latency, off",
    "enhance, seven",
    "motion_enhance, low",
    "graphic_mode, hires1",
]
# user2
hdr_game = [
    "eshift,off",
    "picture_mode, hdr",
    "laser_dim, off",
    "low_latency, on",
    "enhance, seven",
    "motion_enhance, off",
    "graphic_mode, hires1",
]
# user1
sdr_film = [
    "laser_dim, off",
    "low_latency, on",
    "enhance, seven",
    "motion_enhance, low",
    "graphic_mode, hires1",
]
# user2
sdr_game = [
    "low_latency, on",
    "laser_dim, off",
    "enhance, seven",
    "motion_enhance, off",
    "graphic_mode, hires1",
]
