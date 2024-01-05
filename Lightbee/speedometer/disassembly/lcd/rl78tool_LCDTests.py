import serial
import time, struct, binascii
import argparse

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
        of.write(dumpregion(rl78, offset, size))

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
        result += data
    return result
    



def initLCD(rl78: RL78):
        # setup LCD
    data = ocd_runcode(rl78,[0xF5,0x77,0x00, 0xD7])   #CLRB    PIOR  
    data = ocd_runcode(rl78,[0xEC,0x06,0x25,0x00])    #setupLCD0
    data = ocd_runcode(rl78,[0xEC,0xCF,0x22,0x00])    #R_CGC_Create    
    data = ocd_runcode(rl78,[0xEC,0x6F,0x23,0x00])    #R_LCD_Create
    data = ocd_runcode(rl78,[0xEC,0x65,0x24,0x00])    #setSCOC
    data = ocd_runcode(rl78,[0xEC,0x5D,0x24,0x00])    #R_LCD_Start
    # render Symbols
    data = ocd_runcode(rl78,[0xEC,0x24,0x41,0x00])    #render


def tryLED2(rl78: RL78, seg, bit):
    value = 1 << bit  
    rl78.ocd.write(0x400+ seg, [value&0xFF])    

def tryLED3(ser, seg, value):    
    rl78.ocd.write(0x400+ seg, [value&0xFF])

def renderNumber(num):
    """
    Common 7 Segment
          - A - 
        F       B
        | - G - |
        E       C
          - D -      DP
    """   
    """
    Segments:
    F0400 - F0427

    Address     Segment                 Bit/Symbol
                            07  06  05  04  03  02  01  00          
    F0400       SEG00:      NC  NC  NC  NC  NC  NC  NC  NC          <- Percent Segment 1 + A(FGE)
    F0401       SEG01:      NC  NC  NC  NC  NC  NC  NC  NC          <- Percent Segment A(ABCD)
    F0402       SEG02:      NC  NC  NC  NC  NC  NC  NC  NC          <- Percent Segment B(FGE) + Percent Symbol
    F0403       SEG03:      NC  NC  NC  NC  NC  NC  NC  NC          <- Percent Segment B(ABCD)
    F0404       SEG04:      NC  NC  NC  NC  NC  NC  NC  NC          <- Battery Level 4 5 + Flash Symbol
    F0405       SEG05:      NC  NC  NC  NC  NC  08  07  06          <- Battery Level 1 2 3
    F0406       SEG06:      NC  NC  NC  NC  NC  NC  NC  NC          <- Voltage segment C(ABCD)
    F0407       SEG07:      NC  NC  NC  NC  NC  NC  NC  NC          <- Voltage segment C(EGF)  V Symbol
    F0408       SEG08:      NC  NC  NC  NC  NC  NC  NC  NC          <- Voltage segment B(ABCD)
    F0409       SEG09:      NC  NC  NC  NC  NC  NC  NC  NC          <- Voltage segment B(EGF) + Dot

    F040A       SEG10:      NC  NC  NC  NC  NC  NC  NC  NC          <- Voltage segment A(ABCD)
    F040B       SEG11:      NC  NC  NC  NC  NC  NC  NC  NC          <- Voltage segment A(EGF)
    F040C       SEG12:      NC  NC  NC  NC  NC  11  10  09          <- Line Bottom, Total + Trip Symbol
    F040D       SEG13:      NC  NC  NC  NC  NC  NC  NC  NC          <- Distance Segment F(ABCD)
    F040E       SEG14:      NC  NC  NC  NC  NC  NC  NC  NC          <- Distance Segment F(EGF) + Dot
    F040F       SEG15:      NC  NC  NC  NC  NC  NC  NC  NC          <- Distance Segment E(ABCD)
    F0410       SEG16:      NC  NC  NC  NC  NC  14  13  12          <- Distance Segment E(EGF)
    F0411       SEG17:      NC  NC  NC  NC  18  17  16  15          <- Distance Segment D(ABCD)
    F0412       SEG18:      NC  NC  NC  NC  NC  21  20  19          <- Distance Segment D(EGF)
    F0413       SEG19:      NC  NC  NC  NC  NC  NC  NC  NC

    F0414       SEG20:      NC  NC  NC  NC  25  24  23  22          <- Distance Segment C(ABCD)
    F0415       SEG21:      NC  NC  NC  NC  NC  NC  NC  NC
    F0416       SEG22:      NC  NC  NC  NC  NC  28  27  26          <- Distance Segment C(EGF)
    F0417       SEG23:      NC  NC  NC  NC  32  31  30  29          <- Distance Segment B(ABCD)
    F0418       SEG24:      NC  NC  NC  NC  NC  35  34  33          <- Distance Segment B(EGF)
    F0419       SEG25:      NC  NC  NC  NC  39  38  37  36          <- Distance Segment A(ABCD)
    F041A       SEG26:      NC  NC  NC  NC  NC  42  41  40          <- Distance Segment A(EGF)
    F041B       SEG27:      NC  NC  NC  NC  NC  NC  NC  NC          <- Gear Segment B(ABCD)
    F041C       SEG28:      NC  NC  NC  NC  NC  NC  NC  NC
    F041D       SEG29:      NC  NC  NC  NC  NC  NC  NC  NC

    F041E       SEG30:      NC  NC  NC  NC  NC  NC  NC  NC
    F041F       SEG31:      NC  NC  NC  NC  NC  NC  NC  NC          <- Gear Segment B(EGF) + Dot Symbol
    F0420       SEG32:      NC  NC  NC  NC  NC  NC  NC  NC          <- Gear Segment A(ABCD)
    F0421       SEG33:      NC  NC  NC  NC  02  NC  NC  NC          <- Gear Segment A(EGF) + MPH Symbol
    F0422       SEG34:      NC  NC  NC  NC  NC  45  44  43          <- Surron Label (1) + Gear Symbol (4) + Max Symbol (2)
    F0423       SEG35:      NC  NC  NC  NC  49  48  47  46          <- Speed Segment B(ABCD)
    F0424       SEG36:      NC  NC  NC  NC  53  52  51  50          <- Speed Segment B(EGF) + KM/H Symbol
    F0425       SEG37:      NC  NC  NC  NC  57  56  55  54          <- Speed Segment A(ABCD)
    F0426       SEG38:      NC  NC  NC  NC  61  60  59  58          <- Speed Segment 1 + A(EGF)

    ```asciiart
    Common 7 Segment
        - A - 
        F       B
        | - G - |
        E       C
        - D -      DP
    ```

    ```asciiart
    SPEED SEGMENT (S):
    SYM 1     B       C
            -       -
        |   |   |   |   |
            -       -
        |   |   |   |   |
            -       -
    ```

    ```asciiart
    DISTANCE SEGMENT (D):
    SYM  A       B       C       D       E          F
        -       -       -       -       -          -  
    |   |   |   |   |   |   |   |   |   |      |   |
        -       -       -       -       -          -  
    |   |   |   |   |   |   |   |   |   |      |   |
        -       -       -       -       -     #    -  
    ```
    """
    
    ValidSymbols = ['0','1','2','3','4','5','6','7','8','9','A','B','C','D','E','F','H','I','L','O','P','S','U']
    SymbolMap = { 
             #        EGF   DCBA
            
            '0' : [ 0b101,0b1111],
            '1' : [ 0b000,0b0110],
            '2' : [ 0b110,0b1011],
            '3' : [ 0b010,0b1111],
            '4' : [ 0b011,0b0110],
            '5' : [ 0b011,0b1101],
            '6' : [ 0b111,0b1101],
            '7' : [ 0b000,0b0111],
            '8' : [ 0b111,0b1111],
            '9' : [ 0b011,0b1111],
            'A' : [ 0b111,0b0111],  #07 07
            'B' : [ 0b111,0b1111],  #07 0f
            'C' : [ 0b101,0b1001],  #05 09
            'D' : [ 0b101,0b1111],  #05 0f
            'E' : [ 0b111,0b1001],  #07 09
            'F' : [ 0b111,0b0001],  #07 01
            'H' : [ 0b111,0b0110],  #07 06
            'I' : [ 0b000,0b0110],  #00 06
            'L' : [ 0b101,0b1000],  #05 08
            'O' : [ 0b101,0b1111],  #05 0f
            'P' : [ 0b111,0b0011],  #07 03
            'S' : [ 0b011,0b1101],  #03 0d
            'U' : [ 0b101,0b1110],  #05 0e
            'r' : [ 0b110,0b0000],  #06 00
            '-' : [ 0b010,0b0000],  #02 00
    }
    if str(num) in SymbolMap:
        return SymbolMap[str(num)]   
    
    return [0,0]    

