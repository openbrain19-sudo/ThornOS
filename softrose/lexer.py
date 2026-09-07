from enum import Enum, auto
from dataclasses import dataclass


class TT(Enum):
    IDENT = auto()
    NUMBER = auto()
    STRING = auto()
    INTERP = auto()  # {expr} inside v"..."
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    EQ = auto()
    NEQ = auto()
    LT = auto()
    GT = auto()
    LTE = auto()
    GTE = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    ASSIGN = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    COMMA = auto()
    DOT = auto()
    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()
    EOF = auto()
    # keywords
    TASK = auto()
    SEND = auto()
    IF = auto()
    ELIF = auto()
    ELSE = auto()
    LOOP = auto()
    ON = auto()
    OFF = auto()
    VOID = auto()
    SECTION = auto()
    NEED = auto()
    AS = auto()
    FROM = auto()
    START = auto()
    RISK = auto()
    TRY = auto()
    CATCH = auto()
    SPAWN = auto()
    TRUE = auto()
    FALSE = auto()


KEYWORDS = {
    'task': TT.TASK, 'send': TT.SEND,
    'if': TT.IF, 'elif': TT.ELIF, 'else': TT.ELSE,
    'loop': TT.LOOP,
    'on': TT.ON, 'off': TT.OFF, 'void': TT.VOID,
    'section': TT.SECTION,
    'need': TT.NEED, 'as': TT.AS, 'from': TT.FROM,
    'start': TT.START,
    'risk': TT.RISK, 'try': TT.TRY, 'catch': TT.CATCH,
    'spawn': TT.SPAWN,
    'true': TT.TRUE, 'false': TT.FALSE,
}


@dataclass
class Token:
    type: TT
    value: str
    line: int
    col: int = 0

    def __repr__(self):
        return f'Token({self.type.name}, {self.value!r}, L{self.line})'


class Lexer:
    def __init__(self, src):
        self.src = src
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens = []
        self.indent_stack = [0]

    def peek(self):
        return self.src[self.pos] if self.pos < len(self.src) else None

    def peek2(self):
        return self.src[self.pos + 1] if self.pos + 1 < len(self.src) else None

    def advance(self):
        ch = self.src[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def emit(self, tt, val, line=None):
        self.tokens.append(Token(tt, val, line or self.line, self.col))

    def read_string(self):
        self.advance()  # opening "
        parts = []
        is_interp = False
        while self.peek() is not None and self.peek() != '"':
            if self.peek() == '{' and self.peek2() == '{':
                self.advance()
                self.advance()
                parts.append('{')
            elif self.peek() == '}' and self.peek2() == '}':
                self.advance()
                self.advance()
                parts.append('}')
            elif self.peek() == '{':
                is_interp = True
                break
            elif self.peek() == '\\':
                self.advance()
                esc = self.advance()
                parts.append({'n': '\n', 't': '\t', '0': '\0', '\\': '\\', '"': '"'}.get(esc, esc))
            else:
                parts.append(self.advance())
        if self.peek() == '"':
            self.advance()
        return ''.join(parts), is_interp

    def tokenize(self):
        while self.peek() is not None:
            ch = self.peek()

            if ch == ' ' or ch == '\t' or ch == '\r':
                self.advance()
                continue

            if ch == '#':
                while self.peek() is not None and self.peek() != '\n':
                    self.advance()
                continue

            if ch == '\n':
                self.emit(TT.NEWLINE, '\n')
                self.advance()
                continue

            if ch.isalpha() or ch == '_':
                word = ''
                while self.peek() is not None and (self.peek().isalnum() or self.peek() == '_'):
                    word += self.advance()
                tt = KEYWORDS.get(word, TT.IDENT)
                self.emit(tt, word)
                continue

            if ch.isdigit():
                num = ''
                while self.peek() is not None and self.peek().isdigit():
                    num += self.advance()
                if self.peek() == '.' and self.peek2() is not None and self.peek2().isdigit():
                    num += self.advance()
                    while self.peek() is not None and self.peek().isdigit():
                        num += self.advance()
                self.emit(TT.NUMBER, num)
                continue

            if ch == '"':
                line = self.line
                string_val, has_interp = self.read_string()
                if has_interp:
                    self.emit(TT.STRING, string_val, line)
                else:
                    self.emit(TT.STRING, string_val, line)
                continue

            if ch == '+':
                self.emit(TT.PLUS, '+'); self.advance(); continue
            if ch == '-':
                self.emit(TT.MINUS, '-'); self.advance(); continue
            if ch == '*':
                self.emit(TT.STAR, '*'); self.advance(); continue
            if ch == '/':
                self.emit(TT.SLASH, '/'); self.advance(); continue
            if ch == '%':
                self.emit(TT.PERCENT, '%'); self.advance(); continue
            if ch == '(':
                self.emit(TT.LPAREN, '('); self.advance(); continue
            if ch == ')':
                self.emit(TT.RPAREN, ')'); self.advance(); continue
            if ch == '{':
                self.emit(TT.LBRACE, '{'); self.advance(); continue
            if ch == '}':
                self.emit(TT.RBRACE, '}'); self.advance(); continue
            if ch == ',':
                self.emit(TT.COMMA, ','); self.advance(); continue
            if ch == '.':
                self.emit(TT.DOT, '.'); self.advance(); continue

            if ch == '=' and self.peek2() == '=':
                self.emit(TT.EQ, '=='); self.advance(); self.advance(); continue
            if ch == '!' and self.peek2() == '=':
                self.emit(TT.NEQ, '!='); self.advance(); self.advance(); continue
            if ch == '<' and self.peek2() == '=':
                self.emit(TT.LTE, '<='); self.advance(); self.advance(); continue
            if ch == '>' and self.peek2() == '=':
                self.emit(TT.GTE, '>='); self.advance(); self.advance(); continue
            if ch == '<':
                self.emit(TT.LT, '<'); self.advance(); continue
            if ch == '>':
                self.emit(TT.GT, '>'); self.advance(); continue
            if ch == '=':
                self.emit(TT.ASSIGN, '='); self.advance(); continue
            if ch == '&' and self.peek2() == '&':
                self.emit(TT.AND, '&&'); self.advance(); self.advance(); continue
            if ch == '|' and self.peek2() == '|':
                self.emit(TT.OR, '||'); self.advance(); self.advance(); continue
            if ch == '!':
                self.emit(TT.NOT, '!'); self.advance(); continue

            self.advance()

        self.emit(TT.EOF, '')
        return self.tokens


def tokenize(src):
    return Lexer(src).tokenize()
