import struct
from ast_nodes import *
from parser import Parser
from lexer import tokenize_source

# ──────────────────────────────────────────────
#  Global mode (set by bits directive)
# ──────────────────────────────────────────────
CURRENT_BITS = 64

# ──────────────────────────────────────────────
#  Register encoding
# ──────────────────────────────────────────────

REG_MAP = {
    'ret': 0,   'rax': 0,   'eax': 0,   'ax': 0,    'al': 0,
    'r1':  3,   'rbx': 3,   'ebx': 3,   'bx': 3,    'bl': 3,
    'cnt': 1,   'rcx': 1,   'ecx': 1,   'cx': 1,    'cl': 1,
    'dta': 2,   'rdx': 2,   'edx': 2,   'dx': 2,    'dl': 2,
    'src': 6,   'rsi': 6,   'esi': 6,   'si': 6,
    'dst': 7,   'rdi': 7,   'edi': 7,   'di': 7,
    'r2':  8,   'r8':  8,
    'r3':  9,   'r9':  9,
    'r4':  10,  'r10': 10,
    'r5':  11,  'r11': 11,
    'r6':  12,  'r12': 12,
    'r7':  13,  'r13': 13,
    'stp': 4,   'rsp': 4,   'esp': 4,   'sp': 4,
    'sbp': 5,   'rbp': 5,   'ebp': 5,   'bp': 5,
    'cs': 100, 'ds': 101, 'es': 102, 'fs': 103, 'gs': 104, 'ss': 105,
    'm1':  -1,  'm2':  -2,
    'cr0': 200, 'cr2': 202, 'cr3': 203, 'cr4': 204,
}

FLOAT_REG_MAP = {
    'f1': 0, 'f2': 1, 'f3': 2, 'f4': 3,
    'f5': 4, 'f6': 5, 'f7': 6, 'f8': 7,
}

FLAG_MAP = {'carry': 0, 'zero': 4, 'overflow': 11}

CMP_OP_MAP = {
    '==': ('e',  'z'),
    '!=': ('ne', 'nz'),
    '>':  ('nbe', 'a'),
    '<':  ('nlt', 'l'),
    '>=': ('nb', 'ae'),
    '<=': ('nbe', 'le'),  # actually ng, but we use set-version
}


def is_reg(val):
    return isinstance(val, str) and val.lower() in REG_MAP


def is_float_reg(val):
    return isinstance(val, str) and val.lower() in FLOAT_REG_MAP


def reg_num(val):
    return REG_MAP.get(val.lower(), -1)


def float_reg_num(val):
    return FLOAT_REG_MAP.get(val.lower(), -1)


def is_memory_operand(val):
    return isinstance(val, str) and val.startswith('[') and val.endswith(']')


def parse_mem_operand(val):
    """Parse [expr] into parts: base, index, scale, displacement."""
    inner = val[1:-1].strip()
    parts = []
    current = ''
    for ch in inner:
        if ch in '+-*':
            if current.strip():
                parts.append(current.strip())
            parts.append(ch)
            current = ''
        else:
            current += ch
    if current.strip():
        parts.append(current.strip())

    base = None
    index = None
    scale = 1
    displacement = 0
    i = 0

    while i < len(parts):
        p = parts[i]
        if p == '+':
            i += 1
            continue
        elif p == '-':
            i += 1
            if i < len(parts):
                val_str = parts[i]
                if is_reg(val_str):
                    # negative register? shouldn't happen, treat as sub
                    pass
                else:
                    displacement -= parse_immediate(val_str)
            i += 1
            continue
        elif p == '*':
            i += 1
            if i < len(parts):
                scale = parse_immediate(parts[i])
            i += 1
            continue

        if is_reg(p):
            if base is None:
                base = p
            elif index is None:
                index = p
        else:
            displacement = parse_immediate(p)
        i += 1

    return base, index, scale, displacement


def parse_immediate(val):
    """Parse an immediate value (number, hex, or float) to int."""
    if isinstance(val, int):
        return val
    if not isinstance(val, str):
        return 0
    val = val.strip()
    try:
        if val.startswith('0x') or val.startswith('0X'):
            return int(val, 16)
        if '.' in val:
            return int(float(val))
        return int(val)
    except ValueError:
        return 0


def parse_float_immediate(val):
    """Parse a float immediate to IEEE 754 single-precision bytes."""
    try:
        f = float(val)
        return struct.pack('<f', f)
    except ValueError:
        return b'\x00\x00\x00\x00'


def encode_float_to_u32(val):
    """Parse float to uint32 for SSE integer move."""
    try:
        f = float(val)
        return struct.unpack('<I', struct.pack('<f', f))[0]
    except ValueError:
        return 0


# ──────────────────────────────────────────────
#  REX prefix helpers
# ──────────────────────────────────────────────

def rex_byte(w, r, x, b):
    """Generate REX prefix byte."""
    return 0x40 | (w << 3) | (r << 2) | (x << 1) | b


def needs_rex(reg_id):
    return reg_id >= 8


def reg_needs_rex(val):
    return is_reg(val) and reg_num(val) >= 8


# ──────────────────────────────────────────────
#  ModR/M + SIB encoding
# ──────────────────────────────────────────────

def modrm(mod, reg, rm):
    return ((mod & 3) << 6) | ((reg & 7) << 3) | (rm & 7)


def sib(scale, index, base):
    sc = {1: 0, 2: 1, 4: 2, 8: 3}.get(scale, 0)
    return ((sc & 3) << 6) | ((index & 7) << 3) | (base & 7)


SPECIAL_RMS = {4: 'rsp', 5: 'rbp'}


def encode_reg_reg(opcode, dst_val, src_val, w=1):
    """Encode reg, reg instruction."""
    global CURRENT_BITS
    dst_id = reg_num(dst_val)
    src_id = reg_num(src_val)
    code = bytearray()

    if CURRENT_BITS == 16:
        # 16-bit: no REX prefix, use 16-bit registers
        # For 16-bit mov: opcode is same, no REX
        code.append(opcode)
        code.append(modrm(3, src_id & 7, dst_id & 7))
        return code
    elif CURRENT_BITS == 32:
        # 32-bit: no REX prefix unless extended registers
        if needs_rex(dst_id) or needs_rex(src_id):
            r = (src_id >> 3) & 1
            b = (dst_id >> 3) & 1
            code.append(rex_byte(0, r, 0, b))
        code.append(opcode)
        code.append(modrm(3, src_id & 7, dst_id & 7))
        return code
    else:
        # 64-bit: REX.W prefix
        r = (src_id >> 3) & 1
        b = (dst_id >> 3) & 1
        if w or needs_rex(dst_id) or needs_rex(src_id):
            code.append(rex_byte(1, r, 0, b))
        code.append(opcode)
        code.append(modrm(3, src_id & 7, dst_id & 7))
        return code


