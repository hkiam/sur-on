import argparse, hashlib, json

known_hashes = {
    '83e667a0d8874003e57baf742980cb42' : 'known firmware'
}
known_sizes = {
    2048 : 'eeprom',
    32768 : 'flash',
    1048576 : 'fulldump',
}

import six
CRC16_KERMIT_TAB = \
    [
        0x0000, 0x1189, 0x2312, 0x329b, 0x4624, 0x57ad, 0x6536, 0x74bf,
        0x8c48, 0x9dc1, 0xaf5a, 0xbed3, 0xca6c, 0xdbe5, 0xe97e, 0xf8f7,
        0x1081, 0x0108, 0x3393, 0x221a, 0x56a5, 0x472c, 0x75b7, 0x643e,
        0x9cc9, 0x8d40, 0xbfdb, 0xae52, 0xdaed, 0xcb64, 0xf9ff, 0xe876,
        0x2102, 0x308b, 0x0210, 0x1399, 0x6726, 0x76af, 0x4434, 0x55bd,
        0xad4a, 0xbcc3, 0x8e58, 0x9fd1, 0xeb6e, 0xfae7, 0xc87c, 0xd9f5,
        0x3183, 0x200a, 0x1291, 0x0318, 0x77a7, 0x662e, 0x54b5, 0x453c,
        0xbdcb, 0xac42, 0x9ed9, 0x8f50, 0xfbef, 0xea66, 0xd8fd, 0xc974,
        0x4204, 0x538d, 0x6116, 0x709f, 0x0420, 0x15a9, 0x2732, 0x36bb,
        0xce4c, 0xdfc5, 0xed5e, 0xfcd7, 0x8868, 0x99e1, 0xab7a, 0xbaf3,
        0x5285, 0x430c, 0x7197, 0x601e, 0x14a1, 0x0528, 0x37b3, 0x263a,
        0xdecd, 0xcf44, 0xfddf, 0xec56, 0x98e9, 0x8960, 0xbbfb, 0xaa72,
        0x6306, 0x728f, 0x4014, 0x519d, 0x2522, 0x34ab, 0x0630, 0x17b9,
        0xef4e, 0xfec7, 0xcc5c, 0xddd5, 0xa96a, 0xb8e3, 0x8a78, 0x9bf1,
        0x7387, 0x620e, 0x5095, 0x411c, 0x35a3, 0x242a, 0x16b1, 0x0738,
        0xffcf, 0xee46, 0xdcdd, 0xcd54, 0xb9eb, 0xa862, 0x9af9, 0x8b70,
        0x8408, 0x9581, 0xa71a, 0xb693, 0xc22c, 0xd3a5, 0xe13e, 0xf0b7,
        0x0840, 0x19c9, 0x2b52, 0x3adb, 0x4e64, 0x5fed, 0x6d76, 0x7cff,
        0x9489, 0x8500, 0xb79b, 0xa612, 0xd2ad, 0xc324, 0xf1bf, 0xe036,
        0x18c1, 0x0948, 0x3bd3, 0x2a5a, 0x5ee5, 0x4f6c, 0x7df7, 0x6c7e,
        0xa50a, 0xb483, 0x8618, 0x9791, 0xe32e, 0xf2a7, 0xc03c, 0xd1b5,
        0x2942, 0x38cb, 0x0a50, 0x1bd9, 0x6f66, 0x7eef, 0x4c74, 0x5dfd,
        0xb58b, 0xa402, 0x9699, 0x8710, 0xf3af, 0xe226, 0xd0bd, 0xc134,
        0x39c3, 0x284a, 0x1ad1, 0x0b58, 0x7fe7, 0x6e6e, 0x5cf5, 0x4d7c,
        0xc60c, 0xd785, 0xe51e, 0xf497, 0x8028, 0x91a1, 0xa33a, 0xb2b3,
        0x4a44, 0x5bcd, 0x6956, 0x78df, 0x0c60, 0x1de9, 0x2f72, 0x3efb,
        0xd68d, 0xc704, 0xf59f, 0xe416, 0x90a9, 0x8120, 0xb3bb, 0xa232,
        0x5ac5, 0x4b4c, 0x79d7, 0x685e, 0x1ce1, 0x0d68, 0x3ff3, 0x2e7a,
        0xe70e, 0xf687, 0xc41c, 0xd595, 0xa12a, 0xb0a3, 0x8238, 0x93b1,
        0x6b46, 0x7acf, 0x4854, 0x59dd, 0x2d62, 0x3ceb, 0x0e70, 0x1ff9,
        0xf78f, 0xe606, 0xd49d, 0xc514, 0xb1ab, 0xa022, 0x92b9, 0x8330,
        0x7bc7, 0x6a4e, 0x58d5, 0x495c, 0x3de3, 0x2c6a, 0x1ef1, 0x0f78
    ]


