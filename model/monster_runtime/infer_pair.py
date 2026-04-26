#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
infer_pair.py
- 单对/批量左右图立体匹配推理
- 输出：16-bit PNG（disp*256）、可选伪彩、可选npy
放在项目根目录运行，依赖 core/ 与 pretrained/ 与 README 中的环境。
"""
from torch.serialization import add_safe_globals

"""
python infer_pair.py --restore_ckpt ./pretrained/mix_all.pth --left  ./my_data/11.jpg --right ./my_data/22.jpg --out ./outputs --save_color --save_npy
"""

import os
import sys
import glob
import argparse
import time
from pathlib import Path
from typing import List, Tuple

import numpy as np
import torch
import torch.nn as nn
import cv2
from PIL import Image

# === 依赖项目内模块 ===
RUNTIME_ROOT = Path(__file__).resolve().parent
sys.path.append(str(RUNTIME_ROOT))
from core.monster import Monster
from core.utils.utils import InputPadder
from types import SimpleNamespace

def default_monster_args():
    # 与仓库评测脚本的默认配置一致/相近
    return SimpleNamespace(
        encoder='vitl',                # 可选: vits/vitb/vitl/vitg
        hidden_dims=[128, 128, 128],   # GRU 隐层维度
        corr_implementation='reg',     # 相关性实现：reg / alt（按仓库默认）
        shared_backbone=False,         # 是否共享主干
        corr_levels=2,                 # 金字塔层数
        corr_radius=4,                 # 相关性半径
        n_downsample=2,                # 下采样次数
        slow_fast_gru=False,           # 是否使用 slow-fast GRU
        n_gru_layers=3,                # GRU 层数
        max_disp=192                   # 最大视差范围（权重通常按 192 训练）
    )


def parse_args():
    parser = argparse.ArgumentParser("MonSter - Inference on your own stereo pairs")

    # 1) 这些不再 required，允许用默认值
    parser.add_argument("--restore_ckpt", type=str, required=False,
                        help="路径到预训练权重 .pth")
    parser.add_argument("--left", type=str, required=False,
                        help="左图路径；支持通配符（配合 --pair_glob）")
    parser.add_argument("--right", type=str, required=False,
                        help="右图路径；支持通配符（配合 --pair_glob）")

    # 其他参数保持不变
    parser.add_argument("--pair_glob", action="store_true",
                        help="把 --left/--right 当作通配符批量模式")
    parser.add_argument("--out", type=str, default=str(RUNTIME_ROOT / "outputs"),
                        help="输出目录")
    parser.add_argument("--valid_iters", type=int, default=32,
                        help="推理迭代次数（越大越准但越慢）")
    parser.add_argument("--max_pairs", type=int, default=-1,
                        help="仅处理前 N 对（调试用；-1为全部）")
    parser.add_argument("--save_color", action="store_true",
                        help="保存伪彩色视差（_color.png）")
    parser.add_argument("--save_npy", action="store_true",
                        help="保存原始视差 numpy（.npy）")
    parser.add_argument("--suffix", type=str, default="",
                        help="输出文件名后缀（如 _ms32 表示 iters=32）")
    parser.add_argument("--no_cuda", action="store_true",
                        help="用 CPU 推理（不推荐）")

    # 2) 设定你想要的默认值（不传参时就用这些）
    parser.set_defaults(
        restore_ckpt=str(RUNTIME_ROOT / "pretrained" / "mix_all.pth"),
        left=str(RUNTIME_ROOT / "my_data" / "11.jpg"),
        right=str(RUNTIME_ROOT / "my_data" / "22.jpg"),
        out=str(RUNTIME_ROOT / "outputs"),
        valid_iters=32,
        save_color=True,
        save_npy=True,
        no_cuda=False,
    )

    # 3) 如果没有传任何命令行参数（只有脚本名），就用默认值
    if len(sys.argv) == 1:
        args = parser.parse_args([])   # 不从命令行取参
    else:
        args = parser.parse_args()     # 正常解析命令行

    return args


def list_pairs(left_pat: str, right_pat: str, glob_mode: bool) -> List[Tuple[str, str]]:
    if glob_mode:
        L = sorted(glob.glob(left_pat))
        R = sorted(glob.glob(right_pat))
        if len(L) == 0 or len(L) != len(R):
            raise RuntimeError(f"匹配到的左右图数量异常：L={len(L)} R={len(R)}；请检查通配符与目录。")
        return list(zip(L, R))
    else:
        return [(left_pat, right_pat)]


def pil_to_uint8_rgb(path: str) -> np.ndarray:
    """
    读取任意常见格式图片并统一成 uint8 RGB:
    - 16-bit（uint16）线性压到 0~255
    - 灰度扩成 3 通道
    - RGBA 去掉 A
    """
    img = Image.open(path)
    arr = np.array(img)  # 先拿到真正的 dtype，再判断

    # 位深处理：把 16-bit/浮点等线性压到 uint8
    if arr.dtype != np.uint8:
        mn, mx = np.min(arr), np.max(arr)
        if mx <= mn:
            arr = np.zeros_like(arr, dtype=np.uint8)
        else:
            arr = ((arr - mn) / (mx - mn) * 255.0 + 0.5).astype(np.uint8)

    # 通道处理：统一到 HxWx3
    if arr.ndim == 2:
        arr = np.repeat(arr[..., None], 3, axis=2)
    elif arr.ndim == 3:
        if arr.shape[2] == 1:
            arr = np.repeat(arr, 3, axis=2)
        elif arr.shape[2] > 3:
            arr = arr[:, :, :3]  # 丢掉 alpha 或额外通道
    else:
        raise ValueError(f"Unsupported image shape: {arr.shape} from {path}")
    return arr



def load_image_as_tensor(path: str, device: torch.device) -> torch.Tensor:
    img = pil_to_uint8_rgb(path)
    # 与仓库现有脚本保持一致：不 /255、不归一化
    ten = torch.from_numpy(img).permute(2, 0, 1).float()[None].to(device)  # 1x3xHxW, float32
    return ten


def build_model(ckpt_path: str, device: torch.device) -> nn.Module:
    margs = default_monster_args()
    model = Monster(margs)
    # ❌ 不要用 DataParallel（单对推理会把 batch 切成空片）
    model.to(device)

    if not os.path.isfile(ckpt_path):
        raise FileNotFoundError(f"未找到权重：{ckpt_path}")

    # 允许 Namespace；仍然用 weights_only=True（安全）
    add_safe_globals([argparse.Namespace, SimpleNamespace])
    state = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    state_dict = state.get("state_dict", state)

    # 兼容 'module.' 前缀
    new_state = {}
    for k, v in state_dict.items():
        new_state[k if k.startswith("module.") else ("module." + k)] = v

    # 如果权重是 DataParallel 存的（带 module.），而我们是单卡，就挪掉前缀再加载
    try:
        model.load_state_dict({k.replace("module.", "", 1): v for k, v in new_state.items()}, strict=False)
    except RuntimeError:
        # 兜底：直接按原键加载
        model.load_state_dict(state_dict, strict=False)

    model.eval()
    return model

def save_disp_png_uint16(path: str, disp: np.ndarray):
    # KITTI 兼容：保存 disp*256 的 16-bit PNG
    out = np.round(disp * 256.0).astype(np.uint16)
    ok = cv2.imwrite(path, out)
    if not ok:
        raise RuntimeError(f"Failed to save disparity png: {path}")


def save_color_png(path: str, disp: np.ndarray):
    # min-max 归一化后做 JET 伪彩
    d = disp.copy()
    d[np.isnan(d)] = 0.0
    d[np.isinf(d)] = 0.0
    dn = (d - d.min()) / (d.max() - d.min() + 1e-6)
    color_bgr = cv2.applyColorMap((dn * 255.0).astype(np.uint8), cv2.COLORMAP_JET)
    ok = cv2.imwrite(path, color_bgr)
    if not ok:
        raise RuntimeError(f"Failed to save color disparity image: {path}")


def main():
    args = parse_args()
    os.makedirs(args.out, exist_ok=True)

    device = torch.device("cpu" if args.no_cuda or not torch.cuda.is_available() else "cuda")

    pairs = list_pairs(args.left, args.right, args.pair_glob)
    if args.max_pairs > 0:
        pairs = pairs[:args.max_pairs]

    model = build_model(args.restore_ckpt, device)

    total_t = 0.0
    for idx, (lp, rp) in enumerate(pairs, 1):
        stem = os.path.splitext(os.path.basename(lp))[0]
        if args.suffix:
            stem += args.suffix

        try:
            image1 = load_image_as_tensor(lp, device)
            image2 = load_image_as_tensor(rp, device)

            # 尺寸检查：必须一致
            if image1.shape[-2:] != image2.shape[-2:]:
                raise ValueError(f"左右图尺寸不一致：{image1.shape[-2:]} vs {image2.shape[-2:]}")

            padder = InputPadder(image1.shape, divis_by=32)
            image1, image2 = padder.pad(image1, image2)

            torch.cuda.synchronize(device) if device.type == "cuda" else None
            t0 = time.time()
            with torch.no_grad():
                disp = model(image1, image2, iters=args.valid_iters, test_mode=True)
            torch.cuda.synchronize(device) if device.type == "cuda" else None
            t1 = time.time()

            disp = padder.unpad(disp)[0, 0].float().cpu().numpy()
            total_t += (t1 - t0)

            out_png = os.path.join(args.out, f"{stem}.png")
            save_disp_png_uint16(out_png, disp)

            if args.save_color:
                out_color = os.path.join(args.out, f"{stem}_color.png")
                save_color_png(out_color, disp)

            if args.save_npy:
                out_npy = os.path.join(args.out, f"{stem}.npy")
                np.save(out_npy, disp)

            print(f"[{idx}/{len(pairs)}] OK: {lp} -> {out_png}  time={t1 - t0:.3f}s")

        except Exception as e:
            print(f"[{idx}/{len(pairs)}] FAIL: {lp} / {rp} -> {e}")

    if len(pairs) > 0:
        print(f"Avg time per pair: {total_t / len(pairs):.3f}s  (iters={args.valid_iters})")


if __name__ == "__main__":
    main()