SPEEDSEGMENT = [[37,38],[35,36]]
PERCENTSEGMENT = [[1,0],[3,2]]
VOLTAGESEGMENT = [[10,11],[8,9],[6,7]]
DISTANCESEGMENT = [[25,26],[23,24],[20,22],[17,18],[15,16],[13,14]]
GEARSEGMENT = [[32,33],[27,31]]




def playLCD(rl78: RL78):
    ValidSymbols = ['0','1','2','3','4','5','6','7','8','9','A','B','C','D','E','F','H','I','L','O','P','S','U']
    while True:
        for j in range(10):            
            for idx,seg in enumerate(DISTANCESEGMENT):
                [A,B] = renderNumber((j+idx)%10)
                tryLED3(rl78, seg[0], B)
                tryLED3(rl78, seg[1], A)

            for idx,seg in enumerate(VOLTAGESEGMENT):
                [A,B] = renderNumber((j+idx)%10)
                tryLED3(rl78, seg[0], B)
                tryLED3(rl78, seg[1], A)

            for idx,seg in enumerate(SPEEDSEGMENT):
                [A,B] = renderNumber((j+idx)%10)
                tryLED3(rl78, seg[0], B)
                tryLED3(rl78, seg[1], A)

            for idx,seg in enumerate(PERCENTSEGMENT):
                [A,B] = renderNumber((j+idx)%10)
                tryLED3(rl78, seg[0], B)
                tryLED3(rl78, seg[1], A)

            for idx,seg in enumerate(GEARSEGMENT):
                [A,B] = renderNumber((j+idx)%10)
                tryLED3(rl78, seg[0], B)
                tryLED3(rl78, seg[1], A)                

            time.sleep(0.5)            


if __name__ == '__main__':

    with serial.Serial('/dev/cu.usbserial-0001', 115200, timeout=1) as ser:
        rl78 = RL78(ser)
        if not rl78.reset(RL78.MODE_OCD):
            print('failed to init ocd')
            exit()
        print("Check OCD Version: %s" % rl78.ocd.ping())
        if ocd_id is not None:
            unlockresponse = rl78.ocd.unlock(ocd_id)
            print("OCD Unlock: %s" % unlockresponse)

        initLCD(rl78)
        playLCD(rl78)
