import serial
import time, struct, binascii
import argparse
import sys

ocd_id = [0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x87, 0x27, 0x75, 0x54]   # sur-ron 

def delay(amount):
    now = start = time.perf_counter()
    while True:
        now = time.perf_counter()
        if now - start >= amount:
            return

# for C232HM-DDHSL-0 cable
WIRE_ORANGE = 1 << 0
WIRE_YELLOW = 1 << 1
WIRE_GREEN = 1 << 2
WIRE_BROWN = 1 << 3
WIRE_GRAY = 1 << 4
WIRE_PURPLE = 1 << 5
WIRE_WHITE = 1 << 6
WIRE_BLUE = 1 << 7

class Reset:
    def __init__(s, port):
        # init gpio mode with gray (conncted to RESET) and green (TOOL0) as outputs
        s.port = port        

    def enter_rom(s):
        # reset nodemcu
        s.port.setDTR(False)    
        time.sleep(0.05)
        s.port.setDTR(True)    
        time.sleep(0.5)        
        s.port.read(1000)

def read_all(port, size):
    data = b''
    while len(data) < size:
        data += port.read(size - len(data))
    assert len(data) == size
    return data

def size8(size):
    if size <= 0 or size > 0x100: return None
    if size == 0x100: size = 0
    return size

def pack24(x):
    assert x < (1 << 24)
    return struct.pack('<HB', x & 0xffff, x >> 16)

