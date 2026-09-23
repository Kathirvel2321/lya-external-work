"""Camera aiming check — "is my face actually in the picture?"

Written because of a real support case: the camera opened, returned perfectly
good frames (correct brightness, sharp, full detail) and yet the detector found
no face. The reason was not software at all - the camera was physically aimed at
the ceiling, so there was genuinely no face in the frame.

This command answers the only question that matters first:

    Can the camera see your face at all?

It reports, in order:

1. Every camera device Windows exposes (usually just one).
2. Whether the frame is a real image or a black/shuttered one.
3. Whether a face is detected *right now*, at both detector sizes.
4. A saved JPEG so a human can look at what the camera actually sees.

The saved frame is the important part: numbers can say "no face", but only your
eyes can tell you *why* (ceiling, closed shutter, wrong desk position).
"""
from __future__ import annotations

import os
import time

import numpy as np

import auth_wall
import camera_control
import config


def device_list() -> list[str]:
    """Names of camera-class devices Windows reports.

    Best effort only. Both the PnP query and the WMI fallback can be refused
    depending on how the process was launched, and a missing device list must
    never stop the checks that actually matter (is a face visible right now).
    """
    commands = [
        ["powershell", "-NoProfile", "-Command",
         "Get-PnpDevice -Class Camera,Image -ErrorAction SilentlyContinue | "
         "Select-Object -ExpandProperty FriendlyName"],
        ["powershell", "-NoProfile", "-Command",
         "Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | "
         "Where-Object { $_.PNPClass -eq 'Camera' } | "
         "Select-Object -ExpandProperty Name"],
    ]
    for command in commands:
        try:
            import subprocess

            result = subprocess.run(command, capture_output=True, text=True,
                                    timeout=25)
            names = [line.strip() for line in result.stdout.splitlines()
                     if line.strip()]
            if names:
                return names
        except Exception:
            continue
    return []


def probe(save_path: str | None = None, samples: int = 8) -> dict:
    """Open camera 0, take real frames, and report whether a face is visible."""
    report: dict = {"ok": False, "checks": [], "advice": []}

    def add(label: str, value, good: bool | None = None):
        report["checks"].append({"label": label, "value": value, "good": good})

    devices = device_list()
    if devices:
        add("camera devices Windows reports", devices, True)
    else:
        # Not fatal: the device list is cosmetic. The real question is whether
        # the camera can open and see a face, which the checks below answer.
        add("camera devices Windows reports",
            "not queryable from here (harmless)", None)

    cam = camera_control.camera()
    if not cam.open():
        add("camera open", cam.last_error or "failed", False)
        report["advice"].append(
            "The camera could not be opened. Close any other app using it "
            "(Teams, Zoom, Camera app, browser tab) and try again.")
        return report
    add("camera open", f"index {cam.index}", True)

    try:
        cam.set_streaming(True)
        time.sleep(0.4)

        frames = []
        for _ in range(max(1, samples)):
            frame = cam.read()
            if frame is not None:
                frames.append(frame)
            time.sleep(0.08)
        if not frames:
            add("frames captured", 0, False)
            report["advice"].append("The camera opened but produced no frames.")
            return report

        frame = frames[-1]
        add("frames captured", len(frames), True)
        add("resolution", f"{frame.bgr.shape[1]}x{frame.bgr.shape[0]}", True)

        gray = frame.gray
        brightness = float(np.mean(gray))
        spread = float(np.std(gray))
        sharpness = float(camera_control.blur_score(gray))

        add("brightness", round(brightness, 1), 40 < brightness < 230)
        add("image detail (std)", round(spread, 1), spread > 12)
        add("sharpness", round(sharpness, 1), sharpness > config.BLUR_MIN)

        if brightness < 35:
            report["advice"].append(
                "The frame is almost black. A closed privacy shutter or a "
                "covered lens looks exactly like this. Find the shutter on the "
                "top bezel (or the vendor's camera key) and open it.")
        elif spread < 8:
            report["advice"].append(
                "The frame has almost no detail - the lens is likely blocked.")
        elif sharpness < config.BLUR_MIN:
            report["advice"].append(
                "The image is very soft/fuzzy. If a privacy shutter is partly "
                "closed it produces exactly this washed-out look.")

        # Region balance: a steeply angled camera shows very uneven lighting.
        h, w = gray.shape
        corners = {
            "top-left": float(gray[0:60, 0:60].mean()),
            "top-right": float(gray[0:60, w - 60:w].mean()),
            "bottom-left": float(gray[h - 60:h, 0:60].mean()),
            "bottom-right": float(gray[h - 60:h, w - 60:w].mean()),
        }
        spread_corners = max(corners.values()) - min(corners.values())
        add("corner brightness spread", round(spread_corners, 1),
            spread_corners < 90)
        if spread_corners >= 90:
            report["advice"].append(
                "The lighting across the frame is very uneven, which is typical "
                "when the camera is angled up at a bright ceiling. Tilt the "
                "screen so it faces you.")

        # Face detection at both sizes. This is the decisive check.
        engine = auth_wall.get_engine()
        found_large = 0
        found_watch = 0
        try:
            boxes, _ = engine.det_model.detect(frame.bgr, input_size=(640, 640))
            found_large = 0 if boxes is None else len(boxes)
        except Exception:
            pass
        try:
            found_watch = len(auth_wall.detect_only(frame.bgr))
        except Exception:
            pass

        add("faces detected (full size)", found_large, found_large > 0)
        add("faces detected (watch size)", found_watch, found_watch > 0)

        reading = auth_wall.read_face(frame.bgr, frame.index) if found_large \
            else {}
        if reading:
            add("face quality", reading["quality"]["score"], True)
            add("head direction bucket", reading["bucket"], True)
            add("face size (of frame width)", reading["quality"]["size"], True)

        if save_path:
            try:
                import cv2

                cv2.imwrite(save_path, frame.bgr,
                            [int(cv2.IMWRITE_JPEG_QUALITY), 92])
                add("saved sample frame", save_path, True)
            except Exception as exc:
                add("saved sample frame", f"failed: {exc}", False)

        if found_large == 0:
            report["advice"].append(
                "NO FACE IS VISIBLE in the picture. This is not a detection "
                "bug - there is no face in the frame. Open the saved image and "
                "look at it yourself: aim the camera at your face, then run "
                "this check again.")
        else:
            report["advice"].append(
                f"A face is visible ({found_large} detected). Detection is "
                "working, so any remaining failure would be in matching - run "
                "'cli.py templates' to confirm you are enrolled.")

        report["ok"] = found_large > 0
        report["frame"] = frame
        return report
    finally:
        cam.set_streaming(False)
        cam.close()


def print_report(report: dict):
    print("\n=== camera aiming check ===\n")
    for check in report["checks"]:
        mark = {True: "ok  ", False: "!!  ", None: "    "}[check["good"]]
        print(f"  [{mark}] {check['label']:<32} {check['value']}")
    print("\n--- what to do ---")
    if report["advice"]:
        for line in report["advice"]:
            print(f"  * {line}")
    else:
        print("  nothing to fix")
    print()


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    target = os.path.join(here, "_camera_check.jpg")
    print("Opening the camera to see whether a face is actually visible...")
    report = probe(save_path=target)
    print_report(report)
    if not report["ok"]:
        print(f"  Look at the saved image: {target}")
        print("  If you cannot see your own face in it, no software can either.")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
