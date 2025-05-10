from flask import Flask, request, jsonify, send_file
from mcstatus import JavaServer
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import base64
import re

app = Flask(__name__)

def query_minecraft_server(hostname: str, port: int = None):
    try:
        server = JavaServer.lookup(f"{hostname}" if port is None else f"{hostname}:{port}")
        status = server.status()

        favicon = getattr(status, "favicon", None)
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
                "html": status.description,
                "text": re.sub(r'§.', '', str(status.description))
            },
            "description_raw": {
                "extra": [{"text": re.sub(r'§.', '', str(status.description))}],
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

def generate_server_image(data):
    # 图像尺寸和背景色
    width, height = 560, 340
    background_color = (12, 10, 30)

    img = Image.new("RGBA", (width, height), background_color)
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("NotoSansSC-Bold.ttf", 36)
        font_sub = ImageFont.truetype("NotoSansSC-Regular.ttf", 16)
        font_label = ImageFont.truetype("NotoSansSC-Regular.ttf", 20)
        font_value = ImageFont.truetype("NotoSansSC-Bold.ttf", 22)
    except:
        font_title = font_sub = font_label = font_value = ImageFont.load_default()

    # 左上角图标
    icon_x, icon_y = 60, 48
    if data.get("favicon") and data["favicon"].startswith("data:image/png;base64,"):
        try:
            icon_data = base64.b64decode(data["favicon"].split(",")[1])
            icon_img = Image.open(BytesIO(icon_data)).convert("RGBA").resize((64, 64))
            mask = Image.new("L", icon_img.size, 0)
            draw_mask = ImageDraw.Draw(mask)
            draw_mask.rounded_rectangle([0, 0, 64, 64], radius=10, fill=255)
            icon_img.putalpha(mask)
            img.paste(icon_img, (icon_x, icon_y), icon_img)
        except Exception:
            pass

    # 标题和副标题
    draw.text((140, 46), "Minecraft 服务器", font=font_sub, fill=(180, 180, 180))
    draw.text((140, 63), data["hostname"], font=font_title, fill="white")
    draw.text((60, 125), "基本信息", font=font_label, fill="white")

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

    x_left = 60
    x_right = 380
    y_base = 180
    y_step = 60

    for i, (label, value) in enumerate(info_left):
        draw.text((x_left, y_base + i * y_step), label, font=font_label, fill=label_color)
        draw.text((x_left, y_base + 24 + i * y_step), value, font=font_value, fill=value_color)

    for i, (label, value) in enumerate(info_right):
        draw.text((x_right, y_base + i * y_step), label, font=font_label, fill=label_color)
        draw.text((x_right, y_base + 24 + i * y_step), value, font=font_value, fill=value_color)

    # 输出图像
    output = BytesIO()
    img.save(output, format='PNG')
    output.seek(0)
    return output


@app.route('/<path:server_addr>')
def query(server_addr):
    img = request.args.get('img')

    if ':' in server_addr:
        hostname, port = server_addr.split(":")
        port = int(port)
    else:
        hostname = server_addr
        port = None

    data = query_minecraft_server(hostname, port)

    if img is not None:
        image_stream = generate_server_image(data)
        return send_file(image_stream, mimetype='image/png')

    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