class ProtoA:
    SOH = 0x01
    STX = 0x02
    ETB = 0x17
    ETX = 0x03

    COM_RESET           = 0x00
    COM_19              = 0x19 # undocumented cmd. sets FSSQ=2
    COM_ERASE           = 0x22
    COM_PROG            = 0x40
    COM_VERIFY          = 0x13
    COM_BLANK_CHECK     = 0x32
    COM_BAUDRATE_SET    = 0x9a
    COM_SILICON_SIG     = 0xc0
    COM_SEC_SET         = 0xa0
    COM_SEC_GET         = 0xa1
    COM_SEC_RLS         = 0xa2
    COM_CHECKSUM        = 0xb0

    ST_COM_NUM_ERR  = 0x04
    ST_PARAM_ERR    = 0x05
    ST_ACK          = 0x06
    ST_SUM_ERR      = 0x07
    ST_VERIFY_ERR   = 0x0f
    ST_PROTECT_ERR  = 0x10
    ST_NACK         = 0x15
    ST_ERASE_ERR    = 0x1a
    ST_BLANK_ERR    = 0x1b
    ST_WRITE_ERR    = 0x1c

    def __init__(s, port):
        s.port = port

    def read_all(s, size):
        return read_all(s.port, size)

    def _checksum(s, data):
        csum = 0
        for d in data:
            csum -= d
            csum &= 0xff
        return csum

    def _checksum16(s, data):
        csum = 0
        for d in data:
            csum -= d
            csum &= 0xffff
        return csum

    def recv_frame(s):
        while s.port.read() != bytes([s.STX]):
            pass
        len_b = s.port.read()        
        #LEN = size8(struct.unpack('B', len_b)[0])        
        LEN = len_b[0]
        if LEN == 0:
            LEN = 256
        recv_len = LEN + 2
        data = s.read_all(recv_len)
        #print('recv %s' % (binascii.hexlify(data)))
        if s._checksum(len_b + data[:LEN]) != data[LEN]:
            print('bad checksum')
        if data[LEN+1] != s.ETX and data[LEN+1] != s.ETB:
            print('bad footer %02X' % data[LEN+1])
        return data[:LEN]

    def _send_frame(s, data, is_cmd = True, last_data = True):
        header = s.SOH if is_cmd else s.STX
        trailer = s.ETX if last_data else s.ETB
        LEN = size8(len(data))
        SUM = s._checksum(struct.pack('B', LEN) + data)
        cmd = struct.pack('BB%dBBB' % (len(data)), header, LEN, *data, SUM, trailer)
        # print('send %s' % (binascii.hexlify(cmd)))
        s.port.write(cmd)
        # discard the loopback bytes        
        return s.recv_frame()

    def send_frame(s, data, is_cmd = True, last_data = True):
        while True:
            r = s._send_frame(data, is_cmd, last_data)
            if r[0] != s.ST_SUM_ERR:
                return r

    def reset(s):
        return s.send_frame(struct.pack('B', s.COM_RESET))

    def set_baudrate(s, baudrate, voltage):
        return s.send_frame(struct.pack('BBB', s.COM_BAUDRATE_SET, baudrate, voltage))

    def silicon_sig(s):
        r = s.send_frame(struct.pack('B', s.COM_SILICON_SIG))
        if r[0] != s.ST_ACK: return None
        return s.recv_frame()

    def security_get(s):
        r = s.send_frame(struct.pack('B', s.COM_SEC_GET))
        if r[0] != s.ST_ACK: return None
        return s.recv_frame()

    def security_set(s, sec):
        r = s.send_frame(struct.pack('B', s.COM_SEC_SET))
        if r[0] != s.ST_ACK: return None
        return s.send_frame(sec, False)[0] == s.ST_ACK

    def verify(s, addr, data): 
        #print(hex(addr))
        #print('vv %s' % (binascii.hexlify(data)))
        assert len(data) > 0        
        SA = pack24(addr)
        EA = pack24(addr + len(data) - 1)
        r = s.send_frame(struct.pack('B', s.COM_VERIFY) + SA + EA)
        if r[0] != s.ST_ACK: return False        
        for i in range(0, len(data), 0x100):
            last_data = len(data) - i <= 0x100            
            r = s.send_frame(data[i:i+0x100], False, last_data)            
            r = s.recv_frame()
            if r[0] != s.ST_ACK or r[1] != s.ST_ACK:
                return False        
        return True

    def checksum(s, addr, size):
        assert size > 0
        SA = pack24(addr)
        EA = pack24(addr + size - 1)
        r = s.send_frame(struct.pack('B', s.COM_CHECKSUM) + SA + EA)
        if r[0] != s.ST_ACK: return None
        return struct.unpack('<H', s.recv_frame())[0]

    def blank_check(s, addr, size=0x400):
        assert size > 0
        SA = pack24(addr)
        EA = pack24(addr + size - 1)
        # XXX
        D01 = struct.pack('B', 0)
        r = s.send_frame(struct.pack('B', s.COM_BLANK_CHECK) + SA + EA + D01)
        if r[0] not in (s.ST_ACK, s.ST_BLANK_ERR):
            return None
        # True means it is blank
        return r[0] == s.ST_ACK

    def invert_boot_cluster(s):
        # XXX can't be set via protoA :'(
        sec = s.security_get()
        sec = bytes([sec[0] ^ 1, *sec[1:]])
        return s.security_set(sec)

    def cmd19(s):
        # this is standalone "internal verify"
        addr = 0
        size = 0x400
        assert (((addr >> 8) & 0xff) & 3) == 0
        assert ((((addr + size - 1) >> 8) & 0xff) & 3) == 3
        SA = pack24(addr)
        EA = pack24(addr + size - 1)
        return s.send_frame(struct.pack('B', s.COM_19) + SA + EA)

    def erase_block(s, addr):
        return s.send_frame(struct.pack('B', s.COM_ERASE) + pack24(addr))

    def program(s, addr, data):
        SA = pack24(addr)
        EA = pack24(addr + len(data) - 1)
        r = s.send_frame(struct.pack('B', s.COM_PROG) + SA + EA)
        if r[0] != s.ST_ACK: return False
        for i in range(0, len(data), 0x100):
            last_data = len(data) - i <= 0x100
            r = s.send_frame(data[i:i+0x100], False, last_data)
            r = s.recv_frame()            
            if r[0] != s.ST_ACK or r[1] != s.ST_ACK:
                return False
        # iverify status
        return s.recv_frame()

    def write(s, addr, data):
        # erase block = 0x400, everything else can use 0x100
        if addr % 0x400 or len(data) % 0x400:
            return False
        for i in range(0, len(data), 0x400):
            s.erase_block(addr + i)
        # XXX should be able to handle multiple blocks, not sure why it hangs
        #s.program(addr, data)
        for i in range(0, len(data), 0x100):
            s.program(addr + i, data[i:i+0x100])
        return s.verify(addr, data)