def crc16_kermit(data, crc=0):
    """Calculate/Update the Kermit CRC16 checksum for some data"""
    tab = CRC16_KERMIT_TAB  # minor optimization (now in locals)
    for byte in six.iterbytes(data):
        tbl_idx = (crc ^ byte) & 0xff
        crc = (tab[tbl_idx] ^ (crc >> 8)) & 0xffff
    return crc & 0xffff


def readUInt16(data, offset=0):
    return data[offset] + (data[offset+1]<<8) 

def writeUInt16(data, offset=0, value=0):
    data[offset] = value & 0xFF
    data[offset+1] = (value >> 8) & 0xFF

def writeUInt24(data, offset=0, value=0):
    data[offset] = value & 0xFF
    data[offset+1] = (value >> 8) & 0xFF
    data[offset+2] = (value >> 16) & 0xFF

def readUInt24(data, offset=0):
    return data[offset] + (data[offset+1]<<8) + (data[offset+2]<<16) 

def parseDataFlashRecord(data, offset=0):
    """
    00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F 10 11 12 13 14 15 16 17
    CS CS AA AA AA BB BB BB CC ?? DD DD EE EE FF FF GG HH II II JJ JJ ?? ??

    AA = word_FFB7C word_FFB7A = Savecounter   stored as little endian
    BB = word_FFB6E  word_FFB6C Total Distance, 24 Bit?
    CC = byte_FFB22     Display (KM/h/ Trip)
    DD = word_FFB72     Trip Distance
    EE = word_FFB74     Total Distance, 16 Bit?
    FF = word_FFB06 + word_FFB04        Default: 0x1FE  Min:0x14 Max:0xfa0  ?
    GG = byte_FFB85 + byte_FFB84        FFB84=KM(0)/Miles(1)
    HH = byte_FFB87     Trip Max Speed
    II = word_FFB0A     Gear Ratio / 100
    JJ = word_FFB0C
    """
    crc = readUInt16(data, offset)
    calculated_crc = crc16_kermit(data[offset+2:offset+0x18])
    if crc != calculated_crc:
        #print("offset:%06X crc error: %04X != %04X" % (offset,crc, calculated_crc))
        return None
    record_id = readUInt24(data, offset+2)
    total_distance = readUInt24(data, offset+5)
    display_mode = data[offset+0x08]
    trip_distance = readUInt16(data, offset+0x0A)
    trip_maxspeed = data[offset+0x11]
    total_distance_16b = readUInt16(data, offset+0x0C)
    gear_ratio = readUInt16(data, offset+0x12)
    
    return {"offset": offset,"crc": crc, "calculated_crc": calculated_crc, "record_id":record_id,"total_distance":total_distance/10, "display_mode":display_mode, "trip_distance":trip_distance,"total_distance_16b":total_distance_16b/10,"trip_maxspeed":trip_maxspeed, "gear_ratio":gear_ratio/100}
    
def patchTotalDistance(data, offset, newdist):
    writeUInt24(data, offset+5, newdist*10)
    writeUInt16(data, offset+0x0C, newdist)
    calculated_crc = crc16_kermit(data[offset+2:offset+0x18])
    writeUInt16(data, offset, calculated_crc)

def isEEPROM(data):
    return len(data) == 2048

def isFULLDump(data):
    return len(data) == 0x100000

def isFirmware(data):
    return len(data) == 0x8000

