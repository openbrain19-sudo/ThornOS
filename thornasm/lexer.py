from enum import Enum, auto
from dataclasses import dataclass


class TokenType(Enum):
    IDENT = auto()
    NUMBER = auto()
    FLOAT = auto()
    STRING = auto()
    DOT_SIZE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    PLUS = auto()
    STAR = auto()
    MINUS = auto()
    COLON = auto()
    CMP_OP = auto()
    NEWLINE = auto()
    EOF = auto()


@dataclass
class Token:
    type: TokenType
    value: str
    line: int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, L{self.line})"


class Lexer:
    def __init__(self, src: str):
        self.src = src
        self.pos = 0
        self.line = 1

    def peek(self):
        if self.pos < len(self.src):
            return self.src[self.pos]
        return None

    def peek2(self):
        if self.pos + 1 < len(self.src):
            return self.src[self.pos + 1]
        return None

    def advance(self):
        if self.pos < len(self.src):
            ch = self.src[self.pos]
            self.pos += 1
            if ch == '\n':
                self.line += 1
            return ch
        return None

    def skip_whitespace(self):
        while self.peek() is not None and self.peek() in ' \t\r':
            self.advance()

    def read_word(self):
        word = ''
        while self.peek() is not None and (self.peek().isalnum() or self.peek() == '_'):
            word += self.advance()
        return word

    def read_number(self):
        word = ''
        if self.peek() == '0' and self.peek2() in ('x', 'X'):
            word += self.advance()  # '0'
            word += self.advance()  # 'x'
            while self.peek() is not None and self.peek() in '0123456789abcdefABCDEF':
                word += self.advance()
            return Token(TokenType.NUMBER, word, self.line)
        else:
            while self.peek() is not None and self.peek().isdigit():
                word += self.advance()
            if self.peek() == '.' and self.peek2() is not None and self.peek2().isdigit():
                word += self.advance()  # '.'
                while self.peek() is not None and self.peek().isdigit():
                    word += self.advance()
                return Token(TokenType.FLOAT, word, self.line)
            return Token(TokenType.NUMBER, word, self.line)

    def read_string(self):
        self.advance()  # opening "
        word = ''
        while self.peek() is not None and self.peek() != '"':
            if self.peek() == '\\':
                self.advance()
                esc = self.advance()
                if esc == 'n':
                    word += '\n'
                elif esc == 't':
                    word += '\t'
                elif esc == '0':
                    word += '\0'
                elif esc == '\\':
                    word += '\\'
                elif esc == '"':
                    word += '"'
                else:
                    word += esc
            else:
                word += self.advance()
        if self.peek() == '"':
            self.advance()  # closing "
        return Token(TokenType.STRING, word, self.line)

    def tokenize(self):
        tokens = []
        while self.peek() is not None:
            ch = self.peek()

            if ch in ' \t\r':
                self.skip_whitespace()
                continue

            if ch == '\n':
                tokens.append(Token(TokenType.NEWLINE, '\n', self.line))
                self.advance()
                continue

            if ch == '#':
                while self.peek() is not None and self.peek() != '\n':
                    self.advance()
                continue

            if ch.isalpha() or ch == '_':
                word = self.read_word()
                tokens.append(Token(TokenType.IDENT, word, self.line))
                continue

            if ch.isdigit():
                tokens.append(self.read_number())
                continue

            if ch == '"':
                tokens.append(self.read_string())
                continue

            if ch == '[':
                tokens.append(Token(TokenType.LBRACKET, '[', self.line))
                self.advance()
                continue

            if ch == ']':
                tokens.append(Token(TokenType.RBRACKET, ']', self.line))
                self.advance()
                continue

            if ch == '+':
                tokens.append(Token(TokenType.PLUS, '+', self.line))
                self.advance()
                continue

            if ch == '*':
                tokens.append(Token(TokenType.STAR, '*', self.line))
                self.advance()
                continue

            if ch == '-':
                tokens.append(Token(TokenType.MINUS, '-', self.line))
                self.advance()
                continue

            if ch == ':':
                tokens.append(Token(TokenType.COLON, ':', self.line))
                self.advance()
                continue

            if ch == '=' and self.peek2() == '=':
                tokens.append(Token(TokenType.CMP_OP, '==', self.line))
                self.advance()
                self.advance()
                continue

            if ch == '!' and self.peek2() == '=':
                tokens.append(Token(TokenType.CMP_OP, '!=', self.line))
                self.advance()
                self.advance()
                continue

            if ch == '<' and self.peek2() == '=':
                tokens.append(Token(TokenType.CMP_OP, '<=', self.line))
                self.advance()
                self.advance()
                continue

            if ch == '>' and self.peek2() == '=':
                tokens.append(Token(TokenType.CMP_OP, '>=', self.line))
                self.advance()
                self.advance()
                continue

            if ch == '<':
                tokens.append(Token(TokenType.CMP_OP, '<', self.line))
                self.advance()
                continue

            if ch == '>':
                tokens.append(Token(TokenType.CMP_OP, '>', self.line))
                self.advance()
                continue

            if ch == '.':
                if self.peek2() is not None and self.peek2() in '1248':
                    self.advance()  # skip '.'
                    size = self.advance()
                    tokens.append(Token(TokenType.DOT_SIZE, size, self.line))
                    continue
                # could be a float starting with . — skip for now
                self.advance()
                continue

            # unknown character, skip
            self.advance()

        tokens.append(Token(TokenType.EOF, '', self.line))
        return tokens


def tokenize_source(src: str):
    return Lexer(src).tokenize()


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else 'source.tsm'
    with open(path) as f:
        src = f.read()
    tokens = tokenize_source(src)
    for tok in tokens:
        print(tok)
