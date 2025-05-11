from flask import Flask, request, jsonify, send_file
from mcstatus import JavaServer
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import base64
import re

app = Flask(__name__)

# Minecraft §颜色代码映射
MC_COLOR_MAP = {
    '0': (0, 0, 0),         '1': (0, 0, 170),       '2': (0, 170, 0),
    '3': (0, 170, 170),     '4': (170, 0, 0),       '5': (170, 0, 170),
    '6': (255, 170, 0),     '7': (170, 170, 170),   '8': (85, 85, 85),
    '9': (85, 85, 255),     'a': (85, 255, 85),     'b': (85, 255, 255),
    'c': (255, 85, 85),     'd': (255, 85, 255),    'e': (255, 255, 85),
    'f': (255, 255, 255),   'r': (255, 255, 255),
}

def draw_colored_text(draw, text, position, font, default_color=(255, 255, 255), line_spacing=4, mc_color_map=None):
    if mc_color_map is None:
        mc_color_map = MC_COLOR_MAP
    import re
    x, y = position
    line_height = font.getbbox("§")[3] - font.getbbox("§")[1] + line_spacing

    lines = re.split(r'<br\s*/?>|\n', text)

    for line in lines:
        i = 0
        current_color = default_color
        while i < len(line):
            if line[i] == '§' and i + 1 < len(line):
                code = line[i + 1].lower()
                color = mc_color_map.get(code)
                if color:
                    current_color = color
                i += 2
                continue
            draw.text((x, y), line[i], font=font, fill=current_color)
            x += font.getbbox(line[i])[2] - font.getbbox(line[i])[0]
            i += 1

        x = position[0]
        y += line_height


def query_minecraft_server(hostname: str, port: int = None):
    try:
        server = JavaServer.lookup(f"{hostname}" if port is None else f"{hostname}:{port}")
        status = server.status()

        favicon = getattr(status, "favicon", None)
        motd_raw = status.description

        return {
            "hostname": hostname,
            "port": port if port is not None else 25565,
            "ping": int(status.latency),
            "version": status.version.name,
            "protocol": status.version.protocol,
            "players": {
                "max": status.players.max,
                "online": status.players.online
            },
            "description": {
                "html": str(motd_raw),
                "text": re.sub(r'§.', '', str(motd_raw))
            },
            "description_raw": {
                "extra": [{"text": re.sub(r'§.', '', str(motd_raw))}],
                "text": ""
            },
            "favicon": favicon,
            "modinfo": {},
            "online": True
        }
    except Exception as e:
        return {
            "hostname": hostname,
            "port": port if port else 25565,
            "online": False,
            "error": str(e)
        }

def generate_server_image(data, scale=1.0):
    base_width, base_height = 610, 430
    width, height = int(base_width * scale), int(base_height * scale)
    background_color = (12, 10, 30)

    img = Image.new("RGBA", (width, height), background_color)
    draw = ImageDraw.Draw(img)

    def scaled(val): return int(val * scale)

    try:
        font_title = ImageFont.truetype("NotoSansSC-Bold.ttf", scaled(36))
        font_sub = ImageFont.truetype("NotoSansSC-Regular.ttf", scaled(16))
        font_label = ImageFont.truetype("NotoSansSC-Regular.ttf", scaled(20))
        font_value = ImageFont.truetype("NotoSansSC-Bold.ttf", scaled(22))
    except:
        font_title = font_sub = font_label = font_value = ImageFont.load_default()

    icon_x, icon_y = scaled(60), scaled(48)
    if data.get("favicon") and data["favicon"].startswith("data:image/png;base64,"):
        try:
            icon_data = base64.b64decode(data["favicon"].split(",")[1])
            icon_img = Image.open(BytesIO(icon_data)).convert("RGBA").resize((scaled(64), scaled(64)))
            mask = Image.new("L", icon_img.size, 0)
            draw_mask = ImageDraw.Draw(mask)
            draw_mask.rounded_rectangle([0, 0, scaled(64), scaled(64)], radius=scaled(10), fill=255)
            icon_img.putalpha(mask)
            img.paste(icon_img, (icon_x, icon_y), icon_img)
        except Exception:
            pass

    draw.text((scaled(140), scaled(46)), "Minecraft 服务器", font=font_sub, fill=(180, 180, 180))
    draw.text((scaled(140), scaled(63)), data["hostname"], font=font_title, fill="white")
    draw.text((scaled(60), scaled(125)), "基本信息", font=font_label, fill="white")

    label_color = (200, 200, 200)
    value_color = (255, 255, 255)

    info_left = [
        ("状态", "在线" if data["online"] else "离线"),
        ("版本", data.get("version", "")),
    ]
    info_right = [
        ("玩家数量", f'{data["players"]["online"]} / {data["players"]["max"]}'),
        ("延迟", str(data.get("ping", "")))
    ]

    x_left = scaled(60)
    x_right = scaled(380)
    y_base = scaled(180)
    y_step = scaled(60)

    def render_info_block(draw, items, x, y_start, y_step, label_font, value_font, label_color, value_color):
        for i, (label, value) in enumerate(items):
            y = y_start + i * y_step
            draw.text((x, y), label, font=label_font, fill=label_color)
            draw.text((x, y + scaled(24)), value, font=value_font, fill=value_color)

    render_info_block(draw, info_left, x_left, y_base, y_step, font_label, font_value, label_color, value_color)
    render_info_block(draw, info_right, x_right, y_base, y_step, font_label, font_value, label_color, value_color)

    # 渲染 MOTD
    font_motd = ImageFont.truetype("Minecraft.ttf", scaled(21))
    motd_y_start = y_base + len(info_left) * y_step
    draw.text((x_left, motd_y_start), "服务器 MOTD", font=font_label, fill=label_color)
    draw_colored_text(
        draw,
        data["description"]["html"],
        (x_left, motd_y_start + scaled(32)),
        font=font_motd,
        default_color=value_color
    )

    output = BytesIO()
    img.save(output, format='PNG')
    output.seek(0)
    return output

@app.route('/<path:server_addr>')
def query(server_addr):
    img = request.args.get('img')
    size_param = request.args.get('size', '100')

    try:
        scale = float(size_param) / 100
        if scale <= 0:
            scale = 1.0
    except ValueError:
        scale = 1.0

    if ':' in server_addr:
        hostname, port = server_addr.split(":")
        port = int(port)
    else:
        hostname = server_addr
        port = None

    data = query_minecraft_server(hostname, port)

    if img is not None:
        image_stream = generate_server_image(data, scale=scale)
        return send_file(image_stream, mimetype='image/png')

    return jsonify(data)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
