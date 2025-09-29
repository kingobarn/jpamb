import jpamb
from jpamb import jvm
from dataclasses import dataclass

import sys
from loguru import logger

from jpamb.jvm.opcode import Throw

logger.remove()
logger.add(sys.stderr, format="[{level}] {message}")

methodid, input = jpamb.getcase()


@dataclass
class PC:
    method: jvm.AbsMethodID
    offset: int

    def __iadd__(self, delta):
        self.offset += delta
        return self

    def __add__(self, delta):
        return PC(self.method, self.offset + delta)

    def __str__(self):
        return f"{self.method}:{self.offset}"


@dataclass
class Bytecode:
    suite: jpamb.Suite
    methods: dict[jvm.AbsMethodID, list[jvm.Opcode]]

    def __getitem__(self, pc: PC) -> jvm.Opcode:
        try:
            opcodes = self.methods[pc.method]
        except KeyError:
            opcodes = list(self.suite.method_opcodes(pc.method))
            self.methods[pc.method] = opcodes

        return opcodes[pc.offset]


@dataclass
class Stack[T]:
    items: list[T]

    def __bool__(self) -> bool:
        return len(self.items) > 0

    @classmethod
    def empty(cls):
        return cls([])

    def peek(self) -> T:
        return self.items[-1]

    def pop(self) -> T:
        return self.items.pop(-1)

    def push(self, value):
        self.items.append(value)
        return self

    def __str__(self):
        if not self:
            return "ϵ"
        return "".join(f"{v}" for v in self.items)


suite = jpamb.Suite()
bc = Bytecode(suite, dict())


@dataclass
class Frame:
    locals: dict[int, jvm.Value]
    stack: Stack[jvm.Value]
    pc: PC

    def __str__(self):
        locals = ", ".join(f"{k}:{v}" for k, v in sorted(self.locals.items()))
        return f"<{{{locals}}}, {self.stack}, {self.pc}>"

    def from_method(method: jvm.AbsMethodID) -> "Frame":
        return Frame({}, Stack.empty(), PC(method, 0))


@dataclass
class State:
    heap: dict[int, jvm.Value]
    frames: Stack[Frame]

    def __str__(self):
        return f"{self.heap} {self.frames}"


def step(state: State) -> State | str:
    assert isinstance(state, State), f"expected frame but got {state}"
    frame = state.frames.peek()
    opr = bc[frame.pc]
    logger.debug(f"STEP {opr}\n{state}")
    match opr:
        case jvm.Push(value=v):
            frame.stack.push(v)
            frame.pc += 1
            return state
        case jvm.Load(type=jvm.Int(), index=i):
            frame.stack.push(frame.locals[i])
            frame.pc += 1
            return state
        case jvm.Binary(type=jvm.Int(), operant=jvm.BinaryOpr.Div):
            v2, v1 = frame.stack.pop(), frame.stack.pop()
            assert v1.type is jvm.Int(), f"expected int, but got {v1}"
            assert v2.type is jvm.Int(), f"expected int, but got {v2}"
            if v2.value == 0:
                return "divide by zero"
            frame.stack.push(jvm.Value.int(v1.value // v2.value))
            frame.pc += 1
            return state
        case jvm.Return(type=jvm.Int()): # return instruction for ints
            v1 = frame.stack.pop()
            state.frames.pop()
            if state.frames:
                frame = state.frames.peek()
                frame.stack.push(v1)
                frame.pc += 1
                return state
            else:
                return "ok"
        case jvm.Return(type=None):
            state.frames.pop()
            if state.frames:
                frame = state.frames.peek()
                frame.pc += 1
                return state
            else:
                return "ok"
        case jvm.Get():
            frame.stack.push(0) #pushing false to the stack
            frame.pc += 1
            return state  
        case jvm.Boolean():
            frame.stack.push("Z")
            frame.pc += 1
            return state
        case jvm.Ifz():
            v1 = frame.stack.pop()
            logger.debug(f"v1: {v1}") #to print a message in the terminal
            if(v1 == 0):
                frame.pc += opr.target - frame.pc.offset
                logger.debug(f"opr.target: {opr.target}") #TA: s233852@dtu.dk
            else:
                frame.pc += 1
            return state
        case jvm.New():
            frame.stack.push(0)
            frame.pc += 1
            return state
        case jvm.Dup():
            v1 = frame.stack.pop()
            frame.stack.push(v1)
            frame.stack.push(v1)
            frame.pc += 1
            return state
        case a:
            raise NotImplementedError(f"Don't know how to handle: {a!r}")


frame = Frame.from_method(methodid)
for i, v in enumerate(input.values):
    match v:

        case jvm.Value(type=jvm.Reference()):
            pass
        case jvm.Value(type=jvm.Float()):
            pass
        case jvm.Value(type=jvm.Boolean(), value = value):
            v= jvm.Value.int(1 if value else 0)
        case jvm.Value(type=jvm.Int()):
            pass
        #case jvm.Value(type=jvm.Char()):

        case _:
            assert False, f"Do not know how to handle {v}"
    logger.debug(f"v has the value: {v}")
    frame.locals[i] = v

state = State({}, Stack.empty().push(frame))

for x in range(1000):
    state = step(state)
    if isinstance(state, str):
        print(state)
        break
else:
    print("*")