def encode_reg_imm8(opcode, reg_val, imm):
    """Encode reg, imm8 (sign-extended)."""
    rid = reg_num(reg_val)
    code = bytearray()
    if needs_rex(rid):
        code.append(rex_byte(0, 0, 0, (rid >> 3) & 1))
    code.append(opcode)
    code.append(modrm(3, 0, rid & 7))
    code.append(imm & 0xFF)
    return code


def encode_reg_imm32(opcode, reg_val, imm, w=1):
    """Encode MOV reg, imm. Opcode = 0xB8 + rd. No ModR/M."""
    global CURRENT_BITS
    rid = reg_num(reg_val)
    code = bytearray()

    if CURRENT_BITS == 16:
        # 16-bit: mov reg16, imm16 (2-byte immediate, no REX)
        code.append(opcode + (rid & 7))
        code.extend(struct.pack('<H', imm & 0xFFFF))
        return code
    elif CURRENT_BITS == 32:
        # 32-bit: mov reg32, imm32 (4-byte immediate, no REX unless extended)
        b = (rid >> 3) & 1
        if b:
            code.append(rex_byte(0, 0, 0, b))
        code.append(opcode + (rid & 7))
        code.extend(struct.pack('<I', imm & 0xFFFFFFFF))
        return code
    else:
        # 64-bit: mov reg64, imm64 or mov reg32, imm32
        b = (rid >> 3) & 1
        if w and (b or needs_rex(rid)):
            code.append(rex_byte(1, 0, 0, b))
        elif not w and b:
            code.append(rex_byte(0, 0, 0, b))
        code.append(opcode + (rid & 7))
        code.extend(struct.pack('<i', imm))
        return code


def encode_reg_imm64(reg_val, imm):
    """Encode reg, imm64 (MOV with REX.W + imm64)."""
    rid = reg_num(reg_val)
    code = bytearray()
    b = (rid >> 3) & 1
    code.append(rex_byte(1, 0, 0, b))
    code.append(0xB8 + (rid & 7))
    code.extend(struct.pack('<q', imm))
    return code


def encode_mem_reg(opcode, mem_val, reg_val, direction=0, w=1):
    """
    Encode memory, reg or reg, memory.
    direction=0: reg -> mem (opcode + 0)
    direction=1: mem -> reg (opcode + 1)
    """
    base, index, scale, disp = parse_mem_operand(mem_val)
    rid = reg_num(reg_val)
    code = bytearray()

    # Determine REX
    rex_r = 0
    rex_x = 0
    rex_b = 0
    if direction == 0:
        rex_r = (rid >> 3) & 1
    else:
        rex_r = (rid >> 3) & 1

    if base and reg_num(base) >= 8:
        rex_b = 1
    if index and reg_num(index) >= 8:
        rex_x = 1

    need_rex = w or rex_r or rex_x or rex_b
    if need_rex:
        code.append(rex_byte(1 if w else 0, rex_r, rex_x, rex_b))

    code.append(opcode)

    # ModR/M + SIB + displacement
    base_id = reg_num(base) if base else -1
    index_id = reg_num(index) if index else -1

    if base is None and index is None:
        # [disp32] - absolute address
        code.append(modrm(0, rid & 7, 5))
        code.extend(struct.pack('<I', disp & 0xFFFFFFFF))
    elif index is not None:
        # SIB addressing: [base + index*scale + disp]
        idx = index_id & 7
        bas = base_id & 7 if base is not None else 5
        has_disp = disp != 0
        if has_disp and (-128 <= disp <= 127):
            mod = 1
        elif has_disp:
            mod = 2
        else:
            mod = 0
        # if base is rbp/r13 and mod=0, need mod=1 with disp8=0
        if bas == 5 and mod == 0:
            mod = 1
            disp = 0
        code.append(modrm(mod, rid & 7, 4))  # SIB follows
        code.append(sib(scale, idx, bas))
        if mod == 1:
            code.append(disp & 0xFF)
        elif mod == 2:
            code.extend(struct.pack('<i', disp))
    elif base_id & 7 == 4:
        # rsp/r12 as base needs SIB
        code.append(modrm(0, rid & 7, 4))
        code.append(sib(1, 4, 4))  # scale=1, index=rsp (none), base=rsp
    elif base_id & 7 == 5 and disp == 0:
        # rbp/r13 with no displacement needs mod=1 with disp8=0
        code.append(modrm(1, rid & 7, 5))
        code.append(0x00)
    else:
        has_disp = disp != 0
        if has_disp and (-128 <= disp <= 127):
            mod = 1
        elif has_disp:
            mod = 2
        else:
            mod = 0
        code.append(modrm(mod, rid & 7, base_id & 7))
        if mod == 1:
            code.append(disp & 0xFF)
        elif mod == 2:
            code.extend(struct.pack('<i', disp))

    return code


def encode_mem_imm(opcode, mem_val, imm, w=1):
    """Encode [mem], imm (sign-extended)."""
    base, index, scale, disp = parse_mem_operand(mem_val)
    code = bytearray()

    rex_x = 0
    rex_b = 0
    if base and reg_num(base) >= 8:
        rex_b = 1
    if index and reg_num(index) >= 8:
        rex_x = 1

    if w or rex_x or rex_b:
        code.append(rex_byte(1 if w else 0, 0, rex_x, rex_b))

    # opcode: 0xC6 for imm8, 0xC7 for imm32
    if -128 <= imm <= 127:
        code.append(0xC6 if not w else 0xC7)
    else:
        code.append(0xC7)

    base_id = reg_num(base) if base else -1
    index_id = reg_num(index) if index else -1

    if base is None and index is None:
        code.append(modrm(0, 0, 5))
        code.extend(struct.pack('<I', disp & 0xFFFFFFFF))
    elif index is not None:
        idx = index_id & 7
        bas = base_id & 7 if base is not None else 5
        has_disp = disp != 0
        if has_disp and (-128 <= disp <= 127):
            mod = 1
        elif has_disp:
            mod = 2
        else:
            mod = 0
        if bas == 5 and mod == 0:
            mod = 1
        code.append(modrm(mod, 0, 4))
        code.append(sib(scale, idx, bas))
        if mod == 1:
            code.append(disp & 0xFF)
        elif mod == 2:
            code.extend(struct.pack('<i', disp))
    elif base_id & 7 == 4:
        code.append(modrm(0, 0, 4))
        code.append(sib(1, 4, 4))
    elif base_id & 7 == 5 and disp == 0:
        code.append(modrm(1, 0, 5))
        code.append(0x00)
    else:
        has_disp = disp != 0
        if has_disp and (-128 <= disp <= 127):
            mod = 1
        elif has_disp:
            mod = 2
        else:
            mod = 0
        code.append(modrm(mod, 0, base_id & 7))
        if mod == 1:
            code.append(disp & 0xFF)
        elif mod == 2:
            code.extend(struct.pack('<i', disp))

    # immediate
    if -128 <= imm <= 127 and not w:
        code.append(imm & 0xFF)
    else:
        code.extend(struct.pack('<i', imm))
    return code