if __name__ == '__main__':

    def auto_int(x):
            return int(x, 0)
    
    parser = argparse.ArgumentParser()
    

    commands = parser.add_subparsers(dest='command')

    parser_a = commands.add_parser('info', help='binary info')    
    parser_a.add_argument('-i', '--input', dest='filename', help='filename of the input file', required=True)

    parser_b = commands.add_parser('eeprominfo', help='eeprom infos')    
    parser_b.add_argument('-i', '--input', dest='filename', help='filename of the input file', required=True)
    parser_b.add_argument('-v', '--verbose', dest='verbose', help='print all records', required=False, default=False, type=bool)

    parser_c = commands.add_parser('extracteeprom', help='extract eeprom from fulldump')    
    parser_c.add_argument('-i', '--input', dest='filename', help='filename of the input file', required=True)
    parser_c.add_argument('-o', '--output', dest='ouputfilename', help='filename of the output file', required=True)

    parser_d = commands.add_parser('extractfirm', help='extract firmware from fulldump')    
    parser_d.add_argument('-i', '--input', dest='filename', help='filename of the input file', required=True)
    parser_d.add_argument('-o', '--output', dest='ouputfilename', help='filename of the output file', required=True)

    parser_e = commands.add_parser('patchfirm', help='add/remove feature to firmware')    
    parser_e.add_argument('-i', '--input', dest='filename', help='filename of the input file', required=True)
    parser_e.add_argument('-o', '--output', dest='ouputfilename', help='filename of the output file', required=True)
    parser_e.add_argument('-p', '--patch', dest='patchname', help='name of the patch', required=True)
    parser_e.add_argument('-r', '--reverse', dest='reverse', help='remove patch', required=False, default=False, type=bool)


    kwargs = parser.parse_args()
    if kwargs.command == 'info':
        with open(kwargs.filename, 'rb') as f:
            data = f.read()
            print("name: %s" % kwargs.filename)
            print("size: %d" % len(data))
            print("type: %s" % known_sizes.get(len(data), 'unknown'))

            md5 = hashlib.md5(data).hexdigest()
            if md5 in known_hashes:
                print("md5: %s => %s" % (md5, known_hashes[md5])) 
            else:
                print("md5: %s => unknown" % md5)            
        exit()    
    elif kwargs.command == 'eeprominfo':
        validcount = 0
        lastRecord = None
        with open(kwargs.filename, 'rb') as f:
            data = f.read()
            if not isEEPROM(data):
                print("invalid size, not an eeprom")
                exit()
            for offset in range(0,0x400,0x18):
                result = parseDataFlashRecord(data, offset)
                if result is not None:
                    validcount += 1
                    if lastRecord is None or lastRecord["record_id"] < result["record_id"]:
                        lastRecord = result
                    if kwargs.verbose:
                        print(result)
            for offset in range(0x400,0x800,0x18):
                result = parseDataFlashRecord(data, offset)
                if result is not None:
                    validcount += 1
                    if lastRecord is None or lastRecord["record_id"] < result["record_id"]:
                        lastRecord = result
                    if kwargs.verbose:
                        print(result)
        
        if lastRecord is None:
            print("no valid records, maybe not an eeprom?")
        else:
            print("last record: %s" % lastRecord)
        exit()
    elif kwargs.command == 'extracteeprom':        
        with open(kwargs.filename, 'rb') as f:
            data = f.read()            
            if not isFULLDump(data):
                print("invalid size, not an fulldump")
                exit()
            with open(kwargs.ouputfilename, 'wb') as of:
                of.write(data[0x0F1000:0x0F1000+0x800])
        exit()
    elif kwargs.command == 'extractfirm':        
        with open(kwargs.filename, 'rb') as f:
            data = f.read()            
            if not isFULLDump(data):
                print("invalid size, not an fulldump")
                exit()
            with open(kwargs.ouputfilename, 'wb') as of:
                of.write(data[0x0:0x8000])
        exit()  
    elif kwargs.command == 'patchfirm':     
        patchdata = None
        with open('patches.json', 'r') as f:
            patchdata = json.load(f)
   
        with open(kwargs.filename, 'rb') as f:
            data = f.read()            
            if not isFirmware(data):
                print("invalid size, not an firmware")
                exit()

            for patch in patchdata:
                if patch['name'].lower() == kwargs.patchname.lower():
                    for hook in patch['data']:
                        offset = int(hook['offset'],0)
                        orgdata = bytes.fromhex(hook['orgdata'])
                        newdata = bytes.fromhex(hook['newdata'])

                        if data[offset:offset+len(orgdata)] != orgdata:
                            print("hook not found")
                            exit()
                        data = data[:offset] + newdata + data[offset+len(orgdata):]
                                                
                    with open(kwargs.ouputfilename, 'wb') as of:
                        of.write(data)
        exit()                              
    