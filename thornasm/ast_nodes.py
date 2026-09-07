from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MoveNode:
    dst: str
    src: str
    size: Optional[str] = None


@dataclass
class AddNode:
    dst: str
    src: str


@dataclass
class SubNode:
    dst: str
    src: str


@dataclass
class MulNode:
    dst: str
    src: str


@dataclass
class SMulNode:
    dst: str
    src: str


@dataclass
class DivNode:
    dst: str
    src: str


@dataclass
class SDivNode:
    dst: str
    src: str


@dataclass
class AwcNode:
    dst: str
    src: str


@dataclass
class SwbNode:
    dst: str
    src: str


@dataclass
class AndNode:
    dst: str
    src: str


@dataclass
class OrNode:
    dst: str
    src: str


@dataclass
class XorNode:
    dst: str
    src: str


@dataclass
class ShlNode:
    dst: str
    src: str


@dataclass
class ShrNode:
    dst: str
    src: str


@dataclass
class AsrNode:
    dst: str
    src: str


@dataclass
class RotlNode:
    dst: str
    src: str


@dataclass
class RotrNode:
    dst: str
    src: str


@dataclass
class RaclNode:
    dst: str
    src: str


@dataclass
class RacrNode:
    dst: str
    src: str


@dataclass
class LmaNode:
    dst: str
    src: str


@dataclass
class SwapNode:
    dst: str
    src: str


@dataclass
class MoveSxNode:
    dst: str
    src: str


@dataclass
class MoveZxNode:
    dst: str
    src: str


@dataclass
class FaddNode:
    dst: str
    src: str


@dataclass
class FsubNode:
    dst: str
    src: str


@dataclass
class FmulNode:
    dst: str
    src: str


@dataclass
class FdivNode:
    dst: str
    src: str


@dataclass
class FmoveNode:
    dst: str
    src: str


@dataclass
class FcmpNode:
    dst: str
    src: str


@dataclass
class IncNode:
    reg: str


@dataclass
class DecNode:
    reg: str


@dataclass
class NegNode:
    reg: str


@dataclass
class NotNode:
    reg: str


@dataclass
class CmpNode:
    left: str
    op: str
    right: str
    label: str


@dataclass
class CmpFlagNode:
    flag: str
    label: str


@dataclass
class GoNode:
    label: str


@dataclass
class CallNode:
    name: str


@dataclass
class ReturnNode:
    pass


@dataclass
class PushNode:
    value: str


@dataclass
class PopNode:
    reg: str


@dataclass
class FnNode:
    name: str
    body: list
    fn_type: str  # "normal", "global", "raw"


@dataclass
class ExternNode:
    name: str


@dataclass
class LabelNode:
    name: str


@dataclass
class LoopNode:
    body: list


@dataclass
class ModuleNode:
    kind: str  # "code", "data", "reserve"
    body: list


@dataclass
class InterruptHandlerNode:
    number: str
    body: list


@dataclass
class RepMovsNode:
    pass


@dataclass
class RepStosNode:
    pass


@dataclass
class SyscallNode:
    pass


@dataclass
class NopeNode:
    pass


@dataclass
class HaltNode:
    pass


@dataclass
class IoffNode:
    pass


@dataclass
class IonNode:
    pass


@dataclass
class PrNode:
    dst: str
    port: str


@dataclass
class PwNode:
    port: str
    src: str


@dataclass
class IntNode:
    number: str


@dataclass
class RetiNode:
    pass


@dataclass
class SetNode:
    reg: str
    flag: str


@dataclass
class OriginNode:
    address: str


@dataclass
class DataDefNode:
    name: str
    value: str
    size: Optional[str] = None


@dataclass
class AliasNode:
    reg: str
    name: str