# ──────────────────────────────────────────────
#  Code generator
# ──────────────────────────────────────────────

class CodeGen:
    def __init__(self, kernel=False, base_addr=0):
        self.output = bytearray()
        self.data_section = bytearray()
        self.reserve_size = 0
        self.symbols = {}
        self.patches = []
        self.data_patches = []
        self.origin = base_addr
        self.kernel = kernel
        self.current_addr = base_addr
        self.data_symbols = {}
        self.data_offset = 0
        self.code_size = 0
        self.bits_mode = 64  # 16, 32, or 64

    def emit(self, code):
        self.output.extend(code)
        self.current_addr += len(code)

    def emit_byte(self, b):
        self.output.append(b & 0xFF)
        self.current_addr += 1

    def emit32(self, val):
        self.output.extend(struct.pack('<i', val))
        self.current_addr += 4

    def align16(self):
        while len(self.output) % 16 != 0:
            self.emit_byte(0x90)  # nop

    # ── instruction size estimation (pass 1) ──

    def estimate_instruction_size(self, node):
        """Estimate instruction size for pass 1. Returns byte count."""
        if isinstance(node, (NopeNode, HaltNode)):
            return 1
        if isinstance(node, (SyscallNode,)):
            return 2
        if isinstance(node, (IoffNode, IonNode)):
            return 1
        if isinstance(node, ReturnNode):
            return 1  # ret = 0xC3
        if isinstance(node, (RepMovsNode, RepStosNode)):
            return 2  # F3 + opcode
        if isinstance(node, IntNode):
            return 2  # CD + int number
        if isinstance(node, LabelNode):
            return 0
        if isinstance(node, ExternNode):
            return 0
        if isinstance(node, DataDefNode):
            return 0  # data handled separately
        if isinstance(node, PushNode):
            val = node.value
            if is_reg(val):
                return 2 if reg_num(val) >= 8 else 1
            return 2  # push imm8
        if isinstance(node, PopNode):
            return 2 if reg_num(node.reg) >= 8 else 1
        if isinstance(node, (IncNode, DecNode, NegNode, NotNode)):
            return 3  # REX + opcode + ModR/M
        if isinstance(node, GoNode):
            return 5  # JMP rel32
        if isinstance(node, CallNode):
            return 5  # CALL rel32
        if isinstance(node, CmpFlagNode):
            return 5  # JCXZ-like + rel32
        if isinstance(node, CmpNode):
            return 7  # cmp reg,reg + jcc rel32
        if isinstance(node, SetNode):
            return 3  # SETcc + ModR/M
        if isinstance(node, (PrNode, PwNode)):
            return 2
        if isinstance(node, MoveNode):
            return self._estimate_move_size(node)
        if isinstance(node, SwapNode):
            return 6  # xchg is 2 bytes * 2 roughly, we'll use mov via temp
        if isinstance(node, (LmaNode,)):
            return 10  # lea r64, [disp32] with REX
        if isinstance(node, (AddNode, SubNode, AndNode, OrNode, XorNode)):
            return self._estimate_alu_size(node)
        if isinstance(node, MulNode):
            return 4  # mul r/m64
        if isinstance(node, SMulNode):
            return 4
        if isinstance(node, DivNode):
            return 4
        if isinstance(node, SDivNode):
            return 4
        if isinstance(node, AwcNode):
            return 3
        if isinstance(node, SwbNode):
            return 3
        if isinstance(node, (ShlNode, ShrNode, AsrNode)):
            return 3  # D3 + ModR/M
        if isinstance(node, (RotlNode, RotrNode, RaclNode, RacrNode)):
            return 3
        if isinstance(node, (FaddNode, FsubNode, FmulNode, FdivNode)):
            return 4  # SSE: rex + 0F + opcode + ModR/M
        if isinstance(node, FmoveNode):
            return 5  # SSE mov
        if isinstance(node, FcmpNode):
            return 4
        if isinstance(node, LoopNode):
            total = 2  # loop start/end overhead
            for n in node.body:
                total += self.estimate_instruction_size(n)
            return total
        if isinstance(node, InterruptHandlerNode):
            total = 2
            for n in node.body:
                total += self.estimate_instruction_size(n)
            return total
        if isinstance(node, FnNode):
            total = 0
            for n in node.body:
                total += self.estimate_instruction_size(n)
            return total
        return 0

    def _estimate_move_size(self, node):
        dst, src = node.dst, node.src
        size = node.size

        # move [mem], imm
        if is_memory_operand(dst) and not is_reg(src):
            return 10  # worst case

        # move reg, imm
        if is_reg(dst) and not is_reg(src) and not is_memory_operand(src):
            rid = reg_num(dst)
            imm = parse_immediate(src)
            if rid >= 8:
                if -2147483648 <= imm <= 2147483647:
                    return 7  # REX + B8+rd + imm32
                return 10
            if -2147483648 <= imm <= 2147483647:
                return 5
            return 10

        # move reg, [mem]
        if is_reg(dst) and is_memory_operand(src):
            return 7

        # move [mem], reg
        if is_memory_operand(dst) and is_reg(src):
            return 7

        # move reg, reg
        if is_reg(dst) and is_reg(src):
            return 3

        return 7

    def _estimate_alu_size(self, node):
        if is_memory_operand(node.dst):
            return 7
        if is_memory_operand(node.src):
            return 7
        return 3

    # ── pass 1: collect labels and sizes ──

    def collect_labels(self, nodes):
        self.current_addr = self.origin
        self._collect_from_nodes(nodes)
        self.code_size = self.current_addr - self.origin

        # Now fix data symbol addresses to be absolute virtual addresses
        data_base = self.origin + self.code_size
        for name in list(self.data_symbols.keys()):
            self.data_symbols[name] = data_base + self.data_symbols[name]

    def build_data_section(self, data_nodes):
        """Build actual data section bytes from DataDefNode list."""
        self.data_section = bytearray()
        for node in data_nodes:
            if not isinstance(node, DataDefNode):
                continue
            val = node.value
            if isinstance(val, str) and not val.startswith('0'):
                s = val.encode('utf-8') + b'\x00'
                if node.size:
                    forced = parse_immediate(node.size)
                    if forced > len(s):
                        s = s + b'\x00' * (forced - len(s))
                    else:
                        s = s[:forced]
                self.data_section.extend(s)
            else:
                v = parse_immediate(val)
                size = 8
                if node.size and parse_immediate(node.size) > 0:
                    size = parse_immediate(node.size)
                if size == 1:
                    self.data_section.append(v & 0xFF)
                elif size == 2:
                    self.data_section.extend(struct.pack('<H', v & 0xFFFF))
                elif size == 4:
                    self.data_section.extend(struct.pack('<I', v & 0xFFFFFFFF))
                else:
                    self.data_section.extend(struct.pack('<Q', v & 0xFFFFFFFFFFFFFFFF))

    def _collect_from_nodes(self, nodes):
        for node in nodes:
            self._collect_from_node(node)

    def _collect_from_node(self, node):
        if isinstance(node, OriginNode):
            self.origin = parse_immediate(node.address)
            self.current_addr = self.origin
        elif isinstance(node, BitsNode):
            global CURRENT_BITS
            CURRENT_BITS = node.mode
        elif isinstance(node, DataByteNode):
            self.current_addr += len(node.values)
        elif isinstance(node, DataWordNode):
            self.current_addr += len(node.values) * 2
        elif isinstance(node, DataDwordNode):
            self.current_addr += len(node.values) * 4
        elif isinstance(node, TimesNode):
            count = parse_immediate(node.count)
            self.current_addr += count
        elif isinstance(node, ModuleNode):
            if node.kind == 'data':
                for item in node.body:
                    if isinstance(item, DataDefNode):
                        self._collect_data(item)
            elif node.kind == 'reserve':
                for item in node.body:
                    if isinstance(item, DataDefNode):
                        size = self._data_size(item)
                        self.data_symbols[item.name] = self.data_offset
                        self.data_offset += size
                        self.reserve_size += size
            elif node.kind == 'code':
                for item in node.body:
                    self._collect_from_node(item)
        elif isinstance(node, FnNode):
            self.symbols[node.name] = self.current_addr
            for item in node.body:
                self._collect_from_node(item)
        elif isinstance(node, LoopNode):
            for item in node.body:
                self._collect_from_node(item)
        elif isinstance(node, InterruptHandlerNode):
            for item in node.body:
                self._collect_from_node(item)
        elif isinstance(node, LabelNode):
            self.symbols[node.name] = self.current_addr
        elif isinstance(node, ExternNode):
            pass
        else:
            size = self.estimate_instruction_size(node)
            self.current_addr += size

    def _collect_data(self, node):
        """Collect data entry size (actual bytes generated later after code size is known)."""
        name = node.name
        size = self._data_size(node)
        # store as offset for now; actual address = origin + code_size + offset
        self.data_symbols[name] = self.data_offset
        self.data_offset += size

    def _data_size(self, node):
        if isinstance(node.value, str) and not node.value.startswith('0'):
            s = node.value.encode('utf-8') + b'\x00'
            if node.size and parse_immediate(node.size) > 0:
                forced = parse_immediate(node.size)
                return max(forced, len(s))
            return len(s)
        if node.size and parse_immediate(node.size) > 0:
            return parse_immediate(node.size)
        return 8

    # ── pass 2: emit code ──

    def emit_code(self, nodes):
        self.output = bytearray()
        self.current_addr = self.origin
        self._emit_nodes(nodes)

    def _emit_nodes(self, nodes):
        for node in nodes:
            self._emit_node(node)

    def _emit_node(self, node):
        if isinstance(node, OriginNode):
            self.origin = parse_immediate(node.address)
            self.current_addr = self.origin
        elif isinstance(node, BitsNode):
            self.bits_mode = node.mode
            global CURRENT_BITS
            CURRENT_BITS = node.mode
        elif isinstance(node, DataByteNode):
            for v in node.values:
                self.emit_byte(parse_immediate(v))
        elif isinstance(node, DataWordNode):
            for v in node.values:
                self.output.extend(struct.pack('<H', parse_immediate(v) & 0xFFFF))
                self.current_addr += 2
        elif isinstance(node, DataDwordNode):
            for v in node.values:
                self.output.extend(struct.pack('<I', parse_immediate(v) & 0xFFFFFFFF))
                self.current_addr += 4
        elif isinstance(node, TimesNode):
            count = parse_immediate(node.count)
            val = parse_immediate(node.values[0]) if node.values else 0
            for _ in range(count):
                self.emit_byte(val)
        elif isinstance(node, ModuleNode):
            if node.kind == 'code':
                for item in node.body:
                    self._emit_node(item)
        elif isinstance(node, FnNode):
            for item in node.body:
                self._emit_node(item)
        elif isinstance(node, LoopNode):
            for item in node.body:
                self._emit_node(item)
        elif isinstance(node, InterruptHandlerNode):
            for item in node.body:
                self._emit_node(item)
        elif isinstance(node, LabelNode):
            self.symbols[node.name] = self.current_addr
        elif isinstance(node, ExternNode):
            pass
        else:
            code = self._encode_instruction(node)
            if code:
                self.emit(code)

    def _encode_instruction(self, node):
        if isinstance(node, NopeNode):
            return b'\x90'
        if isinstance(node, HaltNode):
            return b'\xF4'  # HLT
        if isinstance(node, SyscallNode):
            return b'\x0F\x05'
        if isinstance(node, IoffNode):
            return b'\xFA'  # CLI
        if isinstance(node, IonNode):
            return b'\xFB'  # STI
        if isinstance(node, RetiNode):
            return b'\xCF'  # IRET
        if isinstance(node, ReturnNode):
            return b'\xC3'
        if isinstance(node, IntNode):
            num = parse_immediate(node.number)
            return bytes([0xCD, num & 0xFF])
        if isinstance(node, RepMovsNode):
            return b'\xF3\xA4'
        if isinstance(node, RepStosNode):
            return b'\xF3\xAA'
        if isinstance(node, LabelNode):
            return b''
        if isinstance(node, ExternNode):
            return b''
        if isinstance(node, DataDefNode):
            return b''
        if isinstance(node, PushNode):
            return self._encode_push(node)
        if isinstance(node, PopNode):
            return self._encode_pop(node)
        if isinstance(node, MoveNode):
            return self._encode_move(node)
        if isinstance(node, LmaNode):
            return self._encode_lma(node)
        if isinstance(node, SwapNode):
            return self._encode_swap(node)
        if isinstance(node, (AddNode, SubNode, AndNode, OrNode, XorNode)):
            return self._encode_alu(node)
        if isinstance(node, MulNode):
            return self._encode_mul(node, signed=False)
        if isinstance(node, SMulNode):
            return self._encode_mul(node, signed=True)
        if isinstance(node, DivNode):
            return self._encode_div(node, signed=False)
        if isinstance(node, SDivNode):
            return self._encode_div(node, signed=True)
        if isinstance(node, (AwcNode, SwbNode)):
            return self._encode_awc_swb(node)
        if isinstance(node, (IncNode, DecNode)):
            return self._encode_inc_dec(node)
        if isinstance(node, NegNode):
            return self._encode_neg(node)
        if isinstance(node, NotNode):
            return self._encode_not(node)
        if isinstance(node, (ShlNode, ShrNode, AsrNode)):
            return self._encode_shift(node)
        if isinstance(node, (RotlNode, RotrNode)):
            return self._encode_rotate(node)
        if isinstance(node, (RaclNode, RacrNode)):
            return self._encode_rotate_carry(node)
        if isinstance(node, GoNode):
            return self._encode_jump(node)
        if isinstance(node, CallNode):
            return self._encode_call(node)
        if isinstance(node, CmpNode):
            return self._encode_cmp(node)
        if isinstance(node, CmpFlagNode):
            return self._encode_cmp_flag(node)
        if isinstance(node, SetNode):
            return self._encode_set(node)
        if isinstance(node, (PrNode, PwNode)):
            return self._encode_port_io(node)
        if isinstance(node, (FaddNode, FsubNode, FmulNode, FdivNode)):
            return self._encode_float_binop(node)
        if isinstance(node, FmoveNode):
            return self._encode_float_move(node)
        if isinstance(node, FcmpNode):
            return self._encode_float_cmp(node)
        if isinstance(node, (MoveSxNode, MoveZxNode)):
            return self._encode_extend(node)
        return b''

    # ── move encoding ──

    def _encode_move(self, node):
        dst, src, size = node.dst, node.src, node.size

        # [mem], imm
        if is_memory_operand(dst) and not is_reg(src):
            imm = parse_immediate(src)
            if size:
                sz = int(size)
                if sz == 1:
                    return encode_mem_imm(0xC6, dst, imm, w=0)
                elif sz == 2:
                    code = bytearray()
                    code.extend(self._rex_w_for(dst, src))
                    code.append(0xC7)
                    # simplified: use modrm with 32-bit immediate
                    return bytes(code) if code else encode_mem_imm(0xC7, dst, imm, w=1)
                elif sz == 4:
                    return encode_mem_imm(0xC7, dst, imm, w=0)
                else:
                    return encode_mem_imm(0xC7, dst, imm, w=1)
            # default: try to fit in imm32
            if -2147483648 <= imm <= 2147483647:
                return encode_mem_imm(0xC7, dst, imm, w=1)
            # 64-bit immediate to memory: mov rax, imm64 then mov [mem], rax
            code = bytearray()
            code.extend(encode_reg_imm64('ret', imm))
            code.extend(encode_mem_reg(0x89, dst, 'ret', direction=0, w=1))
            return code

        # reg, imm
        if is_reg(dst) and not is_reg(src) and not is_memory_operand(src):
            imm = parse_immediate(src)
            rid = reg_num(dst)
            if size:
                sz = int(size)
                if sz == 1:
                    return encode_reg_imm8(0xB0, dst, imm)
                elif sz == 2:
                    code = bytearray()
                    code.append(rex_byte(0, 0, 0, (rid >> 3) & 1))
                    code.append(0x66)
                    code.append(0xB8 + (rid & 7))
                    code.extend(struct.pack('<H', imm & 0xFFFF))
                    return code
                elif sz == 4:
                    return encode_reg_imm32(0xB8, dst, imm, w=0)
                else:
                    return encode_reg_imm64(dst, imm)
            # default: always use 32-bit mov (zero-extends to 64-bit)
            return encode_reg_imm32(0xB8, dst, imm, w=0)
            # default: fit in smallest
            if -128 <= imm <= 127:
                return encode_reg_imm8(0xB0, dst, imm)
            if -2147483648 <= imm <= 2147483647:
                return encode_reg_imm32(0xB8, dst, imm, w=0)
            return encode_reg_imm64(dst, imm)

        # reg, [mem]
        if is_reg(dst) and is_memory_operand(src):
            return encode_mem_reg(0x8B, src, dst, direction=1, w=1)

        # [mem], reg
        if is_memory_operand(dst) and is_reg(src):
            return encode_mem_reg(0x89, dst, src, direction=0, w=1)

        # reg, reg
        if is_reg(dst) and is_reg(src):
            if size:
                sz = int(size)
                if sz == 1:
                    return encode_reg_reg(0x8A, dst, src, w=0)
                elif sz == 2:
                    code = bytearray()
                    code.append(0x66)
                    code.append(rex_byte(0, 0, 0, 0))
                    code.append(0x89)
                    code.append(modrm(3, reg_num(src) & 7, reg_num(dst) & 7))
                    return code
                elif sz == 4:
                    return encode_reg_reg(0x89, dst, src, w=0)
            # default: always 64-bit for SPINE-64
            return encode_reg_reg(0x89, dst, src, w=1)

        return b'\x90'

    def _rex_w_for(self, *vals):
        code = bytearray()
        need = False
        r, x, b = 0, 0, 0
        for v in vals:
            if is_reg(v):
                rid = reg_num(v)
                if rid >= 8:
                    need = True
        if need:
            code.append(rex_byte(1, 0, 0, 0))
        return code

    # ── lma (lea) encoding ──

    def _encode_lma(self, node):
        global CURRENT_BITS
        dst, src = node.dst, node.src
        if is_reg(dst) and is_memory_operand(src):
            return encode_mem_reg(0x8D, src, dst, direction=1, w=1)
        # Symbol reference: MOV reg, imm (patched later)
        if is_reg(dst) and not is_reg(src) and not is_memory_operand(src):
            rid = reg_num(dst)
            code = bytearray()
            if CURRENT_BITS == 16:
                code.append(0xB8 + (rid & 7))
                self.data_patches.append((len(self.output) + len(code), src))
                code.extend(struct.pack('<H', 0))
            elif CURRENT_BITS == 32:
                b = (rid >> 3) & 1
                if b:
                    code.append(rex_byte(0, 0, 0, b))
                code.append(0xB8 + (rid & 7))
                self.data_patches.append((len(self.output) + len(code), src))
                code.extend(struct.pack('<I', 0))
            else:
                code.append(rex_byte(1, 0, 0, (rid >> 3) & 1))
                code.append(0xB8 + (rid & 7))
                self.data_patches.append((len(self.output) + len(code), src))
                code.extend(struct.pack('<q', 0))
            return code
        if is_reg(dst) and is_reg(src):
            return encode_reg_reg(0x89, dst, src, w=1)
        return b''

    # ── swap encoding ──

    def _encode_swap(self, node):
        # XCHG r64, r64
        a, b = node.dst, node.src
        if is_reg(a) and is_reg(b):
            aid = reg_num(a)
            bid = reg_num(b)
            code = bytearray()
            # xchg eax, eax is nop, use the one with rax if possible
            if aid == 0 or bid == 0:
                other = bid if aid == 0 else aid
                code.append(rex_byte(1, 0, 0, (other >> 3) & 1))
                code.append(0x87)
                code.append(modrm(3, other & 7, 0))
            else:
                code.append(rex_byte(1, 0, 0, (aid >> 3) & 1))
                code.append(0x87)
                code.append(modrm(3, aid & 7, bid & 7))
            return code
        return b''

    # ── ALU encoding ──

    def _encode_alu(self, node):
        opcodes = {
            'add': 0x01, 'sub': 0x29,
            'and': 0x21, 'or': 0x09, 'xor': 0x31,
        }
        opcode = opcodes[type(node).__name__.lower().replace('node', '')]

        if isinstance(node, AddNode): opcode = 0x01
        elif isinstance(node, SubNode): opcode = 0x29
        elif isinstance(node, AndNode): opcode = 0x21
        elif isinstance(node, OrNode): opcode = 0x09
        elif isinstance(node, XorNode): opcode = 0x31

        dst, src = node.dst, node.src

        # reg, imm
        if is_reg(dst) and not is_reg(src) and not is_memory_operand(src):
            imm = parse_immediate(src)
            alu_op = {
                0x01: 0xC0,  # ADD
                0x29: 0xE8,  # SUB
                0x21: 0xE0,  # AND
                0x09: 0xC8,  # OR
                0x31: 0xF0,  # XOR
            }.get(opcode, 0xC0)
            if -128 <= imm <= 127:
                return encode_reg_imm8(alu_op, dst, imm)
            return encode_reg_imm32(alu_op, dst, imm, w=0)

        # reg, reg
        if is_reg(dst) and is_reg(src):
            return encode_reg_reg(opcode, dst, src, w=1)

        # [mem], reg
        if is_memory_operand(dst) and is_reg(src):
            return encode_mem_reg(opcode, dst, src, direction=0, w=1)

        # reg, [mem]
        if is_reg(dst) and is_memory_operand(src):
            return encode_mem_reg(opcode + 1, src, dst, direction=1, w=1)

        return b''

    # ── mul encoding ──

    def _encode_mul(self, node, signed=False):
        dst, src = node.dst, node.src
        # IMUL r64, r/m64 (3-operand form)
        if is_reg(dst) and is_reg(src):
            did = reg_num(dst)
            sid = reg_num(src)
            code = bytearray()
            rex = rex_byte(1, (did >> 3) & 1, 0, (sid >> 3) & 1)
            code.append(rex)
            if signed:
                code.append(0x0F)  # IMUL r64, r/m64
                code.append(0xAF)
            else:
                # MUL: one operand form, result in RDX:RAX
                # for two-operand we use IMUL
                code.append(0x0F)
                code.append(0xAF)
            code.append(modrm(3, did & 7, sid & 7))
            return code
        if is_reg(dst) and not is_reg(src):
            imm = parse_immediate(src)
            did = reg_num(dst)
            code = bytearray()
            code.append(rex_byte(1, (did >> 3) & 1, 0, 0))
            if -128 <= imm <= 127:
                code.append(0x6B)
                code.append(modrm(3, did & 7, did & 7))
                code.append(imm & 0xFF)
            else:
                code.append(0x69)
                code.append(modrm(3, did & 7, did & 7))
                code.extend(struct.pack('<i', imm))
            return code
        return b''

    # ── div encoding ──

    def _encode_div(self, node, signed=False):
        src = node.src
        # DIV r/m64: RDX:RAX / src -> RAX quotient, RDX remainder
        # we zero rdx first for unsigned, use cqo for signed
        code = bytearray()
        if signed:
            # xor rdx, rdx to zero it (or cqo for sign extend)
            code.extend(encode_reg_reg(0x31, 'dta', 'dta', w=1))
        else:
            code.extend(encode_reg_reg(0x31, 'dta', 'dta', w=1))

        sid = reg_num(src)
        if signed:
            code.append(rex_byte(1, 0, 0, (sid >> 3) & 1))
            code.append(0xF7)
            code.append(modrm(3, 7, sid & 7))  # /7 = IDIV
        else:
            code.append(rex_byte(1, 0, 0, (sid >> 3) & 1))
            code.append(0xF7)
            code.append(modrm(3, 6, sid & 7))  # /6 = DIV
        return code

    # ── awc / swb ──

    def _encode_awc_swb(self, node):
        # ADD/SUB with carry: dst = dst + src + CF
        dst, src = node.dst, node.src
        is_awc = isinstance(node, AwcNode)
        code = bytearray()
        if is_reg(dst) and is_reg(src):
            did = reg_num(dst)
            sid = reg_num(src)
            # ADC r64, r/m64
            code.append(rex_byte(1, (did >> 3) & 1, 0, (sid >> 3) & 1))
            code.append(0x11 if is_awc else 0x19)  # ADC or SBB
            code.append(modrm(3, did & 7, sid & 7))
            return code
        return b''

    # ── inc/dec ──

    def _encode_inc_dec(self, node):
        reg = node.reg
        rid = reg_num(reg)
        is_dec = isinstance(node, DecNode)
        # INC/DEC r/m64: REX.W + FF /0 or /1
        code = bytearray()
        code.append(rex_byte(1, 0, 0, (rid >> 3) & 1))
        code.append(0xFF)
        code.append(modrm(3, 1 if is_dec else 0, rid & 7))
        return code

    # ── neg ──

    def _encode_neg(self, node):
        rid = reg_num(node.reg)
        code = bytearray()
        code.append(rex_byte(1, 0, 0, (rid >> 3) & 1))
        code.append(0xF7)
        code.append(modrm(3, 3, rid & 7))  # /3 = NEG
        return code

    # ── not ──

    def _encode_not(self, node):
        rid = reg_num(node.reg)
        code = bytearray()
        code.append(rex_byte(1, 0, 0, (rid >> 3) & 1))
        code.append(0xF7)
        code.append(modrm(3, 2, rid & 7))  # /2 = NOT
        return code

    # ── shift ──

    def _encode_shift(self, node):
        reg = node.src  # shift amount in src
        rid = reg_num(node.dst)
        if isinstance(node, ShlNode):
            op = 4  # /4 = SHL
        elif isinstance(node, ShrNode):
            op = 5  # /5 = SHR
        else:  # AsrNode
            op = 7  # /7 = SAR

        # shift by CL
        code = bytearray()
        code.append(rex_byte(1, 0, 0, (rid >> 3) & 1))
        code.append(0xD3)
        code.append(modrm(3, op, rid & 7))
        return code

    # ── rotate ──

    def _encode_rotate(self, node):
        rid = reg_num(node.dst)
        if isinstance(node, RotlNode):
            op = 0  # /0 = ROL
        else:
            op = 1  # /1 = ROR
        code = bytearray()
        code.append(rex_byte(1, 0, 0, (rid >> 3) & 1))
        code.append(0xD3)
        code.append(modrm(3, op, rid & 7))
        return code

    def _encode_rotate_carry(self, node):
        rid = reg_num(node.dst)
        if isinstance(node, RaclNode):
            op = 2  # /2 = RCL
        else:
            op = 3  # /3 = RCR
        code = bytearray()
        code.append(rex_byte(1, 0, 0, (rid >> 3) & 1))
        code.append(0xD3)
        code.append(modrm(3, op, rid & 7))
        return code

    # ── push/pop ──

    def _encode_push(self, node):
        val = node.value
        if is_reg(val):
            rid = reg_num(val)
            code = bytearray()
            # Always use REX.W for 64-bit push
            b = (rid >> 3) & 1
            code.append(rex_byte(1, 0, 0, b))
            code.append(0x50 + (rid & 7))
            return code
        imm = parse_immediate(val)
        if -128 <= imm <= 127:
            return bytes([0x6A, imm & 0xFF])
        return bytes([0x68]) + struct.pack('<i', imm)

    def _encode_pop(self, node):
        rid = reg_num(node.reg)
        code = bytearray()
        # Always use REX.W for 64-bit pop
        b = (rid >> 3) & 1
        code.append(rex_byte(1, 0, 0, b))
        code.append(0x58 + (rid & 7))
        return code

    # ── jump / call ──

    def _encode_jump(self, node):
        # JMP rel32 (we'll patch the offset later)
        code = bytearray()
        code.append(0xE9)
        self.patches.append((len(self.output) + len(code), node.label))
        code.extend(struct.pack('<i', 0))  # placeholder
        return code

    def _encode_call(self, node):
        # CALL rel32
        code = bytearray()
        code.append(0xE8)
        self.patches.append((len(self.output) + len(code), node.name))
        code.extend(struct.pack('<i', 0))  # placeholder
        return code

    # ── cmp ──

    def _encode_cmp(self, node):
        left, right, label, op = node.left, node.right, node.label, node.op
        code = bytearray()

        if is_reg(left) and is_reg(right):
            # CMP r64, r64
            lid = reg_num(left)
            rid = reg_num(right)
            code.append(rex_byte(1, (lid >> 3) & 1, 0, (rid >> 3) & 1))
            code.append(0x39)  # CMP r/m64, r64
            code.append(modrm(3, rid & 7, lid & 7))
        elif is_reg(left) and not is_reg(right):
            imm = parse_immediate(right)
            lid = reg_num(left)
            code.append(rex_byte(1, 0, 0, (lid >> 3) & 1))
            if -128 <= imm <= 127:
                code.append(0x83)
                code.append(modrm(3, 7, lid & 7))
                code.append(imm & 0xFF)
            else:
                code.append(0x81)
                code.append(modrm(3, 7, lid & 7))
                code.extend(struct.pack('<i', imm))
        else:
            return b'\x90'

        # conditional jump
        jcc = self._get_jcc(op)
        code.append(jcc)
        self.patches.append((len(self.output) + len(code), label))
        code.extend(struct.pack('<i', 0))
        return code

    def _get_jcc(self, op):
        """Get Jcc opcode for comparison operator."""
        jcc_map = {
            '==': 0x84, '!=': 0x85,
            '>': 0x8F, '<': 0x8C,
            '>=': 0x8D, '<=': 0x8E,
        }
        return jcc_map.get(op, 0x84)

    def _encode_cmp_flag(self, node):
        # CMP flag go label -> test flag and jnz
        flag_id = FLAG_MAP.get(node.flag, 0)
        code = bytearray()

        # For carry: JB (0x82)
        # For zero: JZ (0x84)
        # For overflow: JO (0x80)
        flag_jcc = {0: 0x82, 4: 0x84, 11: 0x80}
        jcc = flag_jcc.get(flag_id, 0x84)

        code.append(jcc)
        self.patches.append((len(self.output) + len(code), node.label))
        code.extend(struct.pack('<i', 0))
        return code

    # ── set ──

    def _encode_set(self, node):
        rid = reg_num(node.reg)
        flag_id = FLAG_MAP.get(node.flag, 0)
        set_cc = {
            0: 0x92,   # SETC
            4: 0x94,   # SETZ
            11: 0x90,  # SETO
        }
        code = bytearray()
        code.append(rex_byte(1, 0, 0, (rid >> 3) & 1))
        code.append(0x0F)
        code.append(set_cc.get(flag_id, 0x94))
        code.append(modrm(3, 0, rid & 7))
        return code

    # ── port I/O ──

    def _encode_port_io(self, node):
        if isinstance(node, PrNode):
            # IN AL, imm8
            port = parse_immediate(node.port)
            rid = reg_num(node.dst)
            code = bytearray()
            if rid != 0:  # not AL
                code.extend(encode_reg_reg(0x88, node.dst, 'dta', w=0))
            code.append(0xE4 if port <= 0xFF else 0xE5)
            code.append(port & 0xFF)
            return code
        else:  # Pw
            port = parse_immediate(node.port)
            rid = reg_num(node.src)
            code = bytearray()
            if rid != 0:
                code.extend(encode_reg_reg(0x88, 'dta', node.src, w=0))
            code.append(0xE6 if port <= 0xFF else 0xE7)
            code.append(port & 0xFF)
            return code

    # ── SSE float operations ──

    def _encode_float_binop(self, node):
        dst_freg = float_reg_num(node.dst)
        src_freg = float_reg_num(node.src)
        if dst_freg < 0 or src_freg < 0:
            return b''

        sse_ops = {
            'FaddNode': 0x58,
            'FsubNode': 0x5C,
            'FmulNode': 0x59,
            'FdivNode': 0x5E,
        }
        opcode2 = sse_ops.get(type(node).__name__, 0x58)

        code = bytearray()
        code.append(0xF3)
        code.append(0x0F)
        code.append(opcode2)
        code.append(modrm(3, dst_freg, src_freg))
        return code

    def _encode_float_move(self, node):
        dst_freg = float_reg_num(node.dst)
        if dst_freg < 0:
            return b''

        src = node.src
        # reg -> freg: MOVSS xmm, r/m32
        if is_reg(src):
            sid = reg_num(src)
            code = bytearray()
            code.append(0xF3)
            code.append(0x0F)
            code.append(0x10)
            code.append(modrm(3, dst_freg, sid & 7))
            return code

        # imm -> freg: MOVD xmm, r/m32
        imm = encode_float_to_u32(src)
        code = bytearray()
        code.append(0x66)
        code.append(0x0F)
        code.append(0x6E)
        code.append(modrm(3, dst_freg, 0))
        code.extend(struct.pack('<I', imm))
        return code

    def _encode_float_cmp(self, node):
        dst_freg = float_reg_num(node.dst)
        src_freg = float_reg_num(node.src)
        if dst_freg < 0 or src_freg < 0:
            return b''
        code = bytearray()
        code.append(0xF3)
        code.append(0x0F)
        code.append(0xC2)
        code.append(modrm(3, dst_freg, src_freg))
        code.append(0x00)  # EQ
        return code

    # ── extend (movesx / movezx) ──

    def _encode_extend(self, node):
        dst, src = node.dst, node.src
        is_signed = isinstance(node, MoveSxNode)
        if is_reg(dst) and is_reg(src):
            did = reg_num(dst)
            sid = reg_num(src)
            code = bytearray()
            if is_signed:
                # MOVSX r64, r/m32
                code.append(rex_byte(1, (did >> 3) & 1, 0, (sid >> 3) & 1))
                code.append(0x63)
            else:
                # MOVZX r64, r/m32
                code.append(rex_byte(1, (did >> 3) & 1, 0, (sid >> 3) & 1))
                code.append(0x0F)
                code.append(0xB7)
            code.append(modrm(3, did & 7, sid & 7))
            return code
        return b''

    # ── patch labels ──

    def patch_labels(self):
        # Patch code labels (relative jumps/calls)
        for offset, label in self.patches:
            if label in self.symbols:
                target = self.symbols[label]
                current = self.origin + offset + 4
                disp = target - current
                struct.pack_into('<i', self.output, offset, disp)
            else:
                print(f"warning: undefined label '{label}'")
        # Patch data symbol references (absolute addresses)
        for offset, symbol in self.data_patches:
            if symbol in self.symbols:
                addr = self.symbols[symbol]
                struct.pack_into('<q', self.output, offset, addr)
            else:
                print(f"warning: undefined symbol '{symbol}'")


