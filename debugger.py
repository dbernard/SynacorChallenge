import vm
import cmd
import sys
import string
import pickle

from StringIO import StringIO


def chunks(seq, size):
  d, m = divmod(len(seq), size)
  for i in range(d):
    yield seq[i*size:(i+1)*size]
  if m:
    yield seq[d*size:]


def display_chr(c):
    if c >= 256:
        return '.'

    c = chr(c)

    if c in string.letters or c in string.digits or c in string.punctuation:
        return c

    return '.'


def format_chunk(addr, chunk, chunk_size):
    s = StringIO()
    hex_width = (chunk_size * 5) + 3
    s.write('%04Xh: ' % (addr,))
    vals = ' '.join('%04X' % v for v in chunk)
    chrs = ''.join(display_chr(v) for v in chunk)
    s.write(vals)
    s.write(' ' * (hex_width - len(vals)))
    s.write(chrs)
    return s.getvalue()


def print_mem(start_addr, mem):
    for chunk in chunks(mem, 16):
        line = format_chunk(start_addr, chunk, 16)
        print line
        start_addr += len(chunk)


def is_hex(s):
    return all(c in '0123456789abcdefABCDEF' for c in s)


class Debugger(cmd.Cmd):
    '''
    Need:
        * regs - dump the current state of registers including the pc
        * disassemble - dumps from PC forward some number of instructions
        * mem - dump memory contents
        * poke - write data into mem
        * run - runs the vm until halts
        * step - executes one instruction
        * exit - leave the debugger
    '''
    prompt = '(sdb) '

    def __init__(self, filename=None):
        cmd.Cmd.__init__(self)
        # Could also use: super(Debugger, self).__init__()
        # (Method Resolution Order - "super" keeps state, init objects left to
        # right BUT all must call super)

        self.vm = vm.VirtualMachine()
        if filename:
            self.vm.load_image(filename)

    def try_convert(self, arg):
        if arg in ('r0', 'r1', 'r2', 'r3', 'r4', 'r5', 'r6', 'r7'):
            return self.convert_reg(arg)
        elif arg in ('@r0', '@r1', '@r2', '@r3', '@r4', '@r5', '@r6', '@r7'):
            return self.convert_reg_read(arg[1:])
        elif arg == 'pc':
            return self.vm.pc
        elif arg.startswith('0x') and is_hex(arg[2:]):
            return self.convert_hex(arg[2:])
        elif arg.startswith('*') and is_hex(arg[1:]):
            return self.convert_mem(arg[1:])
        elif all(c in string.digits for c in arg):
            return int(arg)
        else:
            return arg

    def convert_reg(self, arg):
        reg = int(arg[1])
        converted_reg = reg + 32768
        return converted_reg

    def convert_reg_read(self, arg):
        reg = self.convert_reg(arg)
        return self.vm.read_reg(reg)

    def convert_hex(self, arg):
        converted_hex = int(arg, 16)
        return converted_hex

    def convert_mem(self, arg):
        val = self.vm.read_mem(int(arg, 16))

    def parse_args(self, args):
        # re.split(r'\s+', (string).strip())
        args = args.split()
        converted_args = []

        for arg in args:
            converted_args.append(self.try_convert(arg))

        return converted_args

    def convert_op_arg(self, arg):
        if arg >= 32768:
            return 'r%d' % (arg - 32768,)
        return str(arg)

    def disassemble_op(self, op, args, compact=False):
        instruction = ['%04X' % op] + ['%04X' % arg for arg in args]
        instruction = ' '.join(instruction)

        if compact:
            s = "%s  %s %s" % (instruction, vm.opcodes[op][0],
                    ' '.join(self.convert_op_arg(x) for x in args))
        else:
            s = "%-23s %s %s" % (instruction, vm.opcodes[op][0],
                    ' '.join(self.convert_op_arg(x) for x in args))

        # Show the ascii character for the out opcode
        if op == 19 and args[0] < 256:
            if compact:
                s += '  # %r' % (chr(args[0]),)
            else:
                s += '\t# %r' % (chr(args[0]),)

        return s

    def get_instructions(self, mem):
        while mem:
            try:
                op, args, pc = self.vm.fetch_instruction_mem(mem, 0)

                # Since fetch_instruction_mem believes our current pc is 0,
                # the returned pc is actually the number of words in the
                # instruction.  Let's return it so that the disassembler can
                # keep track of the current address while disassembling regions.
                yield op, args, pc
                mem = mem[pc:]
            except vm.VmInvalidInstruction:
                break
        return

    def do_disassemble(self, args):
        '''Disassemble a section of memory.'''
        args = self.parse_args(args)
        if len(args) > 0:
            start_addr = args[0]
        else:
            start_addr = 0

        if len(args) > 1:
            length = args[1]
        else:
            length = None

        mem = self.vm.peek(start_addr, length)
        addr = start_addr
        for op, args, size in self.get_instructions(mem):
            print '   %5d:   %s' % (addr, self.disassemble_op(op, args))
            addr += size

    do_d = d_dis = do_disassemble

    def do_save(self, args):
        # NOTE: I am aware this is very sloppy saving/loading... Was a quick
        # implementation to get something working.
        mem_file = 'mem.txt'
        pc_file = 'pc.txt'
        stack_file = 'stack.txt'

        with open(mem_file, 'wb') as file:
            pickle.dump(self.vm.txmem, file)

        with open(pc_file, 'wb') as file:
            pickle.dump(self.vm.pc, file)

        with open(stack_file, 'wb') as file:
            pickle.dump(self.vm.stack, file)

    def do_load(self, args):
        mem_file = 'mem.txt'
        pc_file = 'pc.txt'
        stack_file = 'stack.txt'

        with open(mem_file, 'rb') as file:
            self.vm.txmem = pickle.load(file)

        with open(pc_file, 'rb') as file:
            self.vm.pc = pickle.load(file)

        with open(stack_file, 'rb') as file:
            self.vm.stack = pickle.load(file)

    def do_poke(self, args):
        args = self.parse_args(args)
        reg = args[0]
        val = args[1]

        self.vm.write_reg(reg, val)
        self.vm.txmem.commit()

    def do_backtrace(self, args):
        bt = self.vm.backtrace
        for entry in bt:
            print '%s -> %s' % (entry[0], entry[1])

    do_bt = do_backtrace

    def do_regs(self, args):
        regs = self.vm.regs()
        pc = self.vm.pc

        # print regs here
        #for i, v in enumerate(regs):
        #    pass
        print "Register Contents"
        print "-----------------"
        for entry in regs:
            print "  %s: %d (%04Xh)" % (entry[0], entry[1], entry[1])

        print "  pc: %d, (%04Xh)" % (pc, pc)

        #op, args, _ = self.vm.fetch_instructions_mem(self.vm.mem, pc)

    do_r = do_regs

    def do_exit(self, args):
        '''
        Exit debugger
        '''
        sys.exit(0)

    do_quit = do_EOF = do_exit

    def do_step(self, args):
        '''
        Step a single instruction
        '''
        try:
            self.vm.step()
        except (vm.VmHalted, KeyboardInterrupt):
            pass

    def do_run(self, args):
        '''
        Execute an instruction at the current PC
        '''
        self.vm.execute()

    def do_mem(self, args):
        '''
        Dump memory contents
        '''
        start_addr = 0
        length = None
        mem = self.vm.peek(start_addr, length)
        print_mem(start_addr, mem)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = None

    d = Debugger(filename=filename)
    d.cmdloop()
