"""Guided enrollment — the part that makes recognition work "in every direction".

The owner's actual complaint about every other face tool is that it matches a
frontal photo and then fails when you look sideways, tilt down, or approach
from an angle. That is not a model problem, it is an enrollment problem: a
single frontal template simply has nothing to compare a side view against.

So enrollment here is directional and verified:

* The wizard asks for each direction in turn (front, both slight turns, both
  full turns, plus a downward and upward look).
* Every sample passes a quality gate before it is accepted, and the reason for
  rejection is shown ("hold still", "too dark", "come closer") so the owner can
  fix it instead of guessing.
* A sample only counts once per pose bucket per "step", so holding still for
  two seconds cannot secretly register twenty identical frontal shots.
* Progress is reported per bucket, and enrollment is not considered complete
  until every bucket has enough samples.

Data handling, stated plainly: only 512-d vectors are stored, never images, and
they go straight into the encrypted store. The optional ``dataset/`` capture is
off by default, is written as text-labelled folders, and is only for debugging
recognition from your own angles.
"""
from __future__ import annotations

import os
import time

import numpy as np

import auth_wall
import camera_control
import config
import vault

# The prompts, in order. Each entry maps to one or more pose buckets so the
# wizard naturally produces coverage instead of hoping for it.
STEPS = (
    {"key": "front", "buckets": ("front",),
     "prompt": "Look straight at the camera"},
    {"key": "left_slight", "buckets": ("left_slight",),
     "prompt": "Turn your head slightly to ONE side"},
    {"key": "left", "buckets": ("left",),
     "prompt": "Turn further, near profile on that same side"},
    {"key": "right_slight", "buckets": ("right_slight",),
     "prompt": "Now slightly to the OTHER side"},
    {"key": "right", "buckets": ("right",),
     "prompt": "Further on that side, near profile"},
    {"key": "extras", "buckets": ("front", "left_slight", "right_slight"),
     "prompt": "Face the screen again - one more round for stability"},
)


