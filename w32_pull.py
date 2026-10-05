"""
w32_probe.py
============
不依赖 RTTI / 特征码，直接在堆里定位 CLiveryGroup 实例。

用法：
1. 打开 FH5，进入涂装编辑器
2. 画 2-3 个形状（方便验证）
3. 运行本脚本
"""

import sys
import ctypes
import struct
import time
from ctypes import wintypes

import win32api
import win32con
import win32process


PROCESS_ALL_ACCESS = win32con.PROCESS_ALL_ACCESS

# ============================================================
# profile 参数（来自 forza-painter-fh6 game_profiles.py）
# ============================================================
LIVERY_COUNT_OFFSET = 0x5A
LAYER_TABLE_OFFSET  = 0x78
LAYER_SIZE          = 0x140     # 每个 layer blob 大小

LAYER_POSITION_OFFSET = 0x18
LAYER_SCALE_OFFSET    = 0x28
LAYER_ROTATION_OFFSET = 0x50
LAYER_COLOR_OFFSET    = 0x74
LAYER_MASK_OFFSET     = 0x78
LAYER_SHAPE_ID_OFFSET = 0x7A

MEM_COMMIT     = 0x1000
MEM_PRIVATE    = 0x20000
MEM_IMAGE      = 0x1000000
PAGE_NOACCESS  = 0x01
PAGE_GUARD     = 0x100
READABLE_WRITABLE_MASK = 0xCC


# ============================================================
# Native
# ============================================================
class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD),
    ]


class Native:
    def __init__(self, pid: int):
        self.pid = pid
        self.h_process = win32api.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not self.h_process:
            raise RuntimeError(f"OpenProcess 失败，PID={pid}，请以管理员身份运行")
        self.h_int = int(self.h_process)

        self.ReadProcessMemory = ctypes.windll.kernel32.ReadProcessMemory
        self.ReadProcessMemory.argtypes = [
            wintypes.HANDLE, wintypes.LPCVOID, wintypes.LPVOID,
            ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)
        ]
        self.ReadProcessMemory.restype = wintypes.BOOL

    def read(self, address: int, size: int) -> bytes:
        buffer = ctypes.create_string_buffer(size)
        bytes_read = ctypes.c_size_t(0)
        ok = self.ReadProcessMemory(
            self.h_int, ctypes.c_void_p(address),
            buffer, size, ctypes.byref(bytes_read)
        )
        if not ok:
            raise RuntimeError(f"ReadProcessMemory 失败 @ 0x{address:X}")
        return buffer.raw[:bytes_read.value]

    def try_read(self, address: int, size: int) -> bytes:
        try:
            return self.read(address, size)
        except RuntimeError:
            return b""

    def read_u16(self, address):
        d = self.try_read(address, 2)
        return struct.unpack("<H", d)[0] if len(d) == 2 else None

    def read_u64(self, address):
        d = self.try_read(address, 8)
        return struct.unpack("<Q", d)[0] if len(d) == 8 else None

    def read_f32(self, address):
        d = self.try_read(address, 4)
        return struct.unpack("<f", d)[0] if len(d) == 4 else None

    def close(self):
        if self.h_process:
            win32api.CloseHandle(self.h_process)
            self.h_process = None


# ============================================================
# 内存区域枚举
# ============================================================
def iter_regions(native, type_filter=None, writable_only=True):
    """枚举内存区域"""
    VirtualQueryEx = ctypes.windll.kernel32.VirtualQueryEx
    VirtualQueryEx.argtypes = [
        wintypes.HANDLE, wintypes.LPCVOID,
        ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t
    ]
    VirtualQueryEx.restype = ctypes.c_size_t

    address = 0x10000
    max_address = 0x7FFFFFFFFFFF
    mbi = MEMORY_BASIC_INFORMATION()
    mbi_size = ctypes.sizeof(mbi)

    while address < max_address:
        ret = VirtualQueryEx(native.h_int, ctypes.c_void_p(address),
                             ctypes.byref(mbi), mbi_size)
        if ret == 0:
            address += 0x10000
            continue

        base = int(mbi.BaseAddress or address)
        size = int(mbi.RegionSize)
        if size == 0:
            break

        type_ok = (type_filter is None) or (int(mbi.Type) == type_filter)

        protect = int(mbi.Protect)
        if writable_only:
            readable = (int(mbi.State) == MEM_COMMIT and
                        not (protect & PAGE_NOACCESS) and
                        not (protect & PAGE_GUARD) and
                        bool(protect & READABLE_WRITABLE_MASK))
        else:
            readable = (int(mbi.State) == MEM_COMMIT and
                        not (protect & PAGE_NOACCESS) and
                        not (protect & PAGE_GUARD))

        if readable and type_ok:
            yield base, size

        next_addr = base + size
        if next_addr <= address:
            break
        address = next_addr


