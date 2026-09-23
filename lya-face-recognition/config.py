"""Central configuration for the LYA face-recognition service.

Everything tunable lives here. Nothing in this project downloads anything: the
only model used is InsightFace ``buffalo_l``, which must already be on this
machine. ``models_available()`` verifies that locally, and the engine refuses to
start rather than reaching out to the network.

Tune without editing code by setting the ``FACE_*`` environment variables.
"""
from __future__ import annotations

import os

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.abspath(__file__))          # lya/lya-face-recognition
PRIVATE_DIR = os.path.join(ROOT, "private")                # git-ignored, owner only
TEMPLATE_STORE = os.path.join(PRIVATE_DIR, "face_templates.lya")
DATASET_DIR = os.path.join(ROOT, "dataset")
MODEL_DIR = os.path.join(ROOT, "models")
KEY_PATH = os.path.join(PRIVATE_DIR, "face.key")

# InsightFace keeps its model zoo in the user profile.
INSIGHTFACE_HOME = os.environ.get(
    "FACE_INSIGHTFACE_HOME", os.path.join(os.path.expanduser("~"), ".insightface")
)
MODEL_PACK = os.environ.get("FACE_MODEL_PACK", "buffalo_l")

# --------------------------------------------------------------------------
# Camera
# --------------------------------------------------------------------------
CAMERA_INDEX = int(os.environ.get("FACE_CAMERA_INDEX", "0") or 0)
# 640x480 on purpose: the laptop camera is weak, ArcFace only needs 112x112
# per face, and a small frame keeps the motion trigger and streaming cheap.
FRAME_WIDTH = int(os.environ.get("FACE_FRAME_WIDTH", "640"))
FRAME_HEIGHT = int(os.environ.get("FACE_FRAME_HEIGHT", "480"))
# Frames dropped after opening so auto-exposure and white balance settle.
CAMERA_WARMUP = int(os.environ.get("FACE_CAMERA_WARMUP", "4"))

# --------------------------------------------------------------------------
# Idle cost control (the "runs 24h without pressure" requirement)
# --------------------------------------------------------------------------
# Motion is measured on a 96x96 grayscale thumbnail -> microseconds per frame.
MOTION_DOWNSCALE = 96
# Compared against a frame from about a second ago, NOT the previous frame.
# Measured reason: on this laptop's camera, consecutive frames differ by 1.5-14.7
# (median ~4.9) purely from auto-exposure drift, so a consecutive-frame test
# flagged ~35% of an empty-room frames as motion. A slow reference makes that
# drift cancel out while a person still stands out.
MOTION_REFERENCE_SECONDS = float(os.environ.get("FACE_MOTION_REFERENCE_SECONDS", "1.0"))
MOTION_REFERENCE_DELTA = float(os.environ.get("FACE_MOTION_REFERENCE_DELTA", "12.0"))
# Kept for the simple helper and as the "strong" instantaneous level.
MOTION_THRESHOLD = float(os.environ.get("FACE_MOTION_THRESHOLD", "4.0"))
MOTION_PIXEL_RATIO = float(os.environ.get("FACE_MOTION_RATIO", "0.015"))
# A change this large vs the reference is a person/light: accepted at once.
MOTION_STRONG_DELTA = float(os.environ.get("FACE_MOTION_STRONG_DELTA", "20.0"))
# Sustained frames required within the window before motion is believed.
MOTION_SUSTAIN = int(os.environ.get("FACE_MOTION_SUSTAIN", "2"))
MOTION_SUSTAIN_WINDOW = int(os.environ.get("FACE_MOTION_WINDOW", "4"))
# Waiting for a face runs the detector only, never the embedding network.
DETECT_INTERVAL = float(os.environ.get("FACE_DETECT_INTERVAL", "0.20"))
# Detector input used by the cheap watch path. Lower = cheaper preselect but
# each *match* still uses the full 640 input, so accuracy is unaffected.
WATCH_DET_SIZE = int(os.environ.get("FACE_WATCH_DET_SIZE", "320"))
# Nobody in frame for this many watch iterations -> release the camera entirely.
EMPTY_LIMIT = int(os.environ.get("FACE_EMPTY_LIMIT", "12"))
# Hard ceiling: the watch loop never keeps the device open longer than this
# without a recognition result. Forces the "wake, work, sleep" lifecycle.
WATCH_MAX_OPEN_SECONDS = float(os.environ.get("FACE_WATCH_MAX_OPEN", "45"))
# While the room is empty the loop only samples this often. When a face exists
# but has not been verified yet it samples DETECT_INTERVAL.
WATCH_IDLE_INTERVAL = float(os.environ.get("FACE_WATCH_IDLE_INTERVAL", "1.5"))