class ProtoOCD:
    SYNC = 0x00
    PING = 0x90
    UNLOCK = 0x91
    READ = 0x92
    WRITE = 0x93
    EXEC = 0x94
    EXIT_RETI = 0x95
    EXIT_RAM = 0x97

    PONG = bytes([3, 3])

    ST_UNLOCK_ALREADY = 0xf0
    ST_UNLOCK_LOCKED = 0xf1
    ST_UNLOCK_OK = 0xf2
    ST_UNLOCK_SUM = 0xf3
    ST_UNLOCK_NG = 0xf4

    def __init__(s, port):
        s.port = port
    def read_all(s, size):
        return read_all(s.port, size)
    def checksum(s, data):
        csum = 0
        for d in data:
            csum += d
            csum &= 0xff
        csum -= 1
        csum &= 0xff
        return csum
    def send_cmd(s, cmd):
        #print('send %s' % (binascii.hexlify(cmd)))
        s.port.write(cmd)
        # discard the loopback bytes
        s.read_all(len(cmd))
    def wait_ack(s):
        while s.read_all(1) != bytes([s.SYNC]):
            pass
    def sync(s):
        s.send_cmd(struct.pack('B', s.SYNC))
        s.wait_ack()
    def ping(s):
        s.send_cmd(struct.pack('B', s.PING))
        return s.read_all(len(s.PONG)) == s.PONG
        #return s.read_all(len(ping_result)) == ping_result
    def unlock(s, ocd_id, corrupt_sum = False):
        s.send_cmd(struct.pack('B', s.UNLOCK))
        status = s.read_all(1)[0]
        # f0: already unlocked
        # f1: need to send
        if status == s.ST_UNLOCK_ALREADY:
            print('already unlocked')
            return True
        if status != s.ST_UNLOCK_LOCKED:
            print('unexpected status')
            return False
        csum = s.checksum(ocd_id)
        if corrupt_sum:
            csum += 1
            csum &= 0xff
        s.send_cmd(struct.pack('10BB', *ocd_id, csum))
        status = s.read_all(1)[0]
        # f2: success
        # f3: checksum mismatch
        # f4: checksum matched but ocd_id did not (could trigger flash erase?)
        if status != s.ST_UNLOCK_OK:
            print('unlock failed: %x' % (status))
        return status == s.ST_UNLOCK_OK
    def read(s, offset, size):
        size8_ = size8(size)
        if size8_ is None: return None
        s.send_cmd(struct.pack('<BHB', s.READ, offset, size8_))
        return s.read_all(size)
    def write(s, addr, data):
        size = size8(len(data))
        if size is None: return None        
        s.send_cmd(struct.pack('<BHB', s.WRITE, addr, size) + bytes(data))            
        return s.read_all(1)[0] == s.WRITE
    def call_f07e0(s):
        s.send_cmd(struct.pack('B', s.EXEC))
        return s.read_all(1)[0] == s.EXEC
    def leave(s, to_ram = False):
        cmd = s.EXIT_RAM if to_ram else s.EXIT_RETI
        s.send_cmd(struct.pack('B', cmd))
        return s.read_all(1)[0] == cmd

