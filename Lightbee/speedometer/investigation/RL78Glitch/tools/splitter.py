
def writefile(name, data):
    with open(name, "wb") as f:
        f.write(data)   

skip = 0x922f
with open("/tmp/log.bin","rb") as fi:
    fi.seek(skip,1)
    data = fi.read(0x100000)
    writefile("/tmp/dump1.bin",data)

    data = fi.read(0x100000)
    writefile("/tmp/dump2.bin",data)

    data = fi.read(0x100000)
    writefile("/tmp/dump3.bin",data)


    data = fi.read(0x100000)
    writefile("/tmp/dump4.bin",data)


#00 00 00 00 00 01 87 27 75 54