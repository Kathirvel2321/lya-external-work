# models/ — local, offline model files only

**Never commit anything in this folder.** It is listed in `.gitignore`.

## Why this folder exists

The owner's rule is: no unknown source. So this project has **no download code
path at all**. Every model is either already on the machine or placed here by
hand, and every file is validated before it is loaded.

## 1. InsightFace `buffalo_l` (required)

Detection (RetinaFace `det_10g.onnx`), ArcFace recognition
(`w600k_r50.onnx`) and landmarks (`2d106det.onnx`) come from InsightFace's
`buffalo_l` pack, which already exists at:

```
~/.insightface/models/buffalo_l/
```

`config.models_available()` checks for those `.onnx` files and `auth_wall.py`
aborts with `ModelUnavailable` if any are missing. `INSIGHTFACE_HOME` is set
before the library is imported, so the library can only ever look in that local
folder — it can never quietly fetch the pack.

Only three modules are enabled: detection, recognition and 2-D landmarks.
`genderage` and the 3-D model are skipped, which avoids loading ~150 MB of
weights this service would never use.

## 2. Passive liveness model (optional)

Place **one** of these here to enable passive photo/screen replay rejection:

```
models/fas_minifasnet.onnx
models/face_landmark.onnx
```

Rules enforced by `liveness.py`:

| Rule | Reason |
| --- | --- |
| The file must be local; there is no fetch code | No unknown source, works offline |
| Filename must match a known pattern | An arbitrary dropped `.onnx` is ignored, not executed |
| Loaded via `onnxruntime` CPU session, no custom ops | Static weights only |

Recommended, well-known offline source: a converted `MiniFASNetV2` ONNX from
**minivision-ai/Silent-Face-Anti-Spoofing** (Apache-2.0). That project is the
same family LYA's existing `security/liveness.py` uses.

## Behaviour when a model is missing

* InsightFace missing → service refuses to start; verification is **denied**
  (fails closed, never open).
* Liveness model missing → passive check reports `model_available=false` and
  **does not block** on its own; secure actions still require the active
  challenge (blink / head-turn), which needs no model. The result is always
  labelled with which signals were actually available.