def is_user_ptr(value):
    return value and 0x10000 <= value <= 0x7FFFFFFFFFFF


# ============================================================
# Layer 结构验证
# ============================================================
def valid_layer(native, layer_ptr):
    """验证一个 layer 指针是否指向有效的 layer blob"""
    if not is_user_ptr(layer_ptr):
        return False, None

    raw = native.try_read(layer_ptr, LAYER_SIZE)
    if len(raw) != LAYER_SIZE:
        return False, None

    # 检查 position / scale / rotation 是否为合理浮点数
    try:
        px = struct.unpack_from("<f", raw, LAYER_POSITION_OFFSET)[0]
        py = struct.unpack_from("<f", raw, LAYER_POSITION_OFFSET + 4)[0]
        sx = struct.unpack_from("<f", raw, LAYER_SCALE_OFFSET)[0]
        sy = struct.unpack_from("<f", raw, LAYER_SCALE_OFFSET + 4)[0]
        rot = struct.unpack_from("<f", raw, LAYER_ROTATION_OFFSET)[0]
    except struct.error:
        return False, None

    def plausible(v):
        return v == v and -100000 < v < 100000

    if not (plausible(px) and plausible(py) and
            plausible(sx) and plausible(sy) and plausible(rot)):
        return False, None

    # scale 不应该为 0
    if abs(sx) < 1e-6 and abs(sy) < 1e-6:
        return False, None

    info = {
        "ptr": layer_ptr,
        "position": (px, py),
        "scale": (sx, sy),
        "rotation": rot,
        "color": list(raw[LAYER_COLOR_OFFSET:LAYER_COLOR_OFFSET + 4]),
        "shape_id": struct.unpack_from("<H", raw, LAYER_SHAPE_ID_OFFSET)[0],
    }
    return True, info


def validate_table(native, table_addr, count):
    """验证 table 里前 count 个 layer 都有效，返回 (valid_count, samples)"""
    valid = 0
    samples = []
    for i in range(count):
        ptr = native.read_u64(table_addr + i * 8)
        if not is_user_ptr(ptr):
            break
        ok, info = valid_layer(native, ptr)
        if not ok:
            break
        valid += 1
        if len(samples) < 4:
            samples.append((i, info))
    return valid, samples


