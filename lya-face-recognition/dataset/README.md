# dataset/ — optional debug frames (never committed)

**Empty by default. Nothing here during normal operation.**

This folder is written **only** by `cli.py enroll-test`, which exists so you can
*see* that enrollment is really capturing your side profile and not just
guessing from a number. Normal `cli.py enroll` writes no images at all.

## Layout

```
dataset/
  ipvis/
    front/          front.jpg, front_002.jpg ...
    left_slight/
    left/
    right_slight/
    right/
    labels.txt      one line per image: name, yaw, quality, bucket
```

Each image is a face crop with a little margin, JPEG quality 88. The filename
carries the measured yaw and quality score, so you can compare "what the code
thought the angle was" against what your eyes see.

## Why this folder is worth keeping

Enrollment quality is the whole reason recognition fails from the side. If a
side-angle sample is actually a front-facing shot (because the pose estimate was
wrong, or you did not really turn), no number in the UI will reveal it — but the
photo will. That makes this the fastest way to debug "why does it not know me
when I look left".

## Privacy

These **are** real images of your face, unlike the encrypted store which holds
vectors only. Treat this folder as sensitive:

```powershell
Remove-Item -Recurse -Force .\dataset
```

Deleting it does not affect your enrollment — templates live in `private/`.
`dataset/` is in `.gitignore` so it can never be committed by accident.