# ──────────────────────────────────────────────
#  ELF64 output
# ──────────────────────────────────────────────

def create_elf64(code_bytes, data_bytes, reserve_size, base_addr=0x400000):
    """Create a minimal ELF64 executable."""
    elf = bytearray()

    e_entry = base_addr
    e_phoff = 64
    p_filesz = len(code_bytes) + len(data_bytes)
    p_memsz = p_filesz + reserve_size
    # Section headers go after program header + code + data (set to 0 = no sections)
    e_shoff_val = 0

    # ELF Header (64 bytes)
    elf.extend(b'\x7fELF')
    elf.append(2)            # 64-bit
    elf.append(1)            # little endian
    elf.append(1)            # ELF version
    elf.append(0)            # OS/ABI
    elf.extend(b'\x00' * 8)  # padding
    elf.extend(struct.pack('<H', 2))    # ET_EXEC
    elf.extend(struct.pack('<H', 0x3E)) # AMD64
    elf.extend(struct.pack('<I', 1))    # version
    elf.extend(struct.pack('<Q', e_entry))  # entry
    elf.extend(struct.pack('<Q', e_phoff))  # phoff
    elf.extend(struct.pack('<Q', e_shoff_val))  # shoff (0 if no sections)
    elf.extend(struct.pack('<I', 0))     # flags
    elf.extend(struct.pack('<H', 64))    # ehsize
    elf.extend(struct.pack('<H', 56))    # phentsize
    elf.extend(struct.pack('<H', 1))     # phnum
    elf.extend(struct.pack('<H', 64))    # shentsize
    elf.extend(struct.pack('<H', 0))     # shnum (no section headers needed)
    elf.extend(struct.pack('<H', 0))     # shstrndx

    # Program header (56 bytes) - single LOAD segment for everything
    p_offset = 0
    p_vaddr = base_addr

    elf.extend(struct.pack('<I', 1))     # PT_LOAD
    elf.extend(struct.pack('<I', 7))     # PF_R | PF_W | PF_X
    elf.extend(struct.pack('<Q', p_offset))
    elf.extend(struct.pack('<Q', p_vaddr))
    elf.extend(struct.pack('<Q', p_vaddr))  # p_paddr
    elf.extend(struct.pack('<Q', p_filesz))
    elf.extend(struct.pack('<Q', p_memsz))
    elf.extend(struct.pack('<Q', 0x1000))  # align

    # Code + Data
    elf.extend(code_bytes)
    elf.extend(data_bytes)
    # BSS reserve is zero-filled by memsz > filesz
    if reserve_size > 0:
        elf.extend(b'\x00' * reserve_size)

    return bytes(elf)


