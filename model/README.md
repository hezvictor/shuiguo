# Model Files Guide

This project ignores large model binaries by default (`*.pt`, `*.pth`, `*.npz`, etc.).

Please place required model files locally at the following paths:

- `model/epoch90.pt`
- `model/best_model_finetuned.pth`
- `model/Mango_50_ultimate_model.pth`
- `model/Banana_50_ultimate_model.pth`
- `model/strawberry_ultimate_model.pth`
- `model/monster_runtime/pretrained/mix_all.pth`
- `model/monster_runtime/pretrained/depth_anything_v2_vitl.pth`
- `model/monster_runtime/calibration/calib_stereo.npz`

Notes:

- Keep source code under `model/monster_runtime/` tracked in Git.
- Do not commit model binaries directly to this repository.
- Use internal storage or model registry for binary distribution.
