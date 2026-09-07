from dataclasses import dataclass, field
from typing import List, Optional
from lexer import Token, TT


# ── AST Nodes ──

@dataclass
class NumberLit:
    value: str

@dataclass
class StringLit:
    value: str

@dataclass
class BoolLit:
    value: bool

@dataclass
class VoidLit:
    pass

@dataclass
class Ident:
    name: str

@dataclass
class BinaryOp:
    op: str
    left: 'Expr'
    right: 'Expr'

@dataclass
class UnaryOp:
    op: str
    operand: 'Expr'

@dataclass
class IndexExpr:
    target: 'Expr'
    index: 'Expr'

@dataclass
class FuncCall:
    name: str
    args: list

@dataclass
class Assign:
    name: str
    value: 'Expr'

@dataclass
class TaskDef:
    name: str
    params: list
    body: list

@dataclass
class IfBlock:
    condition: 'Expr'
    body: list
    elifs: list = field(default_factory=list)
    else_body: list = field(default_factory=list)

@dataclass
class ElifBlock:
    condition: 'Expr'
    body: list

@dataclass
class LoopBlock:
    kind: str  # 'forever', 'count', 'counter', 'while', 'iterate'
    expr: 'Expr' = None
    counter: str = None
    body: list = field(default_factory=list)

@dataclass
class ReturnStmt:
    value: 'Expr' = None

@dataclass
class ExprStmt:
    expr: 'Expr'

@dataclass
class SectionDef:
    visibility: str  # 'global', ''
    name: str
    body: list

@dataclass
class NeedStmt:
    module: str
    alias: str = None
    items: list = None

@dataclass
class RiskBlock:
    body: list

@dataclass
class TryCatchBlock:
    body: list
    catch_var: str = None
    catch_body: list = None

@dataclass
class SpawnExpr:
    call: FuncCall

@dataclass
class Program:
    body: list