# ============================================================
# 主定位逻辑：直接搜 layer_count
# ============================================================
def locate_groups(native, layer_count):
    """
    在 MEM_PRIVATE 堆里搜 2 字节的 layer_count，
    对每个命中，向前 0x5A 拿到候选 group，验证其 table。
    """
    print(f"\n🔍 搜索 layer_count = {layer_count} (2字节小端)")
    print("=" * 60)

    pattern = struct.pack("<H", layer_count)
    candidates = []

    region_count = 0
    scanned_mb = 0
    CHUNK = 4 * 1024 * 1024

    for base, size in iter_regions(native, type_filter=MEM_PRIVATE, writable_only=True):
        region_count += 1
        offset = 0
        carry = b""

        while offset < size:
            read_size = min(CHUNK, size - offset)
            data = native.try_read(base + offset, read_size)
            if not data:
                carry = b""
                offset += read_size
                continue

            scanned_mb += len(data) / (1024 * 1024)
            scan_data = carry + data
            scan_base = base + offset - len(carry)

            start = 0
            while True:
                pos = scan_data.find(pattern, start)
                if pos == -1:
                    break
                start = pos + 1
                count_addr = scan_base + pos

                # 候选 group 地址
                group_addr = count_addr - LIVERY_COUNT_OFFSET
                if group_addr < 0x10000:
                    continue

                # 验证 group + 0x78 处是 table 指针
                table_field = group_addr + LAYER_TABLE_OFFSET
                table_addr = native.read_u64(table_field)
                if not is_user_ptr(table_addr):
                    continue

                # 验证 table 内容
                valid, samples = validate_table(native, table_addr, layer_count)
                if valid < layer_count:
                    continue

                # 再次从 group 里读 count 确认
                real_count = native.read_u16(count_addr)
                if real_count != layer_count:
                    continue

                candidates.append({
                    "group_addr": group_addr,
                    "count_addr": count_addr,
                    "table_field": table_field,
                    "table_addr": table_addr,
                    "count": real_count,
                    "samples": samples,
                })
                print(f"✅ 候选 group=0x{group_addr:X} "
                      f"count=0x{count_addr:X}({real_count}) "
                      f"table=0x{table_addr:X} 有效 layer={valid}")

            carry = scan_data[-(len(pattern) - 1):]
            offset += read_size

    print("=" * 60)
    print(f"扫描区域数: {region_count}, 扫描内存: {scanned_mb:.0f} MB")
    print(f"找到 {len(candidates)} 个候选 group")

    return candidates


# ============================================================
# 进程与模块
# ============================================================
def find_pid(name="ForzaHorizon5.exe"):
    for pid in win32process.EnumProcesses():
        try:
            h = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                False, pid)
            if not h:
                continue
            exe = win32process.GetModuleFileNameEx(h, 0)
            win32api.CloseHandle(h)
            if name.lower() in exe.lower():
                return pid, exe
        except Exception:
            continue
    return None, None


# ============================================================
# 主流程
# ============================================================
def main():
    pid, exe = find_pid("ForzaHorizon5.exe")
    if not pid:
        print("❌ 没找到 ForzaHorizon5.exe")
        return 1
    print(f"✅ 找到进程: {exe} (PID={pid})")

    # 让用户输入当前编辑器里的图层数量
    try:
        layer_count = int(input("请输入当前编辑器里的图层数量（画几个就是几）: ").strip())
    except ValueError:
        print("❌ 请输入整数")
        return 1

    native = Native(pid)
    t0 = time.time()
    try:
        candidates = locate_groups(native, layer_count)
    finally:
        native.close()

    print(f"\n耗时: {time.time() - t0:.1f}s")

    if not candidates:
        print("\n❌ 没找到匹配的 group")
        print("建议:")
        print("  1. 确认游戏停留在涂装编辑器界面")
        print("  2. 确认输入的 layer_count 和游戏里显示的一致")
        print("  3. 试试多画几个形状再跑")
        return 1

    # 打印最佳候选的详细信息
    best = candidates[0]
    print(f"\n🎯 最佳候选:")
    print(f"   group 地址:   0x{best['group_addr']:X}")
    print(f"   count 地址:   0x{best['count_addr']:X}")
    print(f"   table 指针字段: 0x{best['table_field']:X}")
    print(f"   table 地址:   0x{best['table_addr']:X}")
    print(f"   图层数量:     {best['count']}")
    print(f"\n   前几个 layer 样本:")
    for i, info in best["samples"]:
        print(f"   [{i}] ptr=0x{info['ptr']:X}")
        print(f"       position={info['position']} scale={info['scale']}")
        print(f"       rotation={info['rotation']:.2f} "
              f"color={info['color']} shape_id={info['shape_id']}")

    print("\n下一步:")
    print("  用这些地址去验证: 在 Cheat Engine 里跳到 group_addr,")
    print("  修改 count 或 layer 数据, 看游戏画面是否立即变化。")
    return 0


if __name__ == "__main__":
    sys.exit(main())