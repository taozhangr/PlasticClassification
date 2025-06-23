#ifndef __OLED_H_
#define __OLED_H_	

#include "stdint.h"
#include "i2c.h"
//#include "sys.h"


#define OLED_CMD  	0		//写命令
#define OLED_DATA 	1		//写数据
//OLED控制用函数

typedef uint32_t  u32;
typedef uint16_t u16;
typedef uint8_t  u8;

void OLED_WR_Byte(u8 data,u8 cmd);	    
void OLED_Display_On(void);
void OLED_Display_Off(void);
void OLED_Refresh_Gram(void);		   
							   		    
void OLED_Init(void);
void OLED_Clear(void);
void OLED_DrawPoint(u8 x,u8 y,u8 t);
void OLED_Fill(u8 x1,u8 y1,u8 x2,u8 y2,u8 dot);
void OLED_ShowChar(u8 x,u8 y,u8 chr,u8 size,u8 mode);
void OLED_ShowNum(u8 x,u8 y,u32 num,u8 len,u8 size);
void OLED_ShowString(u8 x,u8 y,const u8 *p,u8 size);
void OLED_ShowFNum(u8 x,u8 y,float Fnum,u8 size1);
#endif
