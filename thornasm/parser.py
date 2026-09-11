from lexer import Token, TokenType
from ast_nodes import *


TWOOP_INSTRUCTIONS = {
    'add': AddNode, 'sub': SubNode, 'mul': MulNode, 'smul': SMulNode,
    'div': DivNode, 'sdiv': SDivNode, 'awc': AwcNode, 'swb': SwbNode,
    'and': AndNode, 'or': OrNode, 'xor': XorNode,
    'shl': ShlNode, 'shr': ShrNode, 'asr': AsrNode,
    'rotl': RotlNode, 'rotr': RotrNode, 'racl': RaclNode, 'racr': RacrNode,
    'lma': LmaNode, 'swap': SwapNode, 'movesx': MoveSxNode, 'movezx': MoveZxNode,
    'fadd': FaddNode, 'fsub': FsubNode, 'fmul': FmulNode, 'fdiv': FdivNode,
    'fmove': FmoveNode, 'fcmp': FcmpNode,
}

ALL_INSTRUCTIONS = set(TWOOP_INSTRUCTIONS.keys()) | {
    'move', 'not', 'inc', 'dec', 'neg', 'push', 'pop',
    'call', 'return', 'go', 'cmp', 'loop', 'set',
    'pr', 'pw', 'int', 'syscall', 'nope', 'halt',
    'ioff', 'ion', 'reti', 'rep', 'extern', 'fn',
}


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
        self.aliases = {}

    def peek(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def advance(self):
        if self.pos < len(self.tokens):
            tok = self.tokens[self.pos]
            self.pos += 1
            return tok
        return None

    def expect(self, ttype):
        tok = self.advance()
        if tok is None or tok.type != ttype:
            expected = ttype.name
            got = f"{tok.type.name}({tok.value!r})" if tok else "EOF"
            raise SyntaxError(f"expected {expected}, got {got} at line {getattr(tok, 'line', '?')}")
        return tok

    def skip_newlines(self):
        while self.peek() and self.peek().type == TokenType.NEWLINE:
            self.advance()

    def parse_operand(self):
        tok = self.peek()
        if tok is None:
            raise SyntaxError("unexpected end of file in operand")

        if tok.type == TokenType.LBRACKET:
            self.advance()  # [
            parts = []
            while self.peek() and self.peek().type != TokenType.RBRACKET:
                t = self.advance()
                if t.type == TokenType.IDENT:
                    parts.append(self.aliases.get(t.value, t.value))
                elif t.type == TokenType.NUMBER:
                    parts.append(t.value)
                elif t.type == TokenType.FLOAT:
                    parts.append(t.value)
                elif t.type in (TokenType.PLUS, TokenType.STAR, TokenType.MINUS):
                    parts.append(t.value)
                else:
                    parts.append(t.value)
            self.expect(TokenType.RBRACKET)
            return '[' + ' '.join(parts) + ']'

        tok = self.advance()
        if tok.type == TokenType.IDENT:
            return self.aliases.get(tok.value, tok.value)
        elif tok.type == TokenType.NUMBER:
            return tok.value
        elif tok.type == TokenType.FLOAT:
            return tok.value
        elif tok.type == TokenType.STRING:
            return tok.value
        else:
            return tok.value

    def parse_twoop(self, cls):
        dst = self.parse_operand()
        src = self.parse_operand()
        return cls(dst=dst, src=src)

    def parse_statement(self):
        tok = self.peek()
        if tok is None:
            return None
        if tok.type == TokenType.NEWLINE:
            self.advance()
            return None

        if tok.type == TokenType.IDENT:
            val = tok.value

            if val in TWOOP_INSTRUCTIONS:
                self.advance()
                return self.parse_twoop(TWOOP_INSTRUCTIONS[val])

            if val == 'move':
                self.advance()
                size = None
                if self.peek() and self.peek().type == TokenType.DOT_SIZE:
                    size = self.advance().value
                dst = self.parse_operand()
                src = self.parse_operand()
                return MoveNode(dst=dst, src=src, size=size)

            if val == 'not':
                self.advance()
                reg = self.parse_operand()
                return NotNode(reg=reg)
            if val == 'inc':
                self.advance()
                return IncNode(reg=self.parse_operand())
            if val == 'dec':
                self.advance()
                return DecNode(reg=self.parse_operand())
            if val == 'neg':
                self.advance()
                return NegNode(reg=self.parse_operand())
            if val == 'push':
                self.advance()
                return PushNode(value=self.parse_operand())
            if val == 'pop':
                self.advance()
                return PopNode(reg=self.parse_operand())
            if val == 'go':
                self.advance()
                return GoNode(label=self.parse_operand())
            if val == 'call':
                self.advance()
                return CallNode(name=self.parse_operand())
            if val == 'return':
                self.advance()
                return ReturnNode()
            if val == 'set':
                self.advance()
                reg = self.parse_operand()
                flag = self.parse_operand()
                return SetNode(reg=reg, flag=flag)
            if val == 'syscall':
                self.advance()
                return SyscallNode()
            if val == 'nope':
                self.advance()
                return NopeNode()
            if val == 'halt':
                self.advance()
                return HaltNode()
            if val == 'ioff':
                self.advance()
                return IoffNode()
            if val == 'ion':
                self.advance()
                return IonNode()
            if val == 'reti':
                self.advance()
                return RetiNode()
            if val == 'pr':
                self.advance()
                return PrNode(dst=self.parse_operand(), port=self.parse_operand())
            if val == 'pw':
                self.advance()
                return PwNode(port=self.parse_operand(), src=self.parse_operand())
            if val == 'int':
                self.advance()
                return IntNode(number=self.parse_operand())
            if val == 'rep':
                self.advance()
                kind = self.advance().value
                if kind == 'movs':
                    return RepMovsNode()
                return RepStosNode()
            if val == 'extern':
                self.advance()
                return ExternNode(name=self.parse_operand())
            if val == 'loop':
                self.advance()
                self.skip_newlines()
                self.expect(TokenType.IDENT)  # 'start'
                body = self._parse_until_end()
                return LoopNode(body=body)
            if val == 'cmp':
                self.advance()
                return self._parse_cmp()

            # label: name COLON
            if self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].type == TokenType.COLON:
                name = tok.value
                self.advance()  # name
                self.advance()  # :
                return LabelNode(name=name)

            # unknown ident, skip
            self.advance()
            return None

        # skip unknown token
        self.advance()
        return None

    def _parse_cmp(self):
        tok = self.peek()
        if tok and tok.type == TokenType.IDENT and tok.value in ('carry', 'zero', 'overflow'):
            flag = self.parse_operand()
            self.expect(TokenType.IDENT)  # 'go'
            label = self.parse_operand()
            return CmpFlagNode(flag=flag, label=label)
        else:
            left = self.parse_operand()
            op_tok = self.advance()
            op = op_tok.value
            right = self.parse_operand()
            self.expect(TokenType.IDENT)  # 'go'
            label = self.parse_operand()
            return CmpNode(left=left, op=op, right=right, label=label)

    def _parse_until_end(self):
        body = []
        depth = 0
        while self.peek() is not None:
            tok = self.peek()
            if tok.type == TokenType.IDENT and tok.value == 'end':
                if depth == 0:
                    self.advance()
                    return body
                depth -= 1
            if tok.type == TokenType.IDENT and tok.value == 'start':
                depth += 1
            node = self.parse_statement()
            if node is not None:
                body.append(node)
        return body

    def _parse_fn_body(self):
        self.skip_newlines()
        self.expect(TokenType.IDENT)  # 'start'
        body = []
        while self.peek() is not None:
            tok = self.peek()
            if tok.type == TokenType.IDENT and tok.value == 'end':
                self.advance()
                return body
            node = self.parse_statement()
            if node is not None:
                body.append(node)
        return body

    def _parse_module_data(self):
        body = []
        while self.peek() is not None:
            tok = self.peek()
            if tok.type == TokenType.IDENT and tok.value == 'module':
                return body
            if tok.type == TokenType.IDENT and tok.value == 'on':
                return body
            if tok.type == TokenType.EOF:
                return body
            if tok.type == TokenType.NEWLINE:
                self.advance()
                continue
            if tok.type == TokenType.IDENT and tok.value == 'alias':
                self.advance()
                reg = self.parse_operand()
                name = self.parse_operand()
                self.aliases[name] = reg
                continue
            if tok.type == TokenType.IDENT:
                name = tok.value
                self.advance()
                value = self.parse_operand()
                size = None
                if self.peek() and self.peek().type not in (TokenType.NEWLINE, TokenType.EOF):
                    size = self.parse_operand()
                body.append(DataDefNode(name=name, value=value, size=size))
                continue
            self.advance()
        return body

    def _parse_module_code(self):
        body = []
        while self.peek() is not None:
            tok = self.peek()
            if tok.type == TokenType.IDENT and tok.value == 'module':
                return body
            if tok.type == TokenType.EOF:
                return body
            if tok.type == TokenType.NEWLINE:
                self.advance()
                continue
            if tok.type == TokenType.IDENT and tok.value == 'fn':
                self.advance()
                fn_type = 'normal'
                if self.peek() and self.peek().type == TokenType.IDENT and self.peek().value in ('global', 'raw'):
                    fn_type = self.peek().value
                    self.advance()
                name = self.advance().value
                fn_body = self._parse_fn_body()
                body.append(FnNode(name=name, body=fn_body, fn_type=fn_type))
                continue
            if tok.type == TokenType.IDENT and tok.value == 'extern':
                self.advance()
                body.append(ExternNode(name=self.parse_operand()))
                continue
            if tok.type == TokenType.IDENT and tok.value == 'on':
                self.advance()
                self.advance()  # 'interrupt'
                number = self.parse_operand()
                self.skip_newlines()
                self.expect(TokenType.IDENT)  # 'start'
                handler_body = self._parse_until_end()
                body.append(InterruptHandlerNode(number=number, body=handler_body))
                continue
            # could be a label or instruction at module level
            if tok.type == TokenType.IDENT and self.pos + 1 < len(self.tokens) and self.tokens[self.pos + 1].type == TokenType.COLON:
                name = tok.value
                self.advance()
                self.advance()
                body.append(LabelNode(name=name))
                continue
            if tok.type == TokenType.IDENT and tok.value in ALL_INSTRUCTIONS:
                node = self.parse_statement()
                if node is not None:
                    body.append(node)
                continue
            if tok.type == TokenType.IDENT:
                # could be a data definition inside code module
                name = tok.value
                self.advance()
                value = self.parse_operand()
                size = None
                if self.peek() and self.peek().type not in (TokenType.NEWLINE, TokenType.EOF):
                    size = self.parse_operand()
                body.append(DataDefNode(name=name, value=value, size=size))
                continue
            self.advance()
        return body

    def parse(self):
        nodes = []
        self.skip_newlines()
        while self.peek() is not None and self.peek().type != TokenType.EOF:
            tok = self.peek()
            if tok.type == TokenType.NEWLINE:
                self.advance()
                continue
            if tok.type == TokenType.IDENT and tok.value == 'origin':
                self.advance()
                address = self.parse_operand()
                nodes.append(OriginNode(address=address))
                continue
            if tok.type == TokenType.IDENT and tok.value == 'bits':
                self.advance()
                mode = self.advance().value
                nodes.append(BitsNode(mode=int(mode)))
                continue
            if tok.type == TokenType.IDENT and tok.value == 'db':
                self.advance()
                vals = []
                while self.peek() and self.peek().type not in (TokenType.NEWLINE, TokenType.EOF):
                    vals.append(self.parse_operand())
                    if self.peek() and self.peek().type == TokenType.COMMA:
                        self.advance()
                nodes.append(DataByteNode(values=vals))
                continue
            if tok.type == TokenType.IDENT and tok.value == 'dw':
                self.advance()
                vals = []
                while self.peek() and self.peek().type not in (TokenType.NEWLINE, TokenType.EOF):
                    vals.append(self.parse_operand())
                    if self.peek() and self.peek().type == TokenType.COMMA:
                        self.advance()
                nodes.append(DataWordNode(values=vals))
                continue
            if tok.type == TokenType.IDENT and tok.value == 'dd':
                self.advance()
                vals = []
                while self.peek() and self.peek().type not in (TokenType.NEWLINE, TokenType.EOF):
                    vals.append(self.parse_operand())
                    if self.peek() and self.peek().type == TokenType.COMMA:
                        self.advance()
                nodes.append(DataDwordNode(values=vals))
                continue
            if tok.type == TokenType.IDENT and tok.value == 'times':
                self.advance()
                count = self.parse_operand()
                # next should be db/dw/dd and values
                inner_tok = self.advance()
                vals = []
                while self.peek() and self.peek().type not in (TokenType.NEWLINE, TokenType.EOF):
                    vals.append(self.parse_operand())
                    if self.peek() and self.peek().type == TokenType.COMMA:
                        self.advance()
                nodes.append(TimesNode(count=count, dtype=inner_tok.value, values=vals))
                continue
            if tok.type == TokenType.IDENT and tok.value == 'module':
                self.advance()
                kind = self.advance().value
                if kind in ('data', 'reserve'):
                    body = self._parse_module_data()
                else:
                    body = self._parse_module_code()
                nodes.append(ModuleNode(kind=kind, body=body))
                continue
            if tok.type == TokenType.IDENT and tok.value == 'extern':
                self.advance()
                nodes.append(ExternNode(name=self.parse_operand()))
                continue
            if tok.type == TokenType.IDENT and tok.value == 'on':
                self.advance()
                self.advance()  # 'interrupt'
                number = self.parse_operand()
                self.skip_newlines()
                self.expect(TokenType.IDENT)  # 'start'
                handler_body = self._parse_until_end()
                nodes.append(InterruptHandlerNode(number=number, body=handler_body))
                continue
            self.advance()
        return nodes


def parse_tokens(tokens):
    return Parser(tokens).parse()


if __name__ == '__main__':
    import sys
    from lexer import tokenize_source
    path = sys.argv[1] if len(sys.argv) > 1 else 'source.tsm'
    with open(path) as f:
        src = f.read()
    tokens = tokenize_source(src)
    ast = Parser(tokens).parse()
    for node in ast:
        print(node)
