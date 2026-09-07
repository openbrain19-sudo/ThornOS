from parser import *
from lexer import tokenize
import os
import subprocess
import tempfile


class Compiler:
    def __init__(self):
        self.assembly = []
        self.data = []
        self.reserve = []
        self.string_counter = 0
        self.label_counter = 0
        self.functions = {}  # name -> {params, label}
        self.globals = {}  # name -> 'stack_offset'
        self.stack_offset = 0
        self.in_function = False

    def new_label(self, prefix='L'):
        self.label_counter += 1
        return f'{prefix}_{self.label_counter}'

    def add_string(self, s):
        name = f'str_{self.string_counter}'
        self.string_counter += 1
        self.data.append((name, s))
        return name

    def emit(self, line):
        self.assembly.append(line)

    def compile(self, program):
        # first pass: find all tasks
        for stmt in program.body:
            if isinstance(stmt, TaskDef):
                self.functions[stmt.name] = {
                    'params': stmt.params,
                    'label': stmt.name,
                }

        # generate reserve section (needed for stack)
        reserve_lines = ['module reserve', '    _stack 16384', '']

        # generate code section (this populates self.data)
        code_lines = ['module code']
        self.assembly = code_lines

        for stmt in program.body:
            if isinstance(stmt, TaskDef):
                self.compile_task(stmt)

        has_start = any(isinstance(s, TaskDef) and s.name == 'start' for s in program.body)
        if has_start:
            self.assembly.append('')
            self.assembly.append('    fn global _start')
            self.assembly.append('    start')
            self.assembly.append('        call start')
            self.assembly.append('        move ret 0')
            self.assembly.append('        syscall')
            self.assembly.append('    end')

        top_level = [s for s in program.body if not isinstance(s, TaskDef) and not isinstance(s, NeedStmt)]
        if top_level and not has_start:
            self.assembly.append('')
            self.assembly.append('    fn global _start')
            self.assembly.append('    start')
            for stmt in top_level:
                self.compile_stmt(stmt)
            self.assembly.append('        move ret 0')
            self.assembly.append('        syscall')
            self.assembly.append('    end')

        # NOW generate data section (strings collected during code gen)
        data_lines = ['module data']
        for name, s in self.data:
            escaped = s.replace('\\', '\\\\').replace('"', '\\"')
            data_lines.append(f'    {name} "{escaped}"')
        data_lines.append('')

        # combine: data + reserve + code
        return '\n'.join(data_lines + reserve_lines + self.assembly)

    def compile_task(self, task):
        self.stack_offset = 0
        self.globals = {}
        self.in_function = True

        self.emit('')
        self.emit(f'    fn global {task.name}')
        self.emit('    start')
        self.emit('        push sbp')
        self.emit('        move sbp stp')

        # load parameters
        param_regs = ['dst', 'src', 'dta', 'cnt', 'r4', 'r5']
        for i, param in enumerate(task.params):
            self.stack_offset += 8
            self.globals[param] = self.stack_offset
            if i < 6:
                self.emit(f'        move [sbp - {self.stack_offset}] {param_regs[i]}')
            else:
                offset = (i - 6) * 8 + 16
                self.emit(f'        move r1 [sbp + {offset}]')
                self.emit(f'        move [sbp - {self.stack_offset}] r1')

        for stmt in task.body:
            self.compile_stmt(stmt)

        self.emit('        move ret 0')
        self.emit('        move stp sbp')
        self.emit('        pop sbp')
        self.emit('        return')
        self.emit('    end')

        self.in_function = False

    def compile_stmt(self, stmt):
        if isinstance(stmt, Assign):
            self.compile_assign(stmt)
        elif isinstance(stmt, ReturnStmt):
            self.compile_return(stmt)
        elif isinstance(stmt, IfBlock):
            self.compile_if(stmt)
        elif isinstance(stmt, LoopBlock):
            self.compile_loop(stmt)
        elif isinstance(stmt, FuncCall):
            self.compile_call(stmt)
            self.emit('        # discard return value')
        elif isinstance(stmt, ExprStmt):
            if isinstance(stmt.expr, FuncCall):
                self.compile_call(stmt.expr)
            elif isinstance(stmt.expr, Assign):
                self.compile_assign(stmt.expr)
        elif isinstance(stmt, RiskBlock):
            for s in stmt.body:
                self.compile_stmt(s)
        elif isinstance(stmt, TryCatchBlock):
            for s in stmt.body:
                self.compile_stmt(s)
        elif isinstance(stmt, SectionDef):
            for s in stmt.body:
                self.compile_stmt(s)

    def compile_assign(self, stmt):
        self.compile_expr(stmt.value)
        if stmt.name not in self.globals:
            self.stack_offset += 8
            self.globals[stmt.name] = self.stack_offset
        offset = self.globals[stmt.name]
        self.emit(f'        move [sbp - {offset}] ret')

    def compile_return(self, stmt):
        if stmt.value:
            self.compile_expr(stmt.value)
        else:
            self.emit('        move ret 0')
        self.emit('        move stp sbp')
        self.emit('        pop sbp')
        self.emit('        return')

    def compile_if(self, stmt):
        end_label = self.new_label('endif')
        self.compile_expr(stmt.condition)
        self.emit(f'        cmp ret == 0 go {end_label}')

        for s in stmt.body:
            self.compile_stmt(s)

        for elif_block in stmt.elifs:
            elif_label = self.new_label('elif')
            self.emit(f'        go {end_label}')
            self.emit(f'    {elif_label}:')
            self.compile_expr(elif_block.condition)
            self.emit(f'        cmp ret == 0 go {end_label}')
            for s in elif_block.body:
                self.compile_stmt(s)

        if stmt.else_body:
            else_label = self.new_label('else')
            self.emit(f'        go {end_label}')
            self.emit(f'    {else_label}:')
            for s in stmt.else_body:
                self.compile_stmt(s)

        self.emit(f'    {end_label}:')

    def compile_loop(self, stmt):
        if stmt.kind == 'forever':
            start = self.new_label('loop')
            self.emit(f'    {start}:')
            for s in stmt.body:
                self.compile_stmt(s)
            self.emit(f'        go {start}')
        elif stmt.kind == 'count':
            self.compile_expr(stmt.expr)
            counter = self.new_label('counter')
            self.emit(f'        move r1 ret')
            self.emit(f'    {counter}:')
            self.emit(f'        cmp r1 == 0 go {counter}_end')
            for s in stmt.body:
                self.compile_stmt(s)
            self.emit(f'        dec r1')
            self.emit(f'        go {counter}')
            self.emit(f'    {counter}_end:')
        elif stmt.kind == 'counter':
            if stmt.counter not in self.globals:
                self.stack_offset += 8
                self.globals[stmt.counter] = self.stack_offset
            self.compile_expr(stmt.expr)
            offset = self.globals[stmt.counter]
            self.emit(f'        move [sbp - {offset}] ret')
            start = self.new_label('loop')
            self.emit(f'    {start}:')
            # check condition: counter < expr
            self.emit(f'        move r1 [sbp - {offset}]')
            self.emit(f'        move r2 ret')
            self.emit(f'        cmp r1 >= r2 go {start}_end')
            for s in stmt.body:
                self.compile_stmt(s)
            self.emit(f'        inc r1')
            self.emit(f'        move [sbp - {offset}] r1')
            self.emit(f'        go {start}')
            self.emit(f'    {start}_end:')
        elif stmt.kind == 'while':
            start = self.new_label('loop')
            self.emit(f'    {start}:')
            self.compile_expr(stmt.expr)
            self.emit(f'        cmp ret == 0 go {start}_end')
            for s in stmt.body:
                self.compile_stmt(s)
            self.emit(f'        go {start}')
            self.emit(f'    {start}_end:')

    def compile_call(self, func):
        if func.name in ('write', 'print'):
            if len(func.args) >= 1:
                self.compile_expr(func.args[0])
                self.emit(f'        move dst 1')
                self.emit(f'        move src ret')
                if isinstance(func.args[0], StringLit):
                    self.emit(f'        move dta {len(func.args[0].value)}')
                else:
                    self.emit(f'        move dta 0')
                self.emit(f'        move ret 1')
                self.emit(f'        syscall')
            return

        # evaluate arguments and push right-to-left
        for arg in reversed(func.args):
            self.compile_expr(arg)
            self.emit(f'        push ret')

        self.emit(f'        call {func.name}')

        if func.args:
            self.emit(f'        move r1 {len(func.args) * 8}')
            self.emit(f'        add stp r1')

    def compile_expr(self, expr):
        if isinstance(expr, NumberLit):
            self.emit(f'        move ret {expr.value}')
        elif isinstance(expr, StringLit):
            sname = self.add_string(expr.value)
            self.emit(f'        lma ret {sname}')
        elif isinstance(expr, BoolLit):
            self.emit(f'        move ret {1 if expr.value else 0}')
        elif isinstance(expr, VoidLit):
            self.emit(f'        move ret 0')
        elif isinstance(expr, Ident):
            if expr.name in self.globals:
                offset = self.globals[expr.name]
                self.emit(f'        move ret [sbp - {offset}]')
            elif expr.name in self.functions:
                self.emit(f'        lma ret {expr.name}')
            else:
                self.emit(f'        move ret 0  # undefined: {expr.name}')
        elif isinstance(expr, FuncCall):
            self.compile_call(expr)
        elif isinstance(expr, BinaryOp):
            self.compile_binary(expr)
        elif isinstance(expr, UnaryOp):
            self.compile_unary(expr)

    def compile_binary(self, expr):
        # evaluate left into r1
        self.compile_expr(expr.left)
        self.emit(f'        move r1 ret')
        # evaluate right into r2
        self.compile_expr(expr.right)
        self.emit(f'        move r2 ret')
        # perform operation
        ops = {
            '+': 'add', '-': 'sub', '*': 'mul', '/': 'div', '%': 'div',
            '==': 'cmp_eq', '!=': 'cmp_ne', '<': 'cmp_lt', '>': 'cmp_gt',
            '<=': 'cmp_le', '>=': 'cmp_ge',
            '&&': 'and', '||': 'or',
        }
        op = expr.op
        if op in ('==', '!=', '<', '>', '<=', '>='):
            labels = {
                '==': ('eq', 'ne'), '!=': ('ne', 'eq'),
                '<': ('lt', 'ge'), '>': ('gt', 'le'),
                '<=': ('le', 'gt'), '>=': ('ge', 'lt'),
            }
            true_label = self.new_label('cmp_true')
            end_label = self.new_label('cmp_end')
            self.emit(f'        cmp r1 {op} r2 go {true_label}')
            self.emit(f'        move ret 0')
            self.emit(f'        go {end_label}')
            self.emit(f'    {true_label}:')
            self.emit(f'        move ret 1')
            self.emit(f'    {end_label}:')
        elif op == '+':
            self.emit(f'        add r1 r2')
            self.emit(f'        move ret r1')
        elif op == '-':
            self.emit(f'        sub r1 r2')
            self.emit(f'        move ret r1')
        elif op == '*':
            self.emit(f'        mul r1 r2')
            self.emit(f'        move ret r1')
        elif op == '/':
            self.emit(f'        move dta 0')
            self.emit(f'        div r2')
            self.emit(f'        move ret r1')
        elif op == '%':
            self.emit(f'        move dta 0')
            self.emit(f'        div r2')
            self.emit(f'        move ret dta')
        elif op == '&&':
            self.emit(f'        and r1 r2')
            self.emit(f'        move ret r1')
        elif op == '||':
            self.emit(f'        or r1 r2')
            self.emit(f'        move ret r1')

    def compile_unary(self, expr):
        self.compile_expr(expr.operand)
        if expr.op == '-':
            self.emit(f'        neg ret')
        elif expr.op == '!':
            # logical not: if ret == 0 then 1 else 0
            true_label = self.new_label('not_true')
            end_label = self.new_label('not_end')
            self.emit(f'        cmp ret == 0 go {true_label}')
            self.emit(f'        move ret 0')
            self.emit(f'        go {end_label}')
            self.emit(f'    {true_label}:')
            self.emit(f'        move ret 1')
            self.emit(f'    {end_label}:')

    def generate(self, source):
        tokens = tokenize(source)
        ast = parse(tokens)
        return self.compile(ast)