class RL78:
    MODE_A_1WIRE = b'\x3a'
    MODE_A_2WIRE = b'\x00'
    MODE_OCD = b'\xc5'
    BAUDRATE_INIT = 115200
    BAUDRATE_FAST = 1000000
    def __init__(s, port):
        s.reset_ctl = Reset(port)
        s.port = port
        s.a = ProtoA(s.port)
        s.ocd = ProtoOCD(s.port)
        s.mode = None
    def reset(s, mode):
        s.mode = mode
        s.port.baudrate = s.BAUDRATE_INIT
        s.reset_ctl.enter_rom()

        print("enter bootloader mode: %02X" % (mode[0]))
        s.port.write(s.mode)
        # we'll see the reset as a null byte. discard it and the init byte
        resp = read_all(s.port, 3)
        if resp[0] != 0x00 or resp[1] != mode[0]:
            return False
        
        # send baudrate cmd (required) & sync
        #baudrate = s.BAUDRATE_FAST if s.mode != s.MODE_OCD else s.BAUDRATE_INIT
        baudrate = s.BAUDRATE_INIT
        rl78_br = {115200: 0, 250000: 1, 500000: 2, 1000000: 3}[baudrate]
        # 21 = 2.1v
        # really just sets internal voltage regulator to output 1.7, 1.8 or 2.1 volts
        # regulator seems to auto-adjust anyways...
        # feeding with 1.7v uses slower mode, 1.8v and 2.1v are same, slightly faster speed
        r = s.a.set_baudrate(rl78_br, 34)
        #s.port.baudrate = baudrate        
        if r[0] != ProtoA.ST_ACK: return False
        delay(.01)
        if s.mode != s.MODE_OCD:
            r = s.a.reset()
            if r[0] != ProtoA.ST_ACK: return False
        else:
            s.ocd.wait_ack()
            if not s.ocd.ping(): return False
        return True


def program(rl78: RL78, filename, addr=0):
    blocksize = 0x400
    with open(filename, 'rb') as f:
        data = f.read()
        if(len(data) % blocksize):
            print('len not multiple of blocksize')
            return False
        
        if addr != 0 and addr != 0xF1000:
            print('invalid adress')
            return False
        elif addr== 0 and len(data) != 0x8000:
            print('len not 0x8000')
            return False
        elif addr== 0xF1000 and len(data) != 0x800:
            print('len not 0x800')
            return False
                
        for offset in range(0, len(data), blocksize):     
            if not rl78.a.verify(addr + offset, data[offset:offset+blocksize]):
                print('%06X: verify failed, reprogramming' % (addr + offset))
                res = rl78.a.write(addr + offset, data[offset:offset+blocksize])
                if not res:
                    print('%06X: failed to write' % (addr + offset))
                    return False                
            else:
                print('%06X: verify passed' % (addr +offset))        
    return True
    
def writeUInt16(data, offset=0, value=0):
    data[offset] = value & 0xFF
    data[offset+1] = ((value >> 8) & 0xFF)


def ocd_runcode(rl78: RL78, data):            
    rl78.ocd.write(0x07E0, [0xec,0x00,0xfb,0x0f])    # write tampoline code to jump to FB00        
    rl78.ocd.write(0xFB00, data)  # there is more space to use  
    return rl78.ocd.call_f07e0()

def dumpflash3(rl78: RL78, filename, offset=0, size=0x10000):    
    with open(filename,"wb") as of:
        while size > 0:            
            segsize = min(0x10000-(offset&0xFFFF),size)
            print("dumping %06X - %06X" % (offset, offset+segsize-1))
            data = dumpregion(rl78, offset, segsize)
            if len(data) == 0:
                print("read error")
                break
            of.write(data)
            of.flush()
            offset+=len(data)
            size-=len(data)

