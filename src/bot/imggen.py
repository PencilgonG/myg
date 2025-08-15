import io
from typing import Dict, List, Optional

from PIL import Image, ImageDraw, ImageFont
import aiohttp

# ---------- Utilitaires ----------

async def _fetch_image(session: aiohttp.ClientSession, url: str, size: Optional[tuple[int,int]] = None) -> Image.Image:
    try:
        async with session.get(url, timeout=10) as r:
            r.raise_for_status()
            data = await r.read()
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        if size:
            img = img.resize(size, Image.LANCZOS)
        return img
    except Exception:
        w, h = size or (64, 64)
        return Image.new("RGBA", (w, h), (0,0,0,0))

def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("src/assets/Inter-SemiBold.ttf", size)
    except Exception:
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except Exception:
            return ImageFont.load_default()

def _text_wh(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int,int]:
    # Pillow 10+: utiliser textbbox
    bbox = draw.textbbox((0,0), text, font=font)
    return (bbox[2] - bbox[0], bbox[3] - bbox[1])

# ---------- Thème ----------

class Theme:
    def __init__(self, *, bg=(17,17,17,255), fg=(241,224,176,255), accent=(232,93,93,255), grid=(255,255,255,26)):
        self.bg = bg; self.fg = fg; self.accent = accent; self.grid = grid

# ---------- Rendus ----------

async def render_lobby_banner(
    *,
    title: str,
    mode: str,
    logo_url: Optional[str],
    role_icon_urls: Dict[str, str],
    players_by_role: Dict[str, List[str]],
    size: tuple[int,int] = (1200, 520),
    theme: Theme = Theme(),
) -> io.BytesIO:
    W, H = size
    canvas = Image.new("RGBA", (W, H), theme.bg)
    draw = ImageDraw.Draw(canvas)

    # grille légère
    for x in range(0, W, 32): draw.line([(x,0),(x,H)], fill=theme.grid, width=1)
    for y in range(0, H, 32): draw.line([(0,y),(W,y)], fill=theme.grid, width=1)

    # header
    header_h = 92
    draw.rectangle([(0,0),(W,header_h)], fill=theme.accent)

    f_title = _load_font(40)
    f_mode  = _load_font(24)
    draw.text((24, 18), title, font=f_title, fill=(255,255,255,255))
    draw.text((24, 58), f"Mode: {mode}", font=f_mode, fill=(255,255,255,220))

    # logo
    if logo_url:
        try:
            async with aiohttp.ClientSession() as session:
                logo = await _fetch_image(session, logo_url, size=(76,76))
            canvas.alpha_composite(logo, dest=(W-76-16, 8))
        except Exception:
            pass

    roles_order = ["Top","Jungle","Mid","ADC","Support"]
    col_pad = 20
    col_w = (W - 2*col_pad) // 5
    top_y = header_h + 16
    icon_size = (56,56)
    f_role = _load_font(22)
    f_player = _load_font(18)

    async with aiohttp.ClientSession() as session:
        for i, role in enumerate(roles_order):
            x0 = col_pad + i*col_w

            # icône
            icon = None
            url = role_icon_urls.get(role)
            if url:
                try:
                    icon = await _fetch_image(session, url, size=icon_size)
                except Exception:
                    icon = None
            if icon:
                canvas.alpha_composite(icon, dest=(x0 + (col_w - icon_size[0])//2, top_y))

            # label rôle (mesure avec textbbox)
            role_text_w, _ = _text_wh(draw, role, f_role)
            draw.text((x0 + (col_w - role_text_w)//2, top_y + icon_size[1] + 8), role, font=f_role, fill=theme.fg)

            # joueurs
            y = top_y + icon_size[1] + 8 + 28
            for nick in players_by_role.get(role, []):
                txt = nick if len(nick) <= 32 else nick[:31] + "…"
                draw.text((x0 + 8, y), f"• {txt}", font=f_player, fill=(220,220,220,255))
                y += 24

    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    out.seek(0)
    return out


async def render_teams_banner(
    *,
    title: str,
    mode: str,
    logo_url: Optional[str],
    blue_team: List[str],
    red_team: List[str],
    capt_blue: Optional[str] = None,
    capt_red: Optional[str] = None,
    size: tuple[int,int] = (1200, 520),
    theme: Theme = Theme(),
) -> io.BytesIO:
    W, H = size
    canvas = Image.new("RGBA", (W, H), theme.bg)
    draw = ImageDraw.Draw(canvas)

    header_h = 92
    draw.rectangle([(0,0),(W,header_h)], fill=theme.accent)

    f_title = _load_font(40)
    f_mode  = _load_font(24)
    draw.text((24, 18), f"{title} — Line-ups", font=f_title, fill=(255,255,255,255))
    draw.text((24, 58), f"Mode: {mode}", font=f_mode, fill=(255,255,255,220))

    if logo_url:
        try:
            async with aiohttp.ClientSession() as session:
                logo = await _fetch_image(session, logo_url, size=(76,76))
            canvas.alpha_composite(logo, dest=(W-76-16, 8))
        except Exception:
            pass

    f_head  = _load_font(26)
    f_line  = _load_font(20)

    mid_x = W // 2
    pad = 28
    top = header_h + 24

    # Blue
    draw.text((pad, top), "🔵 BLUE", font=f_head, fill=(170,210,255,255))
    y = top + 36
    if capt_blue:
        draw.text((pad, y), f"Capitaine: {capt_blue}", font=f_line, fill=(220,220,220,255))
        y += 28
    for line in blue_team:
        txt = line if len(line) <= 48 else line[:47] + "…"
        draw.text((pad, y), f"• {txt}", font=f_line, fill=(230,230,230,255))
        y += 26

    # Red
    right_x = mid_x + pad
    draw.text((right_x, top), "🔴 RED", font=f_head, fill=(255,180,180,255))
    y = top + 36
    if capt_red:
        draw.text((right_x, y), f"Capitaine: {capt_red}", font=f_line, fill=(220,220,220,255))
        y += 28
    for line in red_team:
        txt = line if len(line) <= 48 else line[:47] + "…"
        draw.text((right_x, y), f"• {txt}", font=f_line, fill=(230,230,230,255))
        y += 26

    out = io.BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    out.seek(0)
    return out
