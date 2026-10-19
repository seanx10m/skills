"""Project scenes for /stick-video. Copy into the project dir, edit, run:
    python3 scenes.py --still 1 5 9   # check frames
    python3 scenes.py                 # render all frames
Timing comes from the voice take: P[i] = start of paragraph i, word_at("trillion", after=P[2]) = a spoken word."""
import json, os, sys
sys.path.insert(0, os.path.expanduser("~/.claude/skills/stick-video/scripts"))
from stickkit import *

P = json.load(open("para_starts.json"))
TOTAL = float(os.popen("ffprobe -v error -show_entries format=duration -of csv=p=0 vo_full.m4a").read()) + 0.8

def S_intro(p, t):
    pip(p, 640, 640, 1.25, arms=(A_DOWN_L, A_WAVE_R), mouth="grin", key="p0")
    p.text("OKAY.", 640, 140, 90, BANG, INK, scale=pop(t, 0.2), key="ok")

def S_number(p, t, t0=None):
    t0 = P[1]
    p.text("$4.1 TRILLION", 640, 300, 110, BANG, GREEN, scale=pop(t, word_at("trillion", after=t0) - 0.1), stroke=1.5)
    pip(p, 1100, 700, 0.8, arms=(A_POINT_L, A_HIP_R), pointer=(0, (820, 330)), mouth="smile", key="p1", look=(-1, 0))

def S_source(p, t):
    card(p, "shots/chart.jpg", 640, 340, 760, "Steve Rattner, Sept 2026", scale=pop(t, P[2]), rot=-1.5)

SCENES = [(0, S_intro), (P[1], S_number), (P[2], S_source)]

if __name__ == "__main__":
    run(SCENES, TOTAL)