def dumpregion(rl78, addr, size):
    """
        ; setup Stackpointer to userspace, the rom code points to 0xf0df8 (reserved area)
        movw ax,sp
        movw sp, #0FE20h
        push ax
    """
    savestack = [0xAE,0xF8,     0xCB,0xF8,0x20,0xFE,    0xC1]    
    
    """
        push ax
        push de
        MOV     A, ES
        push AX

        mov     es, #0          ;segment            <- param 1
        movw    de, #0x1233     ;start offset       <- param 2
        set1    !0xF0090.0    ; enabled access to data flash

        dumploop:
        mov     a, es:[de]
        call    !!uartsend 
        incw    de
        movw    ax, de
        cmpw    ax, #0x1234     ;len +1             <- param 3
        bnz     $dumploop

        pop ax
        mov es,a
        pop de
        pop ax
    """
    shellcode = [
       #                              AAAA      BBBB BBBB                                                                  CCCC CCCC
       #0000,0001,0002,0003,0004,0005,0006,0007,0008,0009,000A,000B,000C,000D,000E,000F,0010,0011,0012,0013,0014,0015,0016,0017,0018               
       # AAAA = Segment 00-0F
       # BBBB = Start Address
       # CCCC = End Address                                                                        
        0xC1,0xC5,0x8E,0xFD,0xC1,0x41,0x00,0x34,0x33,0x12,0x71,0x00,0x90,0x00,0x11,0x89,0xFC,0xA1,0xFF,0x0E,0xA5,0x15,0x44,0x34,0x12,0xDF,0xF3,0xC0,0x9E,0xFD,0xC4,0xC0
    ]

    """
        ; restore Stackpointer
        pop ax
        movw sp,ax
        ret
    """    
    restorestack_ret = [0xc0,   0xbe,0xf8, 0xD7]

    eoffset = (addr +size) &0xFFFF
    shellcode[0x06] = (addr>>16) & 0x0F
    writeUInt16(shellcode, 0x08, addr & 0xFFFF)
    writeUInt16(shellcode, 0x17, eoffset & 0xFFFF)
    ocd_runcode(rl78,savestack + shellcode + restorestack_ret)   # EFFA1
    
    result = b""
    blocksize = 4096    
    while len(result)< size:
        data = rl78.port.read(blocksize)
        if len(data) == 0:
            print("incomplete, pagejump?")
            break
        result += data            
    return result
    
if __name__ == '__main__':

    def auto_int(x):
            return int(x, 0)
    
    parser = argparse.ArgumentParser()
    

    commands = parser.add_subparsers(dest='command')

    parser_a = commands.add_parser('program', help='program flash')
    parser_a.add_argument('-p', '--port', dest='port', help='programmer device', required=True)
    parser_a.add_argument('-i', '--input', dest='filename', help='filename of the input file', required=True)
    parser_a.add_argument('-a', '--address', type=auto_int, dest='offset', help='start address of the data to be written', required=True)
    #parser_a.add_argument('-s', '--skip', type=bool, dest='skipEmpty', help='skip empty blocks', default=False)


    parser_b = commands.add_parser('read', help='dump flash to file')
    parser_b.add_argument('-p', '--port', dest='port', help='programmer device', required=True)
    parser_b.add_argument('-o', '--output', dest='filename', help='filename of the output file', required=True)
    parser_b.add_argument('-a', '--address', type=auto_int, dest='offset', help='start address of the data to read', required=True)    
    parser_b.add_argument('-l', '--length', type=auto_int, dest='length', help='number of bytes to be read', required=True)
    
    parser_c = commands.add_parser('info', help='print rl78 silicon and security infos')
    parser_c.add_argument('-p', '--port', dest='port', help='programmer device', required=True)


    
    kwargs = parser.parse_args()
    with serial.Serial(kwargs.port, 115200, timeout=1) as ser:
    #with serial.Serial('/dev/cu.usbserial-0001', 115200, timeout=1) as ser:
        rl78 = RL78(ser)
        if kwargs.command == 'program':                
            if not rl78.reset(RL78.MODE_A_1WIRE):
                print('failed to init a')
                exit()
            print("start writing at address: 0x%06X ..." % kwargs.offset)         
            program(rl78, kwargs.filename, kwargs.offset)   
            print("Done!")
            exit()
                
        elif kwargs.command == 'read':                        
            if not rl78.reset(RL78.MODE_OCD):
                print('failed to init ocd')
                exit()
            print("Check OCD Version: %s" % rl78.ocd.ping())
            if ocd_id is not None:
                unlockresponse = rl78.ocd.unlock(ocd_id)
                print("OCD Unlock: %s" % unlockresponse)
            print("start reading at address: 0x%06X ..." % kwargs.offset)            
            dumpflash3(rl78, kwargs.filename,kwargs.offset,kwargs.length)
            print("writing output file '%s'" % kwargs.filename)       
            print("Done!")
            exit()

        if kwargs.command == 'info':
            if not rl78.reset(RL78.MODE_A_1WIRE):
                print('failed to init a')
                exit()
            print('sig: %s' % binascii.hexlify(rl78.a.silicon_sig()))
            print('sec: %s' % binascii.hexlify(rl78.a.security_get()))                                    
            print("Done!")
            exit()