# ──────────────────────────────────────────────
#  Assembler entry point
# ──────────────────────────────────────────────

def assemble(source, output_path=None, format='elf', kernel=False, base_addr=0x400000):
    """Assemble SPINE-64 source to binary."""
    from parser import Parser
    from lexer import tokenize_source

    tokens = tokenize_source(source)
    parser = Parser(tokens)
    ast = parser.parse()

    # Determine origin
    origin = base_addr
    for node in ast:
        if isinstance(node, OriginNode):
            origin = parse_immediate(node.address)
            break

    is_bootloader = (format == 'bin') or (format != 'elf' and origin == 0x7C00)

    # Collect data nodes for separate processing
    data_nodes = []
    for node in ast:
        if isinstance(node, ModuleNode) and node.kind == 'data':
            for item in node.body:
                if isinstance(item, DataDefNode):
                    data_nodes.append(item)

    gen = CodeGen(kernel=kernel, base_addr=origin)

    # Pass 1: collect labels and sizes (computes code_size)
    gen.collect_labels(ast)

    # Build data section (needs code_size for correct addresses)
    gen.build_data_section(data_nodes)

    # Pass 2: emit code
    gen.output = bytearray()
    gen.current_addr = origin
    gen.emit_code(ast)

    # Patch labels (including data symbols)
    for name, addr in gen.data_symbols.items():
        gen.symbols[name] = addr
    gen.patch_labels()

    # For flat binary: embed data after code
    if is_bootloader or format == 'bin':
        gen.output.extend(gen.data_section)
        # Pad to 510 bytes for boot sector, add boot signature
        while len(gen.output) < 510:
            gen.output.append(0x90)
        gen.output.extend(b'\x55\xAA')  # boot signature
        result = bytes(gen.output)
    else:
        result = create_elf64(
            bytes(gen.output),
            bytes(gen.data_section),
            gen.reserve_size,
            base_addr
        )

    if output_path:
        with open(output_path, 'wb') as f:
            f.write(result)
        print(f"assembled {len(gen.output)} bytes of code + {len(gen.data_section)} bytes data -> {output_path}")

    return result


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print("usage: python codegen.py <source.tsm> [output] [--bin]")
        sys.exit(1)

    path = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('-') else path.rsplit('.', 1)[0]
    fmt = 'bin' if '--bin' in sys.argv else 'elf'

    with open(path) as f:
        source = f.read()

    result = assemble(source, output_path=out, format=fmt)
    print(f"output: {len(result)} bytes")
