from array import array
import itertools
import struct
import sys


class VmInvalidInstruction(Exception):
    pass

class VmHalted(Exception):
    pass

opcodes = {
        0: ('halt', 0),
        1: ('set', 2),
        2: ('push', 1),
        3: ('pop', 1),
        4: ('eq', 3),
        5: ('gt', 3),
        6: ('jmp', 1),
        7: ('jt', 2),
        8: ('jf', 2),
        9: ('add', 3),
        10: ('mult', 3),
        11: ('mod', 3),
        12: ('and', 3),
        13: ('or', 3),
        14: ('not', 2),
        15: ('rmem', 2),
        16: ('wmem', 2),
        17: ('call', 1),
        18: ('ret', 0),
        19: ('out', 1),
        20: ('in', 1),
        21: ('noop', 0)
}


class VirtualMachine(object):

    def __init__(self):
        self.mem = array('H', itertools.repeat(0, 0x8000))
        self.reg = array('H', itertools.repeat(0, 8))
        self.stack = []

        self.pc = 0

    def load_image(self, filename, address=0):
        with open(filename, 'rb') as f:
            image = f.read()
        image = struct.unpack('%dH' % (len(image) >> 1), image)
        self.mem[address:address + len(image)] = array('H', image)

    def regs(self):
        return [('r%d' % i, v) for i, v in enumerate(self.reg)]

    def peek(self, address=None, length=None):
        if address is None:
            address = 0
        if length is None:
            return self.mem[address:]
        return self.mem[address:address+length]

    def fetch_instruction_mem(self, mem, pc):
        op = mem[pc]
        pc  = (pc + 1) % 32768

        try:
            nargs = opcodes[op][1]
        except KeyError:
            raise VmInvalidInstruction("Unknown opcode %d" % (op,))

        args = []
        try:
            for i in xrange(nargs):
                args.append(mem[pc])
                pc = (pc + 1) % 32768
        except IndexError:
            raise VmInvalidInstruction("Ran off the memory block while decoding")

        return op, args, pc

    def fetch_instruction(self,):
        op, args, pc = self.fetch_instruction_mem(self.mem, self.pc)
        self.pc = pc
        return op, args, pc

    def step(self):
        op, args, pc = self.fetch_instruction()
        fn = getattr(self, 'op_' + opcodes[op][0])
        fn(*args)

    def execute(self):
        try:
            while True:
                self.step()
        except (VmHalted, KeyboardInterrupt):
            print "HALTED: stopped at address %d (%04X)" % (self.pc, self.pc)

    def read_reg(self, r):
        '''
        Convert r into a register and return the contents of that register
        '''
        return self.reg[r - 32768]

    def write_reg(self, r, value):
        '''
        Convert r into a register and write [value] to that register
        '''
        # Question for szak: does <x> syntax mean its a register on arch sheet?
        self.reg[r - 32768] = self.value(value)

    def read_mem(self, addr):
        try:
            return self.mem[self.value(addr)]
        except IndexError:
            print 'Halting at read_mem...'
            self.op_halt()

    def write_mem(self, addr, value):
        try:
            self.mem[self.value(addr)] = self.value(value)
        except IndexError:
            print 'Halting at write_mem...'
            self.op_halt()

    def value(self, v):
        '''
        If v is between 0 and 32767 (inclusive), return it, otherwise return the
        value at register v mod 32768
        '''
        # NOTE: Pay attention to when you need to use me!
        if v >= 0 and v <= 32767:
            return v
        return self.read_reg(v)

    def op_noop(self):
        '''
        Do... nothin'!
        '''
        pass

    def op_halt(self):
        '''
        Halt operations
        '''
        raise VmHalted()

    def op_out(self, a):
        '''
        Write the character represented by ascii code <a> to the terminal
        '''
        v = self.value(a)
        sys.stdout.write(chr(v))

    def op_jmp(self, a):
        '''
        Jump to <a>
        '''
        #print 'jmp - %s' % a
        self.pc = self.value(a)

    def op_jt(self, a, b):
        '''
        If <a> is nonzero, jump to <b>
        '''
        if self.value(a) != 0:
            #print 'jt (a = %s) - %s' % (a, b)
            self.op_jmp(b)

    def op_jf(self, a, b):
        '''
        If <a> is 0, jump to <b>
        '''
        if self.value(a) == 0:
            #print 'jf (a = %s) - %s' % (a, b)
            self.op_jmp(b)

    def op_set(self, a, b):
        '''
        Set register <a> to the value of <b>
        '''
        self.write_reg(a, b)

    def op_add(self, a, b, c):
        '''
        Assign into <a> the value of <b> and <c> (modulo 32768)
        '''
        # 15 bit math! Keep lowest 15 bits -> [math operand] & 0x7FFF
        val1 = self.value(b)
        val2 = self.value(c)

        self.write_reg(a, (val1 + val2 & 0x7FFF))

    def op_eq(self, a, b, c):
        '''
        Set <a> to 1 if <b> is equal to <c> - set it to 0 otherwise
        '''
        if self.value(b) == self.value(c):
            self.write_reg(a, 1)
        else:
            self.write_reg(a, 0)

    def op_push(self, a):
        '''
        Push <a> onto the stack
        '''
        self.stack.append(self.value(a))

    def op_pop(self, a):
        '''
        Remove the top element form the stack and write it into <a>; Error if
        empty
        '''
        try:
            val = self.stack.pop()
            self.write_reg(a, val)
        except IndexError:
            self.op_halt()

    def op_gt(self, a, b, c):
        '''
        Set <a> to 1 if <b> is greater than <c> - otherwise set it to 0
        '''
        if self.value(b) > self.value(c):
            self.write_reg(a, 1)
        else:
            self.write_reg(a, 0)

    def op_and(self, a, b, c):
        '''
        Store into <a> the bitwise AND of <b> and <c>
        '''
        val = self.value(b) & self.value(c)
        self.write_reg(a, val)

    def op_or(self, a, b, c):
        '''
        Store into <a> the bitwise OR of <b> and <c>
        '''
        val = self.value(b) | self.value(c)
        self.write_reg(a, val)

    def op_not(self, a, b):
        '''
        Store 15-bit bitwise inverse of <b> into <a>
        '''
        val = self.value(b) ^ 0x7FFF
        self.write_reg(a, val)

    def op_call(self, a):
        '''
        Write the address of the next instruction on the stack and jump to <a>
        '''
        self.stack.append(self.pc)
        self.op_jmp(a)

    def op_mult(self, a, b, c):
        '''
        Store into <a> the product of <b> and <c> (modulo 32768)
        '''
        val = self.value(b) * self.value(c) & 0x7FFF
        self.write_reg(a, val)

    def op_mod(self, a, b, c):
        '''
        Store into <a> the remainder of <b> divided by <c>
        '''
        val = self.value(b) % self.value(c)
        self.write_reg(a, val)

    def op_rmem(self, a, b):
        '''
        Read memory at address <b> and write it to <a>
        '''
        val = self.read_mem(b)
        self.write_reg(a, val)

    def op_wmem(self, a, b):
        '''
        Write the value in <b> into memory address <a>
        '''
        val = self.value(b)
        self.write_mem(a, val)

    def op_ret(self):
        '''
        Remove the top element from the stack and jump to it. Halt on empty
        stack
        '''
        try:
            val = self.stack.pop()
            self.op_jmp(val)
        except IndexError:
            self.op_halt()

    def op_in(self, a):
        '''
        Read a character from the terminal and write its ascii code to <a>. It
        can be assumed that once input starts, it will continue until a new line
        is encountered. This means you can safely real whole lines from the
        keyboard and trust that they will be fully read.
        '''
        while True:
            try:
                c = sys.stdin.read(1)
                break
            except IOError:
                pass
        self.write_reg(a, ord(c))


if __name__ == '__main__':
    vm = VirtualMachine()
    vm.load_image(sys.argv[1])
    vm.execute()