def compile_source(source, output_path=None, keep_asm=False):
    compiler = Compiler()
    asm = compiler.generate(source)

    if keep_asm or output_path and output_path.endswith('.tsm'):
        if output_path:
            with open(output_path, 'w') as f:
                f.write(asm)
        return asm

    # write asm to temp file, assemble with ThornASM
    asm_path = output_path + '.tsm' if output_path else None
    if not asm_path:
        asm_path = os.path.join(tempfile.gettempdir(), 'softrose_out.tsm')

    with open(asm_path, 'w') as f:
        f.write(asm)

    bin_path = output_path or asm_path.replace('.tsm', '.bin')

    # find spine64 assembler
    script_dir = os.path.dirname(os.path.abspath(__file__))
    assembler = os.path.join(script_dir, '..', 'spine64', 'assembler.py')

    result = subprocess.run(
        ['python', assembler, asm_path, bin_path, '--bin'],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f'assembly error: {result.stderr}')
        return None

    print(result.stdout.strip())

    if not keep_asm:
        os.remove(asm_path)

    return bin_path


if __name__ == '__main__':
    import sys
    if len(sys.argv) < 2:
        print('usage: python compiler.py <source.rose> [output.bin]')
        sys.exit(1)

    with open(sys.argv[1]) as f:
        source = f.read()

    out = sys.argv[2] if len(sys.argv) > 2 else sys.argv[1].replace('.rose', '.bin')
    compile_source(source, out)
