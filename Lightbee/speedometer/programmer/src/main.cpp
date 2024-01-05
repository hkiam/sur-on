#include <Arduino.h>

#include "driver/uart.h"

#define reset_pin       GPIO_NUM_25
#define rl78_rx_pin     GPIO_NUM_32
#define rl78_tx_pin     GPIO_NUM_33

void setup(void) 
{
  Serial.begin(115200);   // USB uart
    
  // Set up pins
  pinMode(reset_pin, OUTPUT);

  // Set initial pin states
  digitalWrite(reset_pin, HIGH);  
}

static void halt(){
  while(true) {sleep(1);}
} 

void loop(){
    uint8_t rxbuffer[100];    
    while(true){    

        if(!Serial.available()) {
          continue;
        }

        uint8_t mode = Serial.read();
        
        if(mode!=0x3a && mode!=0x00 && mode!=0xc5){
          Serial.write(0xEE);
          Serial.write(mode);
          continue;
          //halt();
        }

        Serial.write(0);
        Serial.write(mode);

        int rxlen = 0;        
        Serial1.end();

        pinMode(rl78_rx_pin,INPUT);
        pinMode(rl78_tx_pin,OUTPUT);        
        digitalWrite(rl78_tx_pin, LOW);        
        digitalWrite(reset_pin, LOW);      
        delayMicroseconds(1800);    

        // Reset High, Tool0 Low to enter bootloader mode
        digitalWrite(reset_pin, HIGH);  
        delay(1);                       
      
        // Reset High, Tool0 High
        Serial1.begin(115200,SERIAL_8N1,rl78_rx_pin, rl78_tx_pin);  // TOOL0 uart   
        delay(1);                        
        while(Serial1.available()){
            Serial1.read();
        }

        // enter mode        
        Serial1.write(mode);          // Debugger init cmd
        delay(1);
                
        // Start UART Redirector;        
        while(true)
        {                 
          if(Serial.available()){
            Serial1.write(Serial.read());            
          }

          if(Serial1.available()){
            Serial.write(Serial1.read());            
          }          
        }        
    }
}