# --------------------------------------------------------------------------
# Presence session (the "Hey LYA" door)
# --------------------------------------------------------------------------
SESSION_TTL = float(os.environ.get("FACE_SESSION_TTL", "120"))
# Copying a "still" (printed photo) is a fast-fail state: after this many
# contradictory liveness results the session is dropped hard.
LIVENESS_FAIL_LIMIT = int(os.environ.get("FACE_LIVENESS_FAIL_LIMIT", "3"))

# --------------------------------------------------------------------------
# Recognition
# --------------------------------------------------------------------------
# ArcFace cosine similarity on normed embeddings: same person 0.6-0.8,
# strangers below ~0.3.
OWNER_THRESHOLD = float(os.environ.get("FACE_OWNER_THRESHOLD", "0.50"))
KNOWN_THRESHOLD = float(os.environ.get("FACE_KNOWN_THRESHOLD", "0.42"))
# If the runner-up person is within this margin the result is AMBIGUOUS and
# access is refused. This is what stops one enrolled face from matching a
# similar-looking second person.
MARGIN_MIN = float(os.environ.get("FACE_MARGIN_MIN", "0.06"))
DETECT_SCORE_MIN = float(os.environ.get("FACE_DETECT_SCORE_MIN", "0.60"))
# Face width as a fraction of frame width. Below this, quality is reported low.
FACE_MIN_RATIO = float(os.environ.get("FACE_MIN_RATIO", "0.09"))
FACE_GOOD_RATIO = float(os.environ.get("FACE_GOOD_RATIO", "0.22"))
# Frame voting: among the last CONFIRM_WINDOW judgements, at least
# CONFIRM_VOTES must agree before an identity is accepted.
CONFIRM_WINDOW = int(os.environ.get("FACE_CONFIRM_WINDOW", "5"))
CONFIRM_VOTES = int(os.environ.get("FACE_CONFIRM_VOTES", "3"))
# Hard timeout for one verification burst.
VERIFY_TIMEOUT = float(os.environ.get("FACE_VERIFY_TIMEOUT", "10"))
# Blur guard: lower Laplacian variance = blurrier. Frames below this are
# skipped for matching (they are the usual cause of false accepts).
BLUR_MIN = float(os.environ.get("FACE_BLUR_MIN", "22.0"))

# --------------------------------------------------------------------------
# Enrollment quality gates
# --------------------------------------------------------------------------
ENROLL_QUALITY_MIN = float(os.environ.get("FACE_ENROLL_QUALITY_MIN", "0.45"))
# Samples wanted per direction. This is the wizard's target.
ENROLL_TARGET_PER_BUCKET = int(os.environ.get("FACE_ENROLL_PER_BUCKET", "4"))
# Samples required per direction before enrollment is called *complete*.
# Deliberately lower than the target: the wizard aims high, but a direction is
# considered usable once it has this many, so a slightly awkward angle does not
# block enrollment forever on a weak camera.
POSE_MIN_PER_BUCKET = int(os.environ.get("FACE_POSE_MIN_PER_BUCKET", "2"))
ENROLL_MAX_PER_PERSON = int(os.environ.get("FACE_ENROLL_MAX", "40"))
# Yaw buckets. Covering these is what makes recognition work from every
# direction instead of only dead-centre (the owner's main complaint).
POSE_BUCKETS = (
    ("left", -90.0, -22.0),
    ("left_slight", -22.0, -9.0),
    ("front", -9.0, 9.0),
    ("right_slight", 9.0, 22.0),
    ("right", 22.0, 90.0),
)
POSE_LABELS = tuple(name for name, _, _ in POSE_BUCKETS)

