#include <stdio.h>
#include <string.h>
#include "as726x.h"
#include "i2c.h"
#include "usart.h"


static uint8_t _sensorVersion = 0;

static int getChannel(uint8_t channelRegister);
static float getCalibratedValue(uint8_t calAddress);
static float convertBytesToFloat(uint32_t myLong);
static void clearDataAvailable(void);
static uint8_t virtualReadRegister(uint8_t virtualAddr);
static void virtualWriteRegister(uint8_t virtualAddr, uint8_t dataToWrite);
static uint8_t readRegister(uint8_t addr);
static void writeRegister(uint8_t addr, uint8_t val_adr);

static void (*pdelay)(uint32_t ms_Num) = NULL;

uint8_t AS726_begin(uint8_t v_gain, uint8_t v_measurementMode){
	
	uint8_t gain = v_gain;
	uint8_t measurementMode = v_measurementMode;
	
	_sensorVersion = virtualReadRegister(AS726x_HW_VERSION);
    //HW version for AS7262 and AS7263
	if (_sensorVersion != 0x3E && _sensorVersion != 0x3F) 
	{
		return (0x00);
	}
	else
	{
		printf("AS726x_HW_VERSION %x",_sensorVersion);
	}
    //Set to 12.5mA (minimum)
	setBulbCurrent(0x00);
	//Turn off to avoid heating the sensor
	disableBulb();

	setIndicatorCurrent(0x03);//Set to 8mA (maximum)
	disableIndicator(); //Turn off lights to save power

	setIntegrationTime(50); //50 * 2.8ms = 140ms. 0 to 255 is valid.
//							//If you use Mode 2 or 3 (all the colors) then integration time is double. 140*2 = 280ms between readings.

	setGain(gain); //Set gain to 64x

	setMeasurementMode(measurementMode); //One-shot reading of VBGYOR

	if (_sensorVersion == 0)
	{
		return (0x00);
	}
	return (0xFF);
}

uint8_t getVersion()
{
	return _sensorVersion;
}

///*
//Sets the measurement mode
//Mode 0: Continuous reading of VBGY (7262) / STUV (7263)
//Mode 1: Continuous reading of GYOR (7262) / RTUX (7263)
//Mode 2: Continuous reading of all channels (power-on default)
//Mode 3: One-shot reading of all channels
//*/
void setMeasurementMode(uint8_t mode)
{
	if (mode > 0x03) mode = 0x03;

	//Read, mask/set, write
	uint8_t value = virtualReadRegister(AS726x_CONTROL_SETUP); //Read
	value &= 0xF3; //Clear BANK bits
	value |= (mode << 2); //Set BANK bits with user's choice
	virtualWriteRegister(AS726x_CONTROL_SETUP, value); //Write
}

////Sets the gain value
////Gain 0: 1x (power-on default)
////Gain 1: 3.7x
////Gain 2: 16x
////Gain 3: 64x
void setGain(uint8_t gain)
{
	if (gain > 0x03) gain = 0x03;

	//Read, mask/set, write
	uint8_t value = virtualReadRegister(AS726x_CONTROL_SETUP); //Read
	value &= 0xCF; //Clear GAIN bits
	value |= (gain << 4); //Set GAIN bits with user's choice
	virtualWriteRegister(AS726x_CONTROL_SETUP, value); //Write
}

////Sets the integration value
////Give this function a uint8_t from 0 to 255.
////Time will be 2.8ms * [integration value]
void setIntegrationTime(uint8_t integrationValue)
{
	virtualWriteRegister(AS726x_INT_T, integrationValue); //Write
}

void enableInterrupt()
{
	//Read, mask/set, write
	uint8_t value = virtualReadRegister(AS726x_CONTROL_SETUP); //Read
	value |= 0x40; //Set INT bit
	virtualWriteRegister(AS726x_CONTROL_SETUP, value); //Write
}

void disableInterrupt()
{
	//Read, mask/set, write
	uint8_t value = virtualReadRegister(AS726x_CONTROL_SETUP); //Read
	value &= 0xBF; //Clear INT bit
	virtualWriteRegister(AS726x_CONTROL_SETUP, value); //Write
}

//Tells IC to take measurements and polls for data ready flag
void takeMeasurements()
{
	clearDataAvailable(); //Clear DATA_RDY flag when using Mode 3

						  //Goto mode 3 for one shot measurement of all channels
	setMeasurementMode(3);

	//Wait for data to be ready
	while (dataAvailable() == 0x00) pdelay(POLLING_DELAY);

	//Readings can now be accessed via getViolet(), getBlue(), etc
}

void takeMeasurementsWithBulb()
{
	//enableIndicator(); //Tell the world we are taking a reading. 
	//The indicator LED is red and may corrupt the readings

	enableBulb(); //Turn on bulb to take measurement

	takeMeasurements();

	disableBulb(); //Turn off bulb to avoid heating sensor
				   //disableIndicator();
}

