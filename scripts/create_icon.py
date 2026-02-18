from PIL import Image, ImageDraw, ImageFilter, ImageFont
import os

def create_icon():
    bg_top = (68, 150, 255, 255)
    bg_bottom = (24, 78, 210, 255)
    border_color = (255, 255, 255, 80)
    shadow_color = (0, 0, 0, 90)
    line_color = (255, 255, 255, 230)
    glow_color = (255, 255, 255, 120)

    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    images = []

    def load_font(pixel_size: int) -> ImageFont.ImageFont:
        candidates = [
            r"C:\Windows\Fonts\segoeuib.ttf",
            r"C:\Windows\Fonts\segoeui.ttf",
            r"C:\Windows\Fonts\arialbd.ttf",
            r"C:\Windows\Fonts\arial.ttf",
        ]
        for path in candidates:
            try:
                return ImageFont.truetype(path, size=pixel_size)
            except Exception:
                pass
        return ImageFont.load_default()
    
    for size in sizes:
        width, height = size

        img = Image.new("RGBA", size, (0, 0, 0, 0))
        padding = max(1, width // 8)
        radius = max(2, width // 5)

        mask = Image.new("L", size, 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.rounded_rectangle(
            [(padding, padding), (width - padding, height - padding)],
            radius=radius,
            fill=255,
        )

        gradient = Image.new("RGBA", size, (0, 0, 0, 0))
        grad_draw = ImageDraw.Draw(gradient)
        for y in range(height):
            t = y / max(1, height - 1)
            r = int(bg_top[0] * (1 - t) + bg_bottom[0] * t)
            g = int(bg_top[1] * (1 - t) + bg_bottom[1] * t)
            b = int(bg_top[2] * (1 - t) + bg_bottom[2] * t)
            grad_draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

        img.paste(gradient, (0, 0), mask)

        highlight = Image.new("RGBA", size, (0, 0, 0, 0))
        highlight_draw = ImageDraw.Draw(highlight)
        highlight_height = max(1, height // 2)
        for y in range(highlight_height):
            alpha = int(120 * (1 - y / max(1, highlight_height)))
            highlight_draw.line([(0, y), (width, y)], fill=(255, 255, 255, alpha))
        img = Image.alpha_composite(img, Image.composite(highlight, Image.new("RGBA", size), mask))

        border = Image.new("RGBA", size, (0, 0, 0, 0))
        border_draw = ImageDraw.Draw(border)
        border_draw.rounded_rectangle(
            [(padding, padding), (width - padding, height - padding)],
            radius=radius,
            outline=border_color,
            width=max(1, width // 32),
        )
        img = Image.alpha_composite(img, border)

        shadow = Image.new("RGBA", size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_draw.rounded_rectangle(
            [(padding, padding), (width - padding, height - padding)],
            radius=radius,
            outline=shadow_color,
            width=max(1, width // 28),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(1, width // 28)))
        img = Image.alpha_composite(img, shadow)

        inner_padding = padding + max(1, width // 12)
        inner_w = width - 2 * inner_padding
        inner_h = height - 2 * inner_padding
        x0 = inner_padding
        y0 = inner_padding

        points = [
            (x0 + inner_w * 0.12, y0 + inner_h * 0.75),
            (x0 + inner_w * 0.38, y0 + inner_h * 0.58),
            (x0 + inner_w * 0.58, y0 + inner_h * 0.68),
            (x0 + inner_w * 0.78, y0 + inner_h * 0.38),
            (x0 + inner_w * 0.9, y0 + inner_h * 0.22),
        ]

        line_width = max(1, width // 10)

        glow = Image.new("RGBA", size, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow)
        glow_draw.line(points, fill=glow_color, width=line_width * 2, joint="curve")
        glow = glow.filter(ImageFilter.GaussianBlur(radius=max(1, width // 14)))
        img = Image.alpha_composite(img, glow)

        line_layer = Image.new("RGBA", size, (0, 0, 0, 0))
        line_draw = ImageDraw.Draw(line_layer)
        line_draw.line(points, fill=line_color, width=line_width, joint="curve")
        node_radius = max(1, line_width // 2)
        for px, py in (points[0], points[2], points[-1]):
            line_draw.ellipse(
                [(px - node_radius, py - node_radius), (px + node_radius, py + node_radius)],
                fill=(255, 255, 255, 200),
            )
        img = Image.alpha_composite(img, line_layer)

        if width >= 64:
            badge_scale = 3
            badge_w = int(inner_w * 0.5)
            badge_h = int(inner_h * 0.24)
            badge_x = int(x0 + inner_w * 0.06)
            badge_y = int(y0 + inner_h * 0.7)

            badge_big = Image.new("RGBA", (width * badge_scale, height * badge_scale), (0, 0, 0, 0))
            badge_draw = ImageDraw.Draw(badge_big)
            bx = badge_x * badge_scale
            by = badge_y * badge_scale
            bw = badge_w * badge_scale
            bh = badge_h * badge_scale
            badge_radius = max(2, bh // 3)

            badge_draw.rounded_rectangle(
                [(bx, by), (bx + bw, by + bh)],
                radius=badge_radius,
                fill=(0, 0, 0, 90),
                outline=(255, 255, 255, 100),
                width=max(1, (width * badge_scale) // 160),
            )

            font_px = max(10, int(bh * 0.62))
            font = load_font(font_px)
            text = "LLM"
            text_stroke = max(1, font_px // 18)
            text_bbox = badge_draw.textbbox((0, 0), text, font=font, stroke_width=text_stroke)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]
            tx = bx + (bw - text_w) // 2 - text_bbox[0]
            ty = by + (bh - text_h) // 2 - text_bbox[1]

            shadow_offset = max(1, font_px // 18)
            badge_draw.text(
                (tx + shadow_offset, ty + shadow_offset),
                text,
                font=font,
                fill=(0, 0, 0, 140),
                stroke_width=text_stroke,
                stroke_fill=(0, 0, 0, 160),
            )
            badge_draw.text(
                (tx, ty),
                text,
                font=font,
                fill=(255, 255, 255, 235),
                stroke_width=text_stroke,
                stroke_fill=(255, 255, 255, 180),
            )

            badge = badge_big.resize((width, height), resample=Image.Resampling.LANCZOS)
            img = Image.alpha_composite(img, badge)
        else:
            micro = Image.new("RGBA", size, (0, 0, 0, 0))
            micro_draw = ImageDraw.Draw(micro)
            p1 = (x0 + inner_w * 0.18, y0 + inner_h * 0.78)
            p2 = (x0 + inner_w * 0.34, y0 + inner_h * 0.6)
            p3 = (x0 + inner_w * 0.5, y0 + inner_h * 0.78)
            micro_draw.line([p1, p2, p3], fill=(255, 255, 255, 140), width=max(1, width // 24))
            dot_r = max(1, width // 20)
            for px, py in (p1, p2, p3):
                micro_draw.ellipse(
                    [(px - dot_r, py - dot_r), (px + dot_r, py + dot_r)],
                    fill=(255, 255, 255, 200),
                )
            img = Image.alpha_composite(img, micro)

        images.append(img)

    output_dir = os.path.join(os.path.dirname(__file__), "..", "assets")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    output_path = os.path.join(output_dir, "icon.ico")

    images[-1].save(output_path, format="ICO", sizes=sizes)
    print(f"Icon generated at: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    create_icon()