# --------------------------------------------------------------------------
# Liveness / anti-spoof
# --------------------------------------------------------------------------
PASSIVE_ENABLED = os.environ.get("FACE_PASSIVE_LIVENESS", "1") != "0"
PASSIVE_THRESHOLD = float(os.environ.get("FACE_PASSIVE_THRESHOLD", "0.55"))
# Active challenge is mandatory for secure actions; it needs no model at all.
ACTIVE_ENABLED = os.environ.get("FACE_ACTIVE_LIVENESS", "1") != "0"
CHALLENGE_TIMEOUT = float(os.environ.get("FACE_CHALLENGE_TIMEOUT", "9"))
# Blink = eye-openness drops by this fraction of the person's own baseline.
BLINK_DROP_RATIO = float(os.environ.get("FACE_BLINK_DROP", "0.20"))
# Head turn required, in degrees, relative to the pose at challenge start.
HEAD_TURN_YAW = float(os.environ.get("FACE_HEAD_TURN_YAW", "13.0"))
# How many distinct actions must be completed in one challenge.
CHALLENGE_ACTIONS = int(os.environ.get("FACE_CHALLENGE_ACTIONS", "2"))

# --------------------------------------------------------------------------
# Scene understanding ("do you see a pen on my desk?")
# --------------------------------------------------------------------------
SCENE_MAX_SIDE = int(os.environ.get("FACE_SCENE_MAX_SIDE", "896"))
SCENE_JPEG_QUALITY = int(os.environ.get("FACE_SCENE_JPEG_QUALITY", "70"))
SCENE_HTTP_TIMEOUT = float(os.environ.get("FACE_SCENE_TIMEOUT", "30"))
SCENE_MAX_FRAMES = int(os.environ.get("FACE_SCENE_MAX_FRAMES", "3"))
# Live-view analysis cadence. Measured: one full read costs ~0.6 s while the
# camera delivers ~31 fps, so analysing every frame would make the view lag.
STREAM_ANALYSIS_INTERVAL = float(os.environ.get("FACE_STREAM_ANALYSIS", "0.35"))
# Upper bound on how many frames per second the live view will display.
# Measured need: without a cap the viewer spun ~950,000 iterations/second on the
# same cached frame, pinning a CPU core and making the picture laggy. 30 fps is
# smooth to the eye and leaves the rest of the laptop alone.
STREAM_MAX_FPS = int(os.environ.get("FACE_STREAM_MAX_FPS", "30"))

# --------------------------------------------------------------------------
# Camera modes
# --------------------------------------------------------------------------
MODE_OFF = "off"          # device released, zero cost
MODE_WATCH = "watch"      # cheap presence watch
MODE_VERIFY = "verify"    # focused verification burst
MODE_SCENE = "scene"      # one or more frames for the vision model
MODE_STREAM = "stream"    # user is explicitly looking at the camera
MODE_ENROLL = "enroll"    # guided enrollment recording
VALID_MODES = (MODE_OFF, MODE_WATCH, MODE_VERIFY, MODE_SCENE, MODE_STREAM, MODE_ENROLL)

# --------------------------------------------------------------------------
# Privacy defaults
# --------------------------------------------------------------------------
# Storing biometric templates is OFF until the owner explicitly enrolls.
RECOGNITION_ENABLED = os.environ.get("FACE_RECOGNITION_ENABLED", "0") == "1"
# Frame buffers are never written to disk in normal operation.
RETAIN_FRAMES = False
# Local HTTP API (for a future LYA bridge) is loopback-only and off by default.
API_ENABLED = os.environ.get("FACE_API_ENABLED", "0") == "1"
API_HOST = os.environ.get("FACE_API_HOST", "127.0.0.1")
API_PORT = int(os.environ.get("FACE_API_PORT", "8770"))


def models_available() -> tuple[bool, str]:
    """Verify, without touching the network, that the ArcFace pack is on disk.

    ``insightface`` normally downloads ``buffalo_l`` on first use. That silent
    download is exactly the unknown-source risk to avoid, so every required
    file is checked locally before the library is imported.
    """
    import glob

    pack_dir = os.path.join(INSIGHTFACE_HOME, "models", MODEL_PACK)
    if not os.path.isdir(pack_dir):
        return False, f"model pack not found at {pack_dir}"

    names = {os.path.basename(p) for p in glob.glob(os.path.join(pack_dir, "*.onnx"))}
    required = {"det_10g.onnx", "w600k_r50.onnx"}        # detector + ArcFace
    optional = {"2d106det.onnx", "1k3d68.onnx"}          # landmarks / 3-D pose
    missing = required - names
    if missing:
        return False, "missing required model file(s): " + ", ".join(sorted(missing))
    extra = "landmarks available" if (optional & names) else "no landmark model"
    return True, f"{pack_dir} ({len(names)} files, {extra})"
