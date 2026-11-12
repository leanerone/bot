"""Fab Bot 应用图标生成器 (UMC 标志 × 半导体晶圆 × 液态玻璃)。

用法:  .venv/Scripts/python.exe desktop/shell/Assets/generate_icon.py
依赖:  Pillow, numpy
输入:  Assets/umc-source.png (用户提供的 UMC 圆形标志, 白底)
输出:  Assets/fabbot*.png/.ico, ui/public/favicon*, ui/public/brand.png,
       Assets/icon-preview.png (视觉校对图)

设计: 深蓝玻璃圆角方底 + 抛光晶圆盘(die 网格 / 同心刻线 / notch / 衍射虹彩)
       + 精确抠色的 UMC 标志 + 玻璃高光与虹彩描边。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
PUBLIC = HERE.parents[1] / "ui" / "public"
SOURCE = HERE / "umc-source.png"

W = 1024
S = 2  # 超采样倍率, 保证圆弧/描边平滑
N = W * S
CX = CY = W / 2
R = 396  # 晶圆盘半径
BLUE = (0, 113, 189)  # UMC 蓝
GRAY = (102, 102, 102)  # UMC 灰


def q(v: float) -> int:
    return int(round(v * S))


def blank() -> Image.Image:
    return Image.new("RGBA", (N, N), (0, 0, 0, 0))


def rgba_from(arr: np.ndarray, alpha: np.ndarray | None = None) -> Image.Image:
    rgb = np.clip(arr, 0, 255).astype(np.uint8)
    a = np.full((N, N, 1), 255, np.uint8) if alpha is None else np.clip(alpha, 0, 255).astype(np.uint8)[..., None]
    return Image.fromarray(np.concatenate([rgb, a], axis=2), "RGBA")


def clip_alpha(img: Image.Image, mask: Image.Image) -> Image.Image:
    out = img.copy()
    out.putalpha(ImageChops.multiply(out.getchannel("A"), mask))
    return out


# ── 1. 精确抠掉 UMC 标志的白底（保留纯正品牌色 + 抗锯齿边缘） ──────────────
def extract_logo() -> Image.Image:
    src = np.asarray(Image.open(SOURCE).convert("RGB")).astype(np.float32)
    white = np.array([255.0, 255.0, 255.0], np.float32)

    def unmatte(fore: tuple[int, int, int]):
        f = np.array(fore, np.float32)
        v = white - f
        t = np.clip(((white - src) * v).sum(axis=2) / (v * v).sum(), 0, 1)
        err = ((src - (white - t[..., None] * v)) ** 2).sum(axis=2)
        return t, err

    tb, eb = unmatte(BLUE)
    tg, eg = unmatte(GRAY)
    use_blue = eb < eg
    alpha = np.where(use_blue, tb, tg)
    fg = np.where(use_blue[..., None], np.array(BLUE, np.float32), np.array(GRAY, np.float32))
    out = np.concatenate([fg.astype(np.uint8), (alpha * 255).astype(np.uint8)[..., None]], axis=2)
    im = Image.fromarray(out, "RGBA")
    box = im.getchannel("A").point(lambda p: 255 if p > 6 else 0).getbbox()
    return im.crop(box)


# ── 2. 深蓝液态玻璃底板 ────────────────────────────────────────────────────
def make_squircle_mask() -> Image.Image:
    m = Image.new("L", (N, N), 0)
    ImageDraw.Draw(m).rounded_rectangle((q(20), q(20), q(1004), q(1004)), radius=q(232), fill=255)
    return m


def make_base(mask: Image.Image, xn: np.ndarray, yn: np.ndarray) -> Image.Image:
    t = np.clip(0.54 * xn + 0.46 * yn, 0, 1)
    # 底板刻意压深：与 UMC 品牌蓝拉开明度差，白色晶圆盘与蓝色弧才不会糊在一起
    stops = [(0.0, (9, 28, 62)), (0.46, (4, 62, 124)), (1.0, (3, 19, 50))]
    base = np.stack(
        [np.interp(t, [s[0] for s in stops], [s[1][k] for s in stops]) for k in range(3)], axis=2
    ).astype(np.float32)

    def glow(cx: float, cy: float, rad: float, color, strength: float) -> np.ndarray:
        r = np.sqrt((xn - cx) ** 2 + (yn - cy) ** 2)
        g = np.clip(1 - r / rad, 0, 1) ** 2 * strength
        return g[..., None] * np.array(color, np.float32)

    base += glow(0.17, 0.08, 0.82, (78, 146, 220), 0.52)  # 左上冷白光
    base += glow(0.86, 0.90, 0.72, (96, 72, 198), 0.30)  # 右下紫光
    base += glow(0.78, 0.12, 0.55, (0, 186, 208), 0.20)  # 右上青光
    base += np.random.default_rng(7).normal(0, 1.4, (N, N, 1)).astype(np.float32)  # 极细颗粒
    out = rgba_from(base)
    out.putalpha(mask)
    return out


# ── 3. 晶圆盘：抛光面 / die 网格 / 同心刻线 / notch / 衍射虹彩 ──────────────
def make_wafer(mask: Image.Image, xn: np.ndarray, yn: np.ndarray) -> tuple[Image.Image, Image.Image]:
    # 盘面遮罩：底部 V 形定位缺口 (notch)
    wm = Image.new("L", (N, N), 0)
    dw = ImageDraw.Draw(wm)
    dw.ellipse((q(CX - R), q(CY - R), q(CX + R), q(CY + R)), fill=255)
    dw.polygon(
        [(q(CX - 30), q(CY + R + 2)), (q(CX), q(CY + R - 40)), (q(CX + 30), q(CY + R + 2))], fill=0
    )

    # 抛光面径向渐变：中心纯白，边缘银蓝
    rr = np.sqrt((xn - 0.5) ** 2 + (yn - 0.5) ** 2) / (R / W)
    wr = np.clip(rr, 0, 1)
    stops = [(0.0, (255, 255, 255)), (0.62, (245, 251, 255)), (1.0, (203, 226, 247))]
    surf = np.stack(
        [np.interp(wr, [s[0] for s in stops], [s[1][k] for s in stops]) for k in range(3)], axis=2
    ).astype(np.float32)
    sheen = np.exp(-(((0.72 * xn + 0.28 * yn) - 0.36) / 0.12) ** 2) * 12
    surf = np.clip(surf + sheen[..., None], 0, 255)
    wafer = clip_alpha(rgba_from(surf, np.full((N, N), 255, np.float32)), wm)

    # die 网格 + 少量着色晶粒（wafer map），全部限制在盘内
    grid = blank()
    dg = ImageDraw.Draw(grid)
    step = 46
    rng = np.random.default_rng(2026)
    for gx in range(int(CX - R) // step - 1, int(CX + R) // step + 2):
        for gy in range(int(CY - R) // step - 1, int(CY + R) // step + 2):
            x0, y0 = CX - R + gx * step, CY - R + gy * step
            p = rng.random()
            if p < 0.10:
                dg.rectangle((q(x0 + 2), q(y0 + 2), q(x0 + step - 3), q(y0 + step - 3)), fill=(0, 150, 220, 38))
            elif p < 0.17:
                dg.rectangle((q(x0 + 2), q(y0 + 2), q(x0 + step - 3), q(y0 + step - 3)), fill=(126, 96, 226, 30))
            elif p < 0.22:
                dg.rectangle((q(x0 + 2), q(y0 + 2), q(x0 + step - 3), q(y0 + step - 3)), fill=(255, 255, 255, 56))
    for i in range(-20, 22):
        x = CX + i * step
        dg.line((q(x), q(CY - R - 10), q(x), q(CY + R + 10)), fill=(0, 113, 189, 46), width=max(1, q(1.2)))
        y = CY + i * step
        dg.line((q(CX - R - 10), q(y), q(CX + R + 10), q(y)), fill=(0, 113, 189, 46), width=max(1, q(1.2)))
    grid = clip_alpha(grid, wm)
    wafer = Image.alpha_composite(wafer, grid)

    # 晶圆衍射虹彩：三条斜向柔光带
    iri = blank()
    di = ImageDraw.Draw(iri)
    for off, col in [(-0.20, (64, 214, 236, 78)), (0.02, (150, 128, 255, 64)), (0.24, (255, 150, 208, 52))]:
        di.line(
            (q(-260 + off * W), q(1180), q(920 + off * W), q(-200)), fill=col, width=q(74)
        )
    iri = clip_alpha(iri.filter(ImageFilter.GaussianBlur(q(26))), wm)
    wafer = Image.alpha_composite(wafer, iri)

    # 同心刻线 + 外缘亮环
    rings = blank()
    dr = ImageDraw.Draw(rings)
    for rad, a in [(R - 7, 108), (R - 21, 58), (R - 40, 34)]:
        dr.ellipse((q(CX - rad), q(CY - rad), q(CX + rad), q(CY + rad)), outline=(0, 113, 189, a), width=max(1, q(1.6)))
    dr.ellipse((q(CX - R), q(CY - R), q(CX + R), q(CY + R)), outline=(255, 255, 255, 190), width=max(1, q(2.6)))
    wafer = Image.alpha_composite(wafer, clip_alpha(rings, wm))

    # 盘外蓝色辉光（让晶圆从底板上"浮"起来）
    halo = blank()
    ImageDraw.Draw(halo).ellipse(
        (q(CX - R - 8), q(CY - R - 8), q(CX + R + 8), q(CY + R + 8)),
        outline=(0, 158, 240, 150), width=q(12),
    )
    halo = clip_alpha(halo.filter(ImageFilter.GaussianBlur(q(11))), mask)
    return wafer, halo


# ── 4. 合成 ───────────────────────────────────────────────────────────────
def build() -> Image.Image:
    mask = make_squircle_mask()
    yn, xn = np.mgrid[0:N, 0:N].astype(np.float32)
    xn /= N - 1
    yn /= N - 1

    base = make_base(mask, xn, yn)
    wafer, halo = make_wafer(mask, xn, yn)
    out = Image.alpha_composite(base, halo)
    out = Image.alpha_composite(out, wafer)

    # UMC 标志：等比放大到 690，居中叠加；先落一层柔和投影
    logo = extract_logo()
    scale = 648 / max(logo.size)  # 稍小于晶圆盘, 让外圈 die 网格 / 刻线露出来
    logo = logo.resize((q(logo.width * scale), q(logo.height * scale)), Image.LANCZOS)
    lg = blank()
    lx, ly = q(CX) - logo.width // 2, q(CY) - logo.height // 2
    lg.paste(logo, (lx, ly), logo)

    shadow_alpha = lg.getchannel("A").filter(ImageFilter.GaussianBlur(q(11)))
    shadow = Image.new("RGBA", (N, N), (6, 24, 52, 0))
    shadow.putalpha(shadow_alpha.point(lambda p: int(p * 0.30)))
    shifted = blank()
    shifted.paste(shadow, (0, q(9)))
    out = Image.alpha_composite(out, clip_alpha(shifted, mask))
    out = Image.alpha_composite(out, lg)

    # 玻璃顶层：上半部柔光 + 边缘虹彩描边 + 内暗线
    top = np.clip(1 - yn / 0.46, 0, 1) ** 1.7 * 74
    glass = rgba_from(np.full((N, N, 3), 255, np.float32), top)
    out = Image.alpha_composite(out, clip_alpha(glass, mask))

    edge = blank()
    de = ImageDraw.Draw(edge)
    de.rounded_rectangle((q(20), q(20), q(1004), q(1004)), radius=q(232), outline=(255, 255, 255, 118), width=q(2.6))
    de.rounded_rectangle((q(23), q(23), q(1001), q(1001)), radius=q(229), outline=(2, 22, 58, 74), width=q(2))
    # 贴合轮廓的短高光（不要画内切椭圆弧, 那会在底板上留下"划痕"）
    de.line((q(300), q(22), q(700), q(22)), fill=(214, 244, 255, 132), width=q(3))
    de.line((q(470), q(1002), q(760), q(1002)), fill=(188, 166, 255, 78), width=q(2.6))
    out = Image.alpha_composite(out, clip_alpha(edge.filter(ImageFilter.GaussianBlur(q(0.9))), mask))

    out.putalpha(ImageChops.multiply(out.getchannel("A"), mask))
    return out.resize((W, W), Image.LANCZOS)


def ico(path: Path, img: Image.Image, sizes: list[int]) -> None:
    img.save(path, format="ICO", sizes=[(s, s) for s in sizes])


def font(size: int) -> ImageFont.FreeTypeFont:
    for p in ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def preview(img: Image.Image) -> None:
    """浅/深背景下大图 + 实际尺寸排, 便于校对小尺寸可读性。"""
    PW, PH = 1440, 620
    cv = Image.new("RGB", (PW, PH), (238, 242, 248))
    d = ImageDraw.Draw(cv)
    d.rectangle((0, 0, 720, PH), fill=(242, 246, 252))
    d.rectangle((720, 0, PW, PH), fill=(20, 32, 52))
    big = img.resize((400, 400), Image.LANCZOS)
    cv.paste(big, (70, 70), big)
    cv.paste(big, (830, 70), big)
    d.text((70, 492), "LIGHT", fill=(60, 78, 104), font=font(20))
    d.text((830, 492), "DARK", fill=(170, 196, 226), font=font(20))
    d.text((70, 526), "FAB BOT  /  UMC x WAFER", fill=(20, 84, 148), font=font(26))
    x = 830
    for s in (16, 24, 32, 48, 64, 96):
        small = img.resize((s, s), Image.LANCZOS)
        cv.paste(small, (x, 540 - s), small)
        d.text((x, 552), str(s), fill=(150, 178, 210), font=font(15))
        x += s + 34
    cv.save(HERE / "icon-preview.png")


def main() -> None:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    img = build()
    img.save(HERE / "fabbot.png")
    img.resize((512, 512), Image.LANCZOS).save(HERE / "fabbot-512.png")
    img.resize((256, 256), Image.LANCZOS).save(HERE / "fabbot-256.png")
    ico(HERE / "fabbot.ico", img, [16, 20, 24, 32, 40, 48, 64, 128, 256])
    img.resize((256, 256), Image.LANCZOS).save(PUBLIC / "brand.png")
    img.resize((64, 64), Image.LANCZOS).save(PUBLIC / "favicon.png")
    ico(PUBLIC / "favicon.ico", img, [16, 32, 48])
    preview(img)
    print("生成完成:", HERE / "fabbot.ico")


if __name__ == "__main__":
    main()
