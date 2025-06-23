#ifndef __AS726X_H
#define __AS726X_H

#include <stdint.h>

//7-bit unshifted default I2C Address
#define AS726X_ADDR (0x49<<1) 
#define SENSORTYPE_AS7262 0x3E
#define SENSORTYPE_AS7263 0x3F

//Register addresses
#define AS726x_DEVICE_TYPE 0x00
#define AS726x_HW_VERSION 0x01
#define AS726x_CONTROL_SETUP 0x04
#define AS726x_INT_T 0x05
#define AS726x_DEVICE_TEMP 0x06
#define AS726x_LED_CONTROL 0x07

#define AS72XX_SLAVE_STATUS_REG 0x00
#define AS72XX_SLAVE_WRITE_REG 0x01
#define AS72XX_SLAVE_READ_REG 0x02

/*The same register locations are shared between the AS7262 and AS7263, 
they're just called something different AS7262 Registers */
#define AS7262_V 0x08
#define AS7262_B 0x0A
#define AS7262_G 0x0C
#define AS7262_Y 0x0E
#define AS7262_O 0x10
#define AS7262_R 0x12
#define AS7262_V_CAL 0x14
#define AS7262_B_CAL 0x18
#define AS7262_G_CAL 0x1C
#define AS7262_Y_CAL 0x20
#define AS7262_O_CAL 0x24
#define AS7262_R_CAL 0x28

//AS7263 Registers
#define AS7263_R 0x08
#define AS7263_S 0x0A
#define AS7263_T 0x0C
#define AS7263_U 0x0E
#define AS7263_V 0x10
#define AS7263_W 0x12
#define AS7263_R_CAL 0x14
#define AS7263_S_CAL 0x18
#define AS7263_T_CAL 0x1C
#define AS7263_U_CAL 0x20
#define AS7263_V_CAL 0x24
#define AS7263_W_CAL 0x28

#define AS72XX_SLAVE_TX_VALID 0x02
#define AS72XX_SLAVE_RX_VALID 0x01

#define SENSORTYPE_AS7262 0x3E
#define SENSORTYPE_AS7263 0x3F

//Amount of ms to wait between checking for virtual register changes
#define POLLING_DELAY 5 //Amount of ms to wait between checking for virtual register changes

extern uint8_t _sensorVersion;

uint8_t AS726_begin(uint8_t v_gain, uint8_t v_measurementMode);
void registerDelay(void (* doPrint)(uint32_t ms_Num));
void takeMeasurements(void);
uint8_t getVersion(void);
void takeMeasurementsWithBulb(void);
uint8_t getTemperature(void);
float getTemperatureF(void);
void setMeasurementMode(uint8_t mode);
uint8_t dataAvailable(void);
void enableIndicator(void);
void disableIndicator(void);
void setIndicatorCurrent(uint8_t current);
void enableBulb(void);
void disableBulb(void);
void setBulbCurrent(uint8_t current);
void softReset(void);
void setGain(uint8_t gain);
void setIntegrationTime(uint8_t integrationValue);
void enableInterrupt(void);
void disableInterrupt(void);
//Get the various color readings
int getViolet(void);
int getBlue(void);
int getGreen(void);
int getYellow(void);
int getOrange(void);
int getRed(void);

//Get the various NIR readings
int getR(void);
int getS(void);
int getT(void);
int getU(void);
int getV(void);
int getW(void);

//Returns the various calibration data
float getCalibratedViolet(void);
float getCalibratedBlue(void);
float getCalibratedGreen(void);
float getCalibratedYellow(void);
float getCalibratedOrange(void);
float getCalibratedRed(void);

float getCalibratedR(void);
float getCalibratedS(void);
float getCalibratedT(void);
float getCalibratedU(void);
float getCalibratedV(void);
float getCalibratedW(void);

#endif