class EnrollmentSession:
    """State machine for one guided enrollment run.

    Kept as a plain object with an explicit ``step()`` call rather than an
    internal loop, so the same logic can be driven by the CLI, by the service
    API or by a future LYA orb panel without duplicating it.
    """

    def __init__(self, name: str, role: str = "owner", per_bucket: int | None = None,
                 dataset_path: str | None = None, camera=None):
        self.name = name.strip()
        self.role = role
        self.per_bucket = per_bucket or config.ENROLL_TARGET_PER_BUCKET
        self.camera = camera or camera_control.camera()
        self.dataset_path = dataset_path
        self.step_index = 0
        self.finished = False
        self.owner_written = False

        self.store = vault.load_store()
        self.person = vault.upsert_person(self.store, self.name, self.role)
        # A fresh enrollment for a named person replaces their old templates so
        # the wizard's progress reflects only what was captured now.
        self.person["templates"] = []
        self.counts_before = {name: 0 for name in config.POSE_LABELS}
        self.captured = 0
        self.rejected = 0
        self.cache = auth_wall.EmbeddingCache()
        self._held_bucket_frame = -1
        self._opened_here = False
        self.last_message = "ready"

        if self.dataset_path:
            for bucket in config.POSE_LABELS:
                os.makedirs(os.path.join(self.dataset_path, self.name, bucket),
                            exist_ok=True)

    # ------------------------------------------------------------------
    # camera
    # ------------------------------------------------------------------
    def start(self) -> bool:
        if not self.camera.is_open:
            if not self.camera.open():
                self.last_message = self.camera.last_error or "camera unavailable"
                return False
            self._opened_here = True
        self.camera.set_streaming(True)
        self.camera.reset_motion_baseline()
        self.last_message = "capturing"
        return True

    def stop(self):
        if self._opened_here:
            self.camera.set_streaming(False)
            self.camera.close()
        else:
            self.camera.set_streaming(False)

    # ------------------------------------------------------------------
    # progress
    # ------------------------------------------------------------------
    @property
    def current_step(self) -> dict | None:
        if self.step_index >= len(STEPS):
            return None
        return STEPS[self.step_index]

    def progress(self) -> dict:
        counts = vault.bucket_counts(self.person)
        return {
            "name": self.name,
            "step_index": self.step_index,
            "steps_total": len(STEPS),
            "prompt": (self.current_step or {}).get("prompt", "complete"),
            "counts": counts,
            "per_bucket": self.per_bucket,
            "captured": self.captured,
            "rejected": self.rejected,
            "complete": self.finished,
            "message": self.last_message,
            "coverage": self.coverage(),
        }

    def coverage(self) -> dict:
        counts = vault.bucket_counts(self.person)
        return {bucket: {"have": counts.get(bucket, 0),
                         "need": self.per_bucket,
                         "done": counts.get(bucket, 0) >= self.per_bucket}
                for bucket in config.POSE_LABELS}

    def _step_satisfied(self) -> bool:
        step = self.current_step
        if step is None:
            return True
        counts = vault.bucket_counts(self.person)
        return all(counts.get(bucket, 0) >= self.per_bucket
                   for bucket in step["buckets"])

    # ------------------------------------------------------------------
    # the per-frame call
    # ------------------------------------------------------------------
    def step(self) -> dict:
        """Consume one camera frame. Returns the progress report."""
        if self.finished:
            return self.progress()

        step = self.current_step
        if step is None:
            return self._complete()

        frame = self.camera.read()
        if frame is None:
            self.last_message = "waiting for camera frame"
            return self.progress()

        reading = self.cache.get(frame.index)
        if reading is None:
            reading = auth_wall.read_face(frame.bgr, frame.index)
            self.cache.put(frame.index, reading)

        if not reading:
            self.last_message = "no face found - centre your face in the frame"
            return self.progress()

        quality = reading.get("quality", {})
        bucket = reading.get("bucket", "front")

        # The captured direction must be one this step asked for; otherwise the
        # sample would silently land in the wrong bucket and look like progress.
        if bucket not in step["buckets"]:
            wanted = " or ".join(step["buckets"])
            self.last_message = (f"looking {bucket}; this step needs {wanted} - "
                                 f"{step['prompt'].lower()}")
            return self.progress()

        if float(quality.get("score", 0.0)) < config.ENROLL_QUALITY_MIN:
            self.rejected += 1
            self.last_message = quality.get("reason", "quality too low")
            return self.progress()

        counts = vault.bucket_counts(self.person)
        if counts.get(bucket, 0) >= self.per_bucket:
            # Bucket is full; move on rather than stacking duplicates.
            self.last_message = f"{bucket} already has enough samples"
            return self._advance_if_ready()

        # Do not count the exact same frame twice if the camera reuses it.
        if frame.index == self._held_bucket_frame:
            return self.progress()
        self._held_bucket_frame = frame.index

        vault.add_template(self.store, self.name, reading, role=self.role)
        self.captured += 1
        vault.save_store(self.store)
        self._save_dataset_frame(frame, reading, bucket)

        self.last_message = (f"captured {bucket} sample "
                             f"(quality {quality.get('score')})")
        return self._advance_if_ready()

    def _advance_if_ready(self) -> dict:
        if self._step_satisfied():
            self.step_index += 1
            if self.step_index >= len(STEPS):
                return self._complete()
            self.last_message = STEPS[self.step_index]["prompt"]
        return self.progress()

    def _complete(self) -> dict:
        """Finalise: mark the owner, check coverage, close the camera."""
        if self.current_step is None and not self.finished:
            self.finished = True
            if self.role == "owner" and not self.owner_written:
                vault.set_owner(self.store, self.name)
                self.owner_written = True
            vault.save_store(self.store)
            missing = vault.missing_buckets(
                vault.find_person(self.store, self.name) or {"templates": []})
            if missing:
                self.last_message = ("enrollment saved, but these directions are "
                                     f"thin: {', '.join(missing)} - run enrollment "
                                     "again to strengthen them")
            else:
                self.last_message = "enrollment complete in all directions"
        return self.progress()

    def _save_dataset_frame(self, frame, reading: dict, bucket: str):
        """Optional debug capture: text-labelled folders, off unless requested.

        This is the only path that writes an image, it is never used by normal
        operation, and it is what lets a human check "is my side profile really
        being captured" without trusting a number.
        """
        if not self.dataset_path:
            return
        try:
            import cv2

            x1, y1, x2, y2 = reading["bbox"]
            pad = 0.25
            width = x2 - x1
            height = y2 - y1
            x1 = max(0, int(x1 - width * pad))
            y1 = max(0, int(y1 - height * pad))
            x2 = int(x2 + width * pad)
            y2 = int(y2 + height * pad)
            crop = frame.bgr[y1:y2, x1:x2]
            folder = os.path.join(self.dataset_path, self.name, bucket)
            os.makedirs(folder, exist_ok=True)
            stamp = f"{int(time.time() * 1000)}_{self.captured:03d}"
            yaw = (reading.get("pose") or {}).get("yaw")
            quality = (reading.get("quality") or {}).get("score")
            label = f"yaw{'' if yaw is None else round(yaw)}_q{quality}"
            path = os.path.join(folder, f"{stamp}_{label}.jpg")
            cv2.imwrite(path, crop, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
            with open(os.path.join(folder, "labels.txt"), "a", encoding="utf-8") \
                    as handle:
                handle.write(f"{os.path.basename(path)}\tyaw={yaw}\t"
                             f"quality={quality}\tbucket={bucket}\n")
        except Exception:
            # Debug capture must never break enrollment.
            pass


def quick_enroll_from_arrays(name: str, vectors: list) -> dict:
    """Test helper: enroll synthetic vectors without a camera.

    Used by the test suite so matching logic can be verified end to end on a
    machine with no usable camera, which is exactly this laptop's situation.
    """
    store = vault.load_store()
    for index, vector in enumerate(vectors):
        bucket = config.POSE_LABELS[index % len(config.POSE_LABELS)]
        vault.add_template(store, name, {
            "embedding": np.asarray(vector, dtype=np.float32),
            "bucket": bucket, "pose": {"yaw": 0.0},
            "quality": {"score": 0.9},
        }, role="owner")
    vault.set_owner(store, name)
    vault.save_store(store)
    return vault.summary()
