import struct
import json
import win32api
import win32process
import win32con
import ctypes
from ctypes import wintypes

# 假设我们已经通过逆向工程得知，一个图层结构体（如CLiveryGroup）的内存布局如下：
# 偏移量  字段          类型
# 0x00    position_x    float
# 0x04    position_y    float
# 0x08    size_x        float
# 0x0C    size_y        float
# 0x10    rotation      float
# 0x14    color_r       int (0-255)
# 0x18    color_g       int
# 0x1C    color_b       int
# 0x20    color_a       int
# 0x24    type          int (例如: 16表示旋转椭圆)
LAYER_STRUCT_FORMAT = '<fffffIIIII' # '<' 表示小端序，f=float, I=unsigned int
LAYER_STRUCT_SIZE = struct.calcsize(LAYER_STRUCT_FORMAT)

def parse_shape(shape_json):
    """解析单个JSON形状，提取数据"""
    shape_type = shape_json.get("type")
    if shape_type != 16:  # 只处理旋转椭圆
        return None
    
    data = shape_json["data"]  # [x, y, size_x, size_y, rotation]
    color = shape_json["color"] # [R, G, B, A]
    
    return {
        "x": data[0], "y": data[1], "sx": data[2], "sy": data[3], "rot": data[4],
        "r": color[0], "g": color[1], "b": color[2], "a": color[3],
        "type": 16
    }
#============================================================
def pack_shape_to_bytes(shape_data):
    """将形状数据打包成游戏内存要求的二进制格式"""
    if not shape_data:
        return b''
    
    # 注意：这里的字段顺序必须与 LAYER_STRUCT_FORMAT 完全对应
    packed = struct.pack(
        LAYER_STRUCT_FORMAT,
        shape_data["x"], shape_data["y"],
        shape_data["sx"], shape_data["sy"],
        shape_data["rot"],
        shape_data["r"], shape_data["g"], shape_data["b"], shape_data["a"],
        shape_data["type"]
    )
    return packed

#============================================================