import json

# 输入：FH5-painter 格式的 JSON
INPUT_FILE = "C:\\Users\\Administrator\\Desktop\\Games\\FH5\\picture_and_json\\23\\WEC #81json\\WEC #81.800.FH5-painter.json"
OUTPUT_FILE = "C:\\Users\\Administrator\\Desktop\\Games\\FH5\\picture_and_json\\23\\WEC #81(1)\\WEC #81.800.reload.json"

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

shapes = data["shapes"]

# 构建紧凑格式
lines = ['{"shapes":']

for i, shape in enumerate(shapes):
    t = shape["type"]
    d = [int(round(v)) for v in shape["data"]]   # 浮点 → 整数
    c = [int(v) for v in shape["color"]]
    s = shape["score"]

    # 最后一行不要逗号
    tail = "" if i == len(shapes) - 1 else ","

    line = (
        f'{{"type":{t}, "data":{d}, '
        f'"color":{c}, "score":{s}}}{tail}'
    )
    lines.append(line)

lines.append("]}")
output = "\n".join(lines)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write(output)

print(f"✅ 已生成: {OUTPUT_FILE}")
print(f"📊 共 {len(shapes)} 个形状")