//Get the various color readings
int getViolet() { return(getChannel(AS7262_V)); }
int getBlue() { return(getChannel(AS7262_B)); }
int getGreen() { return(getChannel(AS7262_G)); }
int getYellow() { return(getChannel(AS7262_Y)); }
int getOrange() { return(getChannel(AS7262_O)); }
int getRed() { return(getChannel(AS7262_R)); }

//Get the various NIR readings
int getR() { return(getChannel(AS7263_R)); }
int getS() { return(getChannel(AS7263_S)); }
int getT() { return(getChannel(AS7263_T)); }
int getU() { return(getChannel(AS7263_U)); }
int getV() { return(getChannel(AS7263_V)); }
int getW() { return(getChannel(AS7263_W)); }

//A the 16-bit value stored in a given channel registerReturns 
int getChannel(uint8_t channelRegister)
{
	int colorData = virtualReadRegister(channelRegister) << 8; //High uint8_t
	colorData |= virtualReadRegister(channelRegister + 1); //Low uint8_t
	return(colorData);
}

//Returns the various calibration data
float getCalibratedViolet() { return(getCalibratedValue(AS7262_V_CAL)); }
float getCalibratedBlue() { return(getCalibratedValue(AS7262_B_CAL)); }
float getCalibratedGreen() { return(getCalibratedValue(AS7262_G_CAL)); }
float getCalibratedYellow() { return(getCalibratedValue(AS7262_Y_CAL)); }
float getCalibratedOrange() { return(getCalibratedValue(AS7262_O_CAL)); }
float getCalibratedRed() { return(getCalibratedValue(AS7262_R_CAL)); }

float getCalibratedR() { return(getCalibratedValue(AS7263_R_CAL)); }
float getCalibratedS() { return(getCalibratedValue(AS7263_S_CAL)); }
float getCalibratedT() { return(getCalibratedValue(AS7263_T_CAL)); }
float getCalibratedU() { return(getCalibratedValue(AS7263_U_CAL)); }
float getCalibratedV() { return(getCalibratedValue(AS7263_V_CAL)); }
float getCalibratedW() { return(getCalibratedValue(AS7263_W_CAL)); }

//Given an address, read four uint8_ts and return the floating point calibrated value
float getCalibratedValue(uint8_t calAddress)
{
	uint8_t b0, b1, b2, b3;
	b0 = virtualReadRegister(calAddress + 0);
	b1 = virtualReadRegister(calAddress + 1);
	b2 = virtualReadRegister(calAddress + 2);
	b3 = virtualReadRegister(calAddress + 3);

	//Channel calibrated values are stored big-endian
	uint32_t calBytes = 0;
	calBytes |= ((uint32_t)b0 << (8 * 3));
	calBytes |= ((uint32_t)b1 << (8 * 2));
	calBytes |= ((uint32_t)b2 << (8 * 1));
	calBytes |= ((uint32_t)b3 << (8 * 0));

	return (convertBytesToFloat(calBytes));
}

//Given 4 uint8_ts returns the floating point value
float convertBytesToFloat(uint32_t myLong)
{
	float myFloat;
	memcpy(&myFloat, &myLong, 4); //Copy uint8_ts into a float
	return (myFloat);
}

//Checks to see if DRDY flag is set in the control setup register
uint8_t dataAvailable()
{
	uint8_t value = virtualReadRegister(AS726x_CONTROL_SETUP);
	return (value & (1 << 1)); //Bit 1 is DATA_RDY
}

//Clears the DRDY flag
//Normally this should clear when data registers are read
void clearDataAvailable()
{
	uint8_t value = virtualReadRegister(AS726x_CONTROL_SETUP);
	value &= ~(1 << 1); //Set the DATA_RDY bit
	virtualWriteRegister(AS726x_CONTROL_SETUP, value);
}

//Enable the onboard indicator LED
void enableIndicator()
{
	//Read, mask/set, write
	uint8_t value = virtualReadRegister(AS726x_LED_CONTROL);
	value |= (1 << 0); //Set the bit
	virtualWriteRegister(AS726x_LED_CONTROL, value);
}

//Disable the onboard indicator LED
void disableIndicator()
{
	//Read, mask/set, write
	uint8_t value = virtualReadRegister(AS726x_LED_CONTROL);
	value &= ~(1 << 0); //Clear the bit
	virtualWriteRegister(AS726x_LED_CONTROL, value);
}

////Set the current limit of onboard LED. Default is max 8mA = 0b11.
void setIndicatorCurrent(uint8_t current)
{
	if (current > 0x03) current = 0x03;
	//Read, mask/set, write
	uint8_t value = virtualReadRegister(AS726x_LED_CONTROL); //Read
	value &= 0xF9; //Clear ICL_IND bits
	value |= (current << 1); //Set ICL_IND bits with user's choice
	virtualWriteRegister(AS726x_LED_CONTROL, value); //Write
}

//Enable the onboard 5700k or external incandescent bulb
void enableBulb()
{
	//Read, mask/set, write
	uint8_t value = virtualReadRegister(AS726x_LED_CONTROL);
	value |= (1 << 3); //Set the bit
	virtualWriteRegister(AS726x_LED_CONTROL, value);
}

