
import serial
import time

lastflush = 0

def timeinms():
    return time.time() * 1000       
    
def checkflush():        
    global lastflush        
    if (timeinms()-lastflush > 1000):        
        lastflush = timeinms()
        return True
    return False



with open("/tmp/log.bin","wb") as log:
    with serial.Serial('/dev/cu.usbserial-0001', 460800, timeout=1) as ser:
        while True:
            while ser.in_waiting:        
                x = ser.read()          # read one byte
                log.write(x)                
                if checkflush():                     
                    log.flush()
            if checkflush():                 
                log.flush()

    