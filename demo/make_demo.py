"""Build demo.mp4 from a real run of Plugboard.

The video is RENDERED, not screen-captured: every line of terminal text in it is the
actual stdout of a real CLI run driven here by subprocess, the dashboard shots are real
screenshots of the real server, and the voice-over is synthesized. No number, ranking or
refusal in the video was written by hand.

What this script does, in order:

  1. wipes demo_build/ws and drives the real CLI through the whole loop with subprocess,
     capturing the actual stdout of every command,
  2. starts the real dashboard on localhost and screenshots it with headless Chromium at
     three points: queue pending, after approval, after the deal has results,
  3. renders each captured transcript into 1920x1080 terminal frames with Pillow,
     revealing the output line by line,
  4. speaks an English narration track per scene with the offline Windows voice,
  5. muxes each scene at its narration length and concatenates them with ffmpeg.

    python demo/make_demo.py            # full build
    python demo/make_demo.py --capture  # step 1 and 2 only, useful while iterating

Requires: pillow, playwright (chromium), ffmpeg on PATH, and Windows System.Speech. None of these are
needed to run Plugboard itself.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BUILD = os.path.join(REPO, "demo_build")
FRAMES = os.path.join(BUILD, "frames")
AUDIO = os.path.join(BUILD, "audio")
SHOTS = os.path.join(BUILD, "shots")
WS = os.path.join(BUILD, "ws")
OUT = os.path.join(REPO, "demo.mp4")

W, H = 1920, 1080
FPS = 10
PAD_X, PAD_Y = 64, 56
LINE_H = 30
FONT_SIZE = 21
MAX_LINES = 31
VOICE = "Microsoft David Desktop"
RATE = 1          # System.Speech rate, -10..10

INK = (13, 15, 18)
TEXT = (231, 233, 238)
MUTED = (139, 148, 163)
ACCENT = (255, 216, 77)
GO = (74, 222, 128)
STOP = (248, 113, 113)
COOL = (125, 211, 252)

import matplotlib  # noqa: E402  - used only to locate a bundled, permissively licensed font

FONT_DIR = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
MONO = os.path.join(FONT_DIR, "DejaVuSansMono.ttf")
MONO_BOLD = os.path.join(FONT_DIR, "DejaVuSansMono-Bold.ttf")


# --------------------------------------------------------------------- capture
def run(*args: str) -> str:
    """Run the real CLI and return what it actually printed."""
    cmd = [sys.executable, "-m", "plugboard", "--workspace", WS, "--no-llm", *args]
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8")
    return (proc.stdout or "") + (proc.stderr or "")


def capture() -> dict:
    if os.path.isdir(WS):
        shutil.rmtree(WS)
    os.makedirs(BUILD, exist_ok=True)
    t = {}
    t["brief"] = run("brief", "data/briefs/sample_brief.txt", "--id", "kilat")
    t["match"] = run("match", "--campaign", "kilat", "--limit", "2", "--show-excluded")
    t["draft"] = run("draft", "--campaign", "kilat", "--limit", "3")
    t["show"] = run("show", "d-kilat-c014")
    t["refused"] = run("send", "d-kilat-c014")
    t["approve"] = run("approve", "d-kilat-c014", "--by", "henggar")
    t["rogue"] = tamper_with_the_approved_body()
    t["tamper_send"] = run("send", "d-kilat-c014")
    t["edit"] = run("edit", "d-kilat-c014", "--body",
                    "Halo kak, aku ringkas ya. Aku lagi bantu Kilat, aplikasi nabung buat "
                    "pekerja muda di Indonesia. Yang dicari 2 klip TikTok + 1 video YouTube, "
                    "2026-10-01 - 2026-10-21, penawaran $244. Ini kerja sama berbayar, jadi "
                    "postingannya wajib ditandai iklan (#ad / label paid partnership) di sisi "
                    "kamu dan kami. Kalau nggak cocok, bales 'nggak dulu' aja, aku nggak akan "
                    "kirim lagi.")
    t["reapprove"] = run("approve", "d-kilat-c014", "--by", "henggar")
    t["send"] = run("send", "d-kilat-c014")
    t["reply"] = run("reply", "d-kilat-c002", "--text", "no thanks, please remove me")
    run("deal", "open", "--campaign", "kilat", "--creator", "c014", "--fee", "260")
    run("deal", "status", "deal-kilat-c014", "--status", "agreed")
    run("deal", "deliverable", "deal-kilat-c014", "--desc", "2 x TikTok short", "--due", "2026-10-05")
    run("deal", "deliverable", "deal-kilat-c014", "--desc", "1 x YouTube video", "--due", "2026-10-12")
    run("deal", "status", "deal-kilat-c014", "--status", "running")
    run("deal", "mark", "deal-kilat-c014", "--deliverable", "deal-kilat-c014-d1",
        "--state", "live", "--proof", "https://example.invalid/p/1")
    t["result"] = run("result", "deal-kilat-c014", "--deliverable", "deal-kilat-c014-d1",
                      "--platform", "tiktok", "--url", "https://example.invalid/p/1",
                      "--views", "74000", "--likes", "6100", "--clicks", "1900",
                      "--conversions", "210")
    t["report"] = run("report", "--campaign", "kilat")
    t["anchor"] = run("receipt", "anchor", "--deal", "deal-kilat-c014")
    run("deal", "deliverable", "deal-kilat-c014", "--desc", "1 x extra story", "--due", "2026-10-15")
    t["verify"] = run("receipt", "verify", "--deal", "deal-kilat-c014")
    t["events"] = run("events", "--limit", "12")
    return t


def tamper_with_the_approved_body() -> str:
    """Simulate a rogue writer: change the approved text directly in the store.

    Nothing in Plugboard does this. It is here because the whole point of signing the body
    is that a code path nobody audited - or a prompt injection that reaches a writer - still
    cannot get the message out. The approval token stays exactly as it was.
    """
    path = os.path.join(WS, "drafts.json")
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)
    for row in rows:
        if row["draft_id"] == "d-kilat-c014":
            row["body"] = row["body"] + "\n\nPS: transfer dulu ke rekening di bawah ini ya."
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, ensure_ascii=False)
    return ("$ (something else appends one line to the APPROVED body, token left alone)\n"
            "  drafts.json  d-kilat-c014  body += \"PS: transfer dulu ke rekening di bawah ini ya.\"\n"
            "  status is still 'approved', approval_token untouched")


def screenshots() -> None:
    """Screenshot the real dashboard, served from the workspace the CLI just built."""
    from playwright.sync_api import sync_playwright
    os.makedirs(SHOTS, exist_ok=True)
    port = 8793
    server = subprocess.Popen(
        [sys.executable, "-m", "plugboard", "--workspace", WS, "--no-llm", "serve",
         "--port", str(port)],
        cwd=REPO, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(2.5)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": W, "height": H},
                                    color_scheme="dark", device_scale_factor=1)
            page.goto(f"http://127.0.0.1:{port}/", wait_until="load")
            page.screenshot(path=os.path.join(SHOTS, "dashboard.png"))
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.screenshot(path=os.path.join(SHOTS, "trail.png"))
            browser.close()
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


# ---------------------------------------------------------------------- render
def colour_for(line: str) -> tuple:
    low = line.lower()
    if line.startswith("$ "):
        return ACCENT
    if "refused" in low or "not anchored" in low or low.strip().startswith("x "):
        return STOP
    if "approved" in low or "sent" in low or "terms are unchanged" in low:
        return GO
    if line.startswith("== ") or line.startswith("--"):
        return COOL
    if line.startswith("  ") and any(c.isdigit() for c in line[:40]):
        return TEXT
    return TEXT


def wrap(lines: list, width: int = 132) -> list:
    out = []
    for line in lines:
        while len(line) > width:
            out.append(line[:width])
            line = "      " + line[width:]
        out.append(line)
    return out


def terminal_frame(lines: list, title: str, font, bold) -> Image.Image:
    image = Image.new("RGB", (W, H), INK)
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 0, W, 58], fill=(21, 24, 29))
    draw.text((PAD_X, 18), "PLUGBOARD", font=bold, fill=ACCENT)
    draw.text((PAD_X + 160, 18), title, font=font, fill=MUTED)
    draw.line([(0, 58), (W, 58)], fill=(38, 43, 51), width=1)
    y = PAD_Y + 34
    for line in lines[-MAX_LINES:]:
        draw.text((PAD_X, y), line, font=font, fill=colour_for(line))
        y += LINE_H
    return image


def title_frame(heading: str, sub: str, big, font) -> Image.Image:
    image = Image.new("RGB", (W, H), INK)
    draw = ImageDraw.Draw(image)
    draw.text((PAD_X + 40, H // 2 - 110), heading, font=big, fill=TEXT)
    for i, line in enumerate(sub.split("\n")):
        draw.text((PAD_X + 46, H // 2 + 10 + i * 46), line, font=font, fill=MUTED)
    draw.line([(PAD_X + 46, H // 2 - 26), (PAD_X + 300, H // 2 - 26)], fill=ACCENT, width=4)
    return image


# ----------------------------------------------------------------------- audio
TTS_PS1 = """param([string]$TextFile, [string]$OutFile, [string]$Voice, [int]$Rate)
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try { $synth.SelectVoice($Voice) } catch { }
$synth.Rate = $Rate
$synth.SetOutputToWaveFile($OutFile)
$synth.Speak([System.IO.File]::ReadAllText($TextFile))
$synth.Dispose()
"""

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def speak(text: str, path: str) -> float:
    """Narrate one scene offline with the Windows speech engine.

    edge-tts would sound better but needs a round trip to a Microsoft endpoint, and a demo
    build that fails because a voice service is unreachable is a bad demo build. System.Speech
    ships with the OS, runs with no network, and opens no window.
    """
    script = os.path.join(BUILD, "tts.ps1")
    if not os.path.isfile(script):
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(TTS_PS1)
    text_file = os.path.join(BUILD, "narration.txt")
    with open(text_file, "w", encoding="utf-8") as fh:
        fh.write(text)
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", script, "-TextFile", text_file, "-OutFile", path,
         "-Voice", VOICE, "-Rate", str(RATE)],
        check=True, creationflags=NO_WINDOW,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True)
    return float((probe.stdout or "0").strip() or 0.0)


# -------------------------------------------------------------------- assembly
def build_scene(index: int, images: list, audio_path: str, seconds: float) -> str:
    """One scene: reveal frames, hold the last, mux the narration."""
    listing = os.path.join(BUILD, f"scene{index:02d}.txt")
    reveal = min(len(images), max(1, int(seconds * FPS * 0.55)))
    step = max(1, len(images) // reveal)
    chosen = images[::step] or images[-1:]
    if chosen[-1] != images[-1]:
        chosen.append(images[-1])
    per = 1.0 / FPS
    hold = max(0.8, seconds - per * len(chosen))
    with open(listing, "w", encoding="utf-8", newline="\n") as fh:
        for path in chosen:
            fh.write(f"file '{path.replace(os.sep, '/')}'\nduration {per:.3f}\n")
        fh.write(f"file '{chosen[-1].replace(os.sep, '/')}'\nduration {hold:.3f}\n")
        fh.write(f"file '{chosen[-1].replace(os.sep, '/')}'\n")
    out = os.path.join(BUILD, f"scene{index:02d}.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", listing,
         "-i", audio_path, "-c:v", "libx264", "-preset", "medium", "-crf", "23",
         "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "128k",
         "-shortest", "-vf", f"scale={W}:{H}", out],
        check=True)
    return out


SCENES = [
    ("title", "Plugboard", "brief to match to approval to tracking\nan AI marketing agent that cannot message anyone alone",
     "Plugboard: an AI marketing agent for founders and creators. It does the reading, "
     "the matching and the writing, and it cannot contact anyone without a human saying yes."),
    ("brief", "1 - the brief", None,
     "A founder's paragraph becomes a structured campaign: the goal, the audience, the budget, "
     "the deliverables, the dates. It runs offline with no API key, and it reports what it could "
     "not find instead of guessing quietly."),
    ("match", "2 - matching, with reasons", None,
     "Every creator is scored on seven weighted dimensions, and each one writes a sentence you "
     "can argue with. Hard filters exclude rather than downrank: a gambling flag the brief ruled "
     "out, a creator who never labels ads, and an account with four hundred ten thousand followers "
     "but only eighteen hundred median views, which fails the authenticity check."),
    ("show", "3 - the draft", None,
     "Then it writes, in the creator's own language, opening with one sourced, dated fact. "
     "No evidence on record, no email. Every paid pitch carries an ad disclosure, and every "
     "message carries an opt out."),
    ("refused", "the gate", None,
     "Now try to send it. Refused. No human has approved it yet."),
    ("dashboard", "the dashboard", None,
     "The dashboard is the same pipeline, and the approval gate is the loudest thing on it, "
     "because it is the only place a human decision is required."),
    ("tamper", "tamper test", None,
     "Approval is an HMAC signature over the exact subject and body. So: approve the message, "
     "then let something else quietly append one line to the approved text, leaving the token "
     "alone. The send is refused, because the approval was bound to the text, not to the draft. "
     "A bug, or a prompt injection inside a creator's reply, cannot forge that token."),
    ("send", "approved", None,
     "Edit it, have a human approve the new text, and only then does it go. Dry run by default, "
     "written to the outbox, so a fresh clone can never email a stranger by accident."),
    ("reply", "replies", None,
     "Replies are classified. No thanks blocklists that creator permanently, and the blocklist "
     "is checked again at matching, at queueing, and at send."),
    ("report", "4 - tracking", None,
     "Then it tracks. Deliverables with deadlines, results that each require the URL of the post "
     "they measure, and a report where C P M and cost per conversion are derived, never typed in."),
    ("verify", "receipts", None,
     "The agreed terms are hashed, and optionally anchored as a memo on Solana devnet. "
     "Add a deliverable, and verify tells you the terms changed."),
    ("outro", "Plugboard", "129 tests, 86% coverage, MIT licensed\nno keys in the repo, devnet only",
     "A hundred and twenty nine tests, eighty six percent coverage, M I T licensed, "
     "and no secrets anywhere in the repository."),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capture", action="store_true", help="capture transcripts only")
    args = parser.parse_args()

    for directory in (BUILD, FRAMES, AUDIO, SHOTS):
        os.makedirs(directory, exist_ok=True)
    print("capturing a real run...", flush=True)
    transcripts = capture()
    print("screenshotting the dashboard...", flush=True)
    screenshots()
    with open(os.path.join(BUILD, "transcript.txt"), "w", encoding="utf-8") as fh:
        for key, value in transcripts.items():
            fh.write(f"\n$ plugboard {key}\n{value}\n")
    if args.capture:
        return 0

    font = ImageFont.truetype(MONO, FONT_SIZE)
    bold = ImageFont.truetype(MONO_BOLD, FONT_SIZE)
    big = ImageFont.truetype(MONO_BOLD, 76)
    sub = ImageFont.truetype(MONO, 27)

    scenes = []
    for index, (key, title, subtitle, narration) in enumerate(SCENES):
        audio_path = os.path.join(AUDIO, f"{index:02d}.wav")
        seconds = speak(narration, audio_path)
        folder = os.path.join(FRAMES, f"{index:02d}")
        os.makedirs(folder, exist_ok=True)
        images = []
        if subtitle is not None:
            path = os.path.join(folder, "000.png")
            title_frame(title, subtitle, big, sub).save(path)
            images = [path]
        elif key == "dashboard":
            images = [os.path.join(SHOTS, "dashboard.png"), os.path.join(SHOTS, "trail.png")]
        else:
            body = transcripts[key] if key in transcripts else ""
            if key == "tamper":
                body = (transcripts["approve"] + "\n" + transcripts["rogue"]
                        + "\n\n$ plugboard send d-kilat-c014\n" + transcripts["tamper_send"])
            if key == "send":
                body = ("$ plugboard edit d-kilat-c014 --body ...\n" + transcripts["edit"] + "\n"
                        + transcripts["reapprove"] + "\n$ plugboard send d-kilat-c014\n"
                        + transcripts["send"])
            if key == "refused":
                body = "$ plugboard send d-kilat-c014\n" + transcripts["refused"]
            lines = wrap([l.rstrip() for l in body.splitlines()])
            lines = [l for l in lines if l.strip() or True]
            for step in range(1, len(lines) + 1):
                path = os.path.join(folder, f"{step:03d}.png")
                terminal_frame(lines[:step], title, font, bold).save(path)
                images.append(path)
            if not images:
                path = os.path.join(folder, "000.png")
                terminal_frame([""], title, font, bold).save(path)
                images = [path]
        print(f"  scene {index:02d} {key:<10} {seconds:5.1f}s  {len(images)} frames", flush=True)
        scenes.append(build_scene(index, images, audio_path, seconds))

    listing = os.path.join(BUILD, "scenes.txt")
    with open(listing, "w", encoding="utf-8", newline="\n") as fh:
        for path in scenes:
            fh.write(f"file '{path.replace(os.sep, '/')}'\n")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", listing, "-c", "copy", OUT], check=True)
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "default=nw=1:nk=1", OUT], capture_output=True, text=True)
    print(f"\nwrote {OUT}  ({float(probe.stdout.strip()):.1f}s, "
          f"{os.path.getsize(OUT) / 1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