//Disable the onboard 5700k or external incandescent bulb
void disableBulb()
{
	//Read, mask/set, write
	uint8_t value = virtualReadRegister(AS726x_LED_CONTROL);
	value &= ~(1 << 3); //Clear the bit
	virtualWriteRegister(AS726x_LED_CONTROL, value);
}

////Set the current limit of bulb/LED.
////Current 0: 12.5mA
////Current 1: 25mA
////Current 2: 50mA
////Current 3: 100mA
void setBulbCurrent(uint8_t current)
{
	if (current > 0x03) current = 0x03; //Limit to two bits

										//Read, mask/set, write
	uint8_t value = virtualReadRegister(AS726x_LED_CONTROL); //Read
	value &= 0xCF; //Clear ICL_DRV bits
	value |= (current << 4); //Set ICL_DRV bits with user's choice
	virtualWriteRegister(AS726x_LED_CONTROL, value); //Write
}

//Returns the temperature in C
//Pretty inaccurate: +/-8.5C
uint8_t getTemperature()
{
	return (virtualReadRegister(AS726x_DEVICE_TEMP));
}

//Convert to F if needed
float getTemperatureF()
{
	float temperatureF = getTemperature();
	temperatureF = temperatureF * 1.8 + 32.0;
	return (temperatureF);
}

//Does a soft reset
//Give sensor at least 1000ms to reset
void softReset()
{
	//Read, mask/set, write
	uint8_t value = virtualReadRegister(AS726x_CONTROL_SETUP); //Read
	value |= (1 << 7); //Set RST bit
	virtualWriteRegister(AS726x_CONTROL_SETUP, value); //Write
}

void registerDelay(void (* doPrint)(uint32_t ms_Num)){
	pdelay = doPrint;
}

//Read a virtual register from the AS726x
uint8_t virtualReadRegister(uint8_t virtualAddr)
{
	uint8_t status;

	//Do a prelim check of the read register
	status = readRegister(AS72XX_SLAVE_STATUS_REG);
	if ((status & AS72XX_SLAVE_RX_VALID) != 0) //There is data to be read
	{
		//Serial.println("Premptive read");
		uint8_t incoming = readRegister(AS72XX_SLAVE_READ_REG); //Read the uint8_t but do nothing with it
	}

	//Wait for WRITE flag to clear
	while (1)
	{
		status = readRegister(AS72XX_SLAVE_STATUS_REG);
		if ((status & AS72XX_SLAVE_TX_VALID) == 0) break; // If TX bit is clear, it is ok to write
		pdelay(POLLING_DELAY);
	}

	// Send the virtual register address (bit 7 should be 0 to indicate we are reading a register).
	writeRegister(AS72XX_SLAVE_WRITE_REG, virtualAddr);

	//Wait for READ flag to be set
	while (1)
	{
		status = readRegister(AS72XX_SLAVE_STATUS_REG);
		if ((status & AS72XX_SLAVE_RX_VALID) != 0) break; // Read data is ready.
		pdelay(POLLING_DELAY);
	}

	uint8_t incoming = readRegister(AS72XX_SLAVE_READ_REG);
	return (incoming);
}

//Write to a virtual register in the AS726x
void virtualWriteRegister(uint8_t virtualAddr, uint8_t dataToWrite)
{
	uint8_t status;

	//Wait for WRITE register to be empty
	while (1)
	{
		status = readRegister(AS72XX_SLAVE_STATUS_REG);
		if ((status & AS72XX_SLAVE_TX_VALID) == 0) break; // No inbound TX pending at slave. Okay to write now.
		pdelay(POLLING_DELAY);
	}

	// Send the virtual register address (setting bit 7 to indicate we are writing to a register).
	writeRegister(AS72XX_SLAVE_WRITE_REG, (virtualAddr | 0x80));

	//Wait for WRITE register to be empty
	while (1)
	{
		status = readRegister(AS72XX_SLAVE_STATUS_REG);
		if ((status & AS72XX_SLAVE_TX_VALID) == 0) break; // No inbound TX pending at slave. Okay to write now.
		pdelay(POLLING_DELAY);
	}

	// Send the data to complete the operation.
	writeRegister(AS72XX_SLAVE_WRITE_REG, dataToWrite);
}

//Reads from a give location from the AS726x
uint8_t readRegister(uint8_t addr)
{
	uint8_t data = 0;
	
    if(HAL_I2C_Mem_Read(&hi2c1, AS726X_ADDR, addr,I2C_MEMADD_SIZE_8BIT, &data, 1, 100)==HAL_OK){
		return data;
	}

	else {
		HAL_UART_Transmit(&huart1, (uint8_t *)"readreg error", 7, 1000);
		return (0xFF); //Error
	}
}

//Write a value to a spot in the AS726x
void writeRegister(uint8_t addr, uint8_t val_adr)
{
	if(HAL_I2C_Mem_Write(&hi2c1, AS726X_ADDR, addr, I2C_MEMADD_SIZE_8BIT, &val_adr, 1, 1000)==HAL_OK){
		return;
	}
	else {
		HAL_UART_Transmit(&huart1, (uint8_t *)"writereg error", 7, 1000);
		return; //Error
	}
}

