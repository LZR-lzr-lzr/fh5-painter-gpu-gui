"""
ini_writer.py
读取基准 ini（c.ini），只修改 stopAt / saveAt / saveEvery，
生成新的 ini 到 runtime 目录。

用法：
    # 交互式
    python ini_writer.py

    # 直接指定参数
    python ini_writer.py --stop-at 5000 --save-at "1000,2000,3000,4000,5000" --save-every 100

    # 指定输入/输出路径
    python ini_writer.py --src "C:\...\c.ini" --dst "C:\...\runtime\custom.ini" \
        --stop-at 5000 --save-at "1000,3000,5000" --save-every 200
"""

import os
import re
import argparse

script_dir = os.path.dirname(os.path.abspath(__file__))

# 默认 c.ini 位置（相对于项目结构）
DEFAULT_SRC = r"C:\Users\Administrator\Desktop\Games\FH5\forza-painter-geometrize-gpu-main\settings\c.ini"

# 默认输出到脚本目录下的 runtime
DEFAULT_DST = os.path.join(script_dir, "runtime", "custom.ini")


# ============================================================
# 读取 ini
# ============================================================
def read_ini(ini_path: str) -> list:
    """
    读取 ini 文件，返回行列表（保留原始顺序和注释）
    """
    if not os.path.exists(ini_path):
        raise FileNotFoundError(f"找不到基准配置文件: {ini_path}")

    with open(ini_path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    print(f"📖 已读取基准配置: {ini_path}  ({len(lines)} 行)")
    return lines


# ============================================================
# 修改指定字段
# ============================================================
def set_ini_value(lines: list, key: str, value: str) -> list:
    """
    在行列表里设置 key = value
    - 如果 key 已存在，替换它的值
    - 如果 key 不存在，追加到末尾
    - 大小写不敏感匹配 key
    """
    key_lower = key.lower()
    pattern = re.compile(rf"^\s*{re.escape(key_lower)}\s*=", re.IGNORECASE)

    found = False
    new_lines = []
    for line in lines:
        if pattern.match(line):
            new_lines.append(f"{key} = {value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        # 确保最后一行有换行
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"{key} = {value}\n")
        print(f"➕ 新增字段: {key} = {value}")
    else:
        print(f"✏️ 修改字段: {key} = {value}")

    return new_lines


# ============================================================
# 保存 ini
# ============================================================
def save_ini(lines: list, dst_path: str):
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    with open(dst_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"💾 已保存: {dst_path}")


# ============================================================
# 校验与解析
# ============================================================
def parse_save_at(value: str) -> str:
    """
    把 "1000,2000,3000" 或 "1000, 2000, 3000" 规范化为 "1000,2000,3000"
    并校验每个元素都是整数
    """
    nums = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        if not token.isdigit():
            raise ValueError(f"saveAt 里有非法数字: {token}")
        nums.append(int(token))

    if not nums:
        raise ValueError("saveAt 不能为空")

    # 从小到大排序，去重
    nums = sorted(set(nums))
    return ",".join(str(n) for n in nums)


# ============================================================
# 交互式输入
# ============================================================
def interactive_input():
    print("\n" + "=" * 50)
    print("手动配置 ini（只改 stopAt / saveAt / saveEvery）")
    print("=" * 50)

    # stopAt
    while True:
        raw = input("请输入 stopAt（总形状数，例如 5000）: ").strip()
        if raw.isdigit() and int(raw) > 0:
            stop_at = int(raw)
            break
        print("❌ 请输入正整数")

    # saveAt
    print("\n请输入 saveAt（多个数字用逗号分隔，例如 1000,2000,3000,4000,5000）")
    print("按回车可自动生成：从 saveEvery 到 stopAt 的等间隔数列")
    raw = input("saveAt: ").strip()

    # saveEvery
    while True:
        raw_every = input("\n请输入 saveEvery（每隔多少个形状保存一次，例如 100）: ").strip()
        if raw_every.isdigit() and int(raw_every) > 0:
            save_every = int(raw_every)
            break
        print("❌ 请输入正整数")

    # 如果 saveAt 留空，自动生成
    if not raw:
        save_at = ",".join(str(i) for i in range(save_every, stop_at + 1, save_every))
        print(f"🔧 自动生成 saveAt = {save_at}")

    return stop_at, raw, save_every


# ============================================================
# 主流程
# ============================================================
def build_ini(src_path: str, dst_path: str,
              stop_at: int, save_at: str, save_every: int):
    # 1. 读取基准
    lines = read_ini(src_path)

    # 2. 规范化 saveAt
    save_at_norm = parse_save_at(save_at)
    print(f"🔢 规范化后 saveAt = {save_at_norm}")

    # 3. 逐个修改
    print()
    lines = set_ini_value(lines, "stopAt", str(stop_at))
    lines = set_ini_value(lines, "saveAt", save_at_norm)
    lines = set_ini_value(lines, "saveEvery", str(save_every))

    # 4. 保存
    save_ini(lines, dst_path)


# ============================================================
# 入口
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="读取基准 ini，修改 stopAt/saveAt/saveEvery，保存到 runtime"
    )
    parser.add_argument("--src", default=DEFAULT_SRC,
                        help="基准 ini 文件（默认 c.ini 路径）")
    parser.add_argument("--dst", default=DEFAULT_DST,
                        help="输出 ini 路径（默认 runtime/custom.ini）")
    parser.add_argument("--stop-at", type=int, default=None,
                        help="总形状数，例如 5000")
    parser.add_argument("--save-at", type=str, default=None,
                        help="保存快照的形状数列表，例如 '1000,2000,3000'")
    parser.add_argument("--save-every", type=int, default=None,
                        help="每隔多少个形状保存一次，例如 100")

    args = parser.parse_args()

    # 如果三个参数都没传，走交互式
    if args.stop_at is None and args.save_at is None and args.save_every is None:
        stop_at, save_at, save_every = interactive_input()
    else:
        # 校验必填
        if args.stop_at is None:
            parser.error("--stop-at 是必填项（或走交互式模式）")
        if args.save_every is None:
            parser.error("--save-every 是必填项（或走交互式模式）")
        # saveAt 可留空，自动生成
        if args.save_at is None:
            save_at = ",".join(
                str(i) for i in range(args.save_every, args.stop_at + 1, args.save_every)
            )
            print(f"🔧 自动生成 saveAt = {save_at}")
        else:
            save_at = args.save_at

        stop_at = args.stop_at
        save_every = args.save_every

    build_ini(args.src, args.dst, stop_at, save_at, save_every)

    print("\n" + "=" * 50)
    print("✅ 完成")
    print("=" * 50)


if __name__ == "__main__":
    main()