# ── Parser ──

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, tt):
        tok = self.advance()
        if tok.type != tt:
            raise SyntaxError(f'expected {tt.name}, got {tok.type.name}({tok.value!r}) at line {tok.line}')
        return tok

    def skip_newlines(self):
        while self.peek() and self.peek().type == TT.NEWLINE:
            self.advance()

    def parse(self):
        body = []
        self.skip_newlines()
        while self.peek() and self.peek().type != TT.EOF:
            stmt = self.parse_stmt()
            if stmt:
                body.append(stmt)
            self.skip_newlines()
        return Program(body=body)

    def parse_stmt(self):
        tok = self.peek()
        if tok is None:
            return None
        if tok.type == TT.NEWLINE:
            self.advance()
            return None
        if tok.type == TT.TASK:
            return self.parse_task()
        if tok.type == TT.IF:
            return self.parse_if()
        if tok.type == TT.LOOP:
            return self.parse_loop()
        if tok.type == TT.SEND:
            return self.parse_return()
        if tok.type == TT.SECTION:
            return self.parse_section()
        if tok.type == TT.NEED:
            return self.parse_need()
        if tok.type == TT.RISK:
            return self.parse_risk()
        if tok.type == TT.TRY:
            return self.parse_try()
        if tok.type == TT.SPAWN:
            return self.parse_spawn_stmt()
        # assignment or expression statement
        if tok.type == TT.IDENT and self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].type == TT.ASSIGN:
            return self.parse_assign()
        return self.parse_expr_stmt()

    def parse_task(self):
        self.advance()  # task
        name_tok = self.advance()
        if name_tok.type in (TT.START,):
            name = name_tok.value
        else:
            if name_tok.type != TT.IDENT:
                raise SyntaxError(f'expected task name, got {name_tok.type.name} at line {name_tok.line}')
            name = name_tok.value
        self.expect(TT.LPAREN)
        params = []
        if self.peek() and self.peek().type != TT.RPAREN:
            params.append(self.expect(TT.IDENT).value)
            while self.peek() and self.peek().type == TT.COMMA:
                self.advance()
                params.append(self.expect(TT.IDENT).value)
        self.expect(TT.RPAREN)
        body = self.parse_block()
        return TaskDef(name=name, params=params, body=body)

    def parse_block(self):
        self.skip_newlines()
        self.expect(TT.LBRACE)
        self.skip_newlines()
        body = []
        while self.peek() and self.peek().type != TT.RBRACE:
            stmt = self.parse_stmt()
            if stmt:
                body.append(stmt)
            self.skip_newlines()
        self.expect(TT.RBRACE)
        return body

    def parse_if(self):
        self.advance()  # if
        self.expect(TT.LPAREN)
        cond = self.parse_expr()
        self.expect(TT.RPAREN)
        body = self.parse_block()
        elifs = []
        else_body = []
        self.skip_newlines()
        while self.peek() and self.peek().type == TT.ELIF:
            self.advance()
            self.expect(TT.LPAREN)
            econd = self.parse_expr()
            self.expect(TT.RPAREN)
            ebody = self.parse_block()
            elifs.append(ElifBlock(condition=econd, body=ebody))
            self.skip_newlines()
        if self.peek() and self.peek().type == TT.ELSE:
            self.advance()
            else_body = self.parse_block()
        return IfBlock(condition=cond, body=body, elifs=elifs, else_body=else_body)

    def parse_loop(self):
        self.advance()  # loop
        self.expect(TT.LPAREN)
        tok = self.peek()

        if tok.type == TT.ON:
            self.advance()
            self.expect(TT.RPAREN)
            body = self.parse_block()
            return LoopBlock(kind='forever', body=body)

        if tok.type == TT.NUMBER:
            count = self.advance().value
            self.expect(TT.RPAREN)
            body = self.parse_block()
            return LoopBlock(kind='count', expr=NumberLit(count), body=body)

        if tok.type == TT.IDENT and self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].type == TT.ASSIGN:
            counter = self.advance().value
            self.advance()  # =
            expr = self.parse_expr()
            self.expect(TT.RPAREN)
            body = self.parse_block()
            return LoopBlock(kind='counter', counter=counter, expr=expr, body=body)

        if tok.type == TT.IDENT and self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].type == TT.IDENT:
            # loop(item = myList)
            item = self.advance().value
            self.advance()  # =
            expr = self.parse_expr()
            self.expect(TT.RPAREN)
            body = self.parse_block()
            return LoopBlock(kind='iterate', counter=item, expr=expr, body=body)

        expr = self.parse_expr()
        self.expect(TT.RPAREN)
        body = self.parse_block()
        return LoopBlock(kind='while', expr=expr, body=body)

    def parse_return(self):
        self.advance()  # send
        val = None
        if self.peek() and self.peek().type not in (TT.NEWLINE, TT.EOF, TT.RBRACE):
            val = self.parse_expr()
        return ReturnStmt(value=val)

    def parse_section(self):
        self.advance()  # section
        vis = ''
        if self.peek() and self.peek().type == TT.DOT:
            self.advance()
            vis = self.expect(TT.IDENT).value
        name = self.expect(TT.IDENT).value
        body = self.parse_block()
        return SectionDef(visibility=vis, name=name, body=body)

    def parse_need(self):
        self.advance()  # need
        module = self.expect(TT.IDENT).value
        alias = None
        items = None
        self.skip_newlines()
        if self.peek() and self.peek().type == TT.AS:
            self.advance()
            alias = self.expect(TT.IDENT).value
        elif self.peek() and self.peek().type == TT.FROM:
            self.advance()
            # need X from "file" - reverse: actually this is from syntax
            # but in Thorn it's: need myTask from "myfile"
            pass
        return NeedStmt(module=module, alias=alias, items=items)

    def parse_risk(self):
        self.advance()  # risk
        body = self.parse_block()
        return RiskBlock(body=body)

    def parse_try(self):
        self.advance()  # try
        body = self.parse_block()
        catch_var = None
        catch_body = []
        self.skip_newlines()
        if self.peek() and self.peek().type == TT.CATCH:
            self.advance()
            self.expect(TT.LPAREN)
            catch_var = self.expect(TT.IDENT).value
            self.expect(TT.RPAREN)
            catch_body = self.parse_block()
        return TryCatchBlock(body=body, catch_var=catch_var, catch_body=catch_body)

    def parse_spawn_stmt(self):
        self.advance()  # spawn
        self.expect(TT.LPAREN)
        name = self.expect(TT.IDENT).value
        self.expect(TT.LPAREN)
        args = self.parse_args()
        self.expect(TT.RPAREN)
        self.expect(TT.RPAREN)
        return ExprStmt(expr=FuncCall(name=f'spawn_{name}', args=args))

    def parse_assign(self):
        name = self.expect(TT.IDENT).value
        self.expect(TT.ASSIGN)
        value = self.parse_expr()
        return Assign(name=name, value=value)

    def parse_expr_stmt(self):
        expr = self.parse_expr()
        return ExprStmt(expr=expr)

    # ── Expressions ──

    def parse_expr(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()
        while self.peek() and self.peek().type == TT.OR:
            self.advance()
            right = self.parse_and()
            left = BinaryOp(op='||', left=left, right=right)
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.peek() and self.peek().type == TT.AND:
            self.advance()
            right = self.parse_not()
            left = BinaryOp(op='&&', left=left, right=right)
        return left

    def parse_not(self):
        if self.peek() and self.peek().type == TT.NOT:
            self.advance()
            operand = self.parse_not()
            return UnaryOp(op='!', operand=operand)
        return self.parse_comparison()

    def parse_comparison(self):
        left = self.parse_addition()
        while self.peek() and self.peek().type in (TT.EQ, TT.NEQ, TT.LT, TT.GT, TT.LTE, TT.GTE):
            op = self.advance().value
            right = self.parse_addition()
            left = BinaryOp(op=op, left=left, right=right)
        return left

    def parse_addition(self):
        left = self.parse_multiplication()
        while self.peek() and self.peek().type in (TT.PLUS, TT.MINUS):
            op = self.advance().value
            right = self.parse_multiplication()
            left = BinaryOp(op=op, left=left, right=right)
        return left

    def parse_multiplication(self):
        left = self.parse_unary()
        while self.peek() and self.peek().type in (TT.STAR, TT.SLASH, TT.PERCENT):
            op = self.advance().value
            right = self.parse_unary()
            left = BinaryOp(op=op, left=left, right=right)
        return left

    def parse_unary(self):
        if self.peek() and self.peek().type in (TT.MINUS, TT.NOT):
            op = self.advance().value
            operand = self.parse_unary()
            return UnaryOp(op=op, operand=operand)
        return self.parse_primary()

    def parse_primary(self):
        tok = self.peek()
        if tok is None:
            return VoidLit()

        if tok.type == TT.NUMBER:
            self.advance()
            return NumberLit(value=tok.value)

        if tok.type == TT.STRING:
            self.advance()
            return StringLit(value=tok.value)

        if tok.type == TT.ON:
            self.advance()
            return BoolLit(value=True)
        if tok.type == TT.OFF:
            self.advance()
            return BoolLit(value=False)
        if tok.type == TT.TRUE:
            self.advance()
            return BoolLit(value=True)
        if tok.type == TT.FALSE:
            self.advance()
            return BoolLit(value=False)
        if tok.type == TT.VOID:
            self.advance()
            return VoidLit()

        if tok.type == TT.IDENT:
            self.advance()
            # check for function call
            if self.peek() and self.peek().type == TT.LPAREN:
                self.advance()  # (
                args = self.parse_args()
                self.expect(TT.RPAREN)
                result = FuncCall(name=tok.value, args=args)
            else:
                result = Ident(name=tok.value)
            # check for array indexing: expr[index]
            while self.peek() and self.peek().type == TT.LBRACKET:
                self.advance()  # [
                index = self.parse_expr()
                self.expect(TT.RBRACKET)
                result = IndexExpr(target=result, index=index)
            return result

        if tok.type == TT.LPAREN:
            self.advance()
            expr = self.parse_expr()
            self.expect(TT.RPAREN)
            return expr

        if tok.type == TT.SPAWN:
            self.advance()
            self.expect(TT.LPAREN)
            name = self.expect(TT.IDENT).value
            self.expect(TT.LPAREN)
            args = self.parse_args()
            self.expect(TT.RPAREN)
            self.expect(TT.RPAREN)
            return FuncCall(name=f'spawn_{name}', args=args)

        raise SyntaxError(f'unexpected token {tok.type.name}({tok.value!r}) at line {tok.line}')

    def parse_args(self):
        args = []
        if self.peek() and self.peek().type != TT.RPAREN:
            args.append(self.parse_expr())
            while self.peek() and self.peek().type == TT.COMMA:
                self.advance()
                args.append(self.parse_expr())
        return args


def parse(tokens):
    return Parser(tokens).parse()
