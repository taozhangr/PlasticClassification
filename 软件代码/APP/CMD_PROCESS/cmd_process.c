/*
 * @Author: 一颗牛皮糖 1933924181@qq.com
 * @Date: 2024-05-14 17:12:18
 * @LastEditors: 一颗牛皮糖 1933924181@qq.com
 * @LastEditTime: 2024-05-14 17:35:20
 * @FilePath: \MDK-ARMe:\Users\Administrator\Desktop\p_wxt\plastic\plastic\APP\CMD_PROCESS\cmd_process.c
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
 */
#include "cmd_process.h"
#include <stdio.h>
#include <string.h>
#include "usart.h"
#include "as726x.h"
static const Cmd_list_TypeDef cmd_list[] = 
{
    {MEASUREMENT, measurement, "celiang"},
};

void cmd_process()
{
    char *pcCmdTemp;
	if(USART_RX_STA&0x8000)
	{					   
		pcCmdTemp = RxBuffer;
		
//		printf("%s",pcCmdTemp);
		int i = 0;
		for(i = 0; i < sizeof(cmd_list)/sizeof(cmd_list[0]); i++)
		{
			if(strcmp(pcCmdTemp, cmd_list[i].pcCmd) == 0)
			{
				cmd_list[i].pcFunction();
			}
		}
		
		USART_RX_STA=0;
	}
}

int measurement(void)
{
	takeMeasurementsWithBulb();
	
	if (getVersion() == SENSORTYPE_AS7262)
	{
		//Visible readings
		printf("Reading: ");
		printf(" V[%.4f]",getCalibratedViolet());
		printf(" B[%.4f]",getCalibratedBlue());
		printf(" G[%.4f]",getCalibratedGreen());
		printf(" Y[%.4f]",getCalibratedYellow());
		printf(" O[%.4f]",getCalibratedOrange());
		printf(" R[%.4f]",getCalibratedRed());
	}
	else if (getVersion() == SENSORTYPE_AS7263)
	{
		//Near IR readings
		printf("Reading: ");
		printf(" R[%.4f]",getCalibratedR());
		printf(" S[%.4f]",getCalibratedS());
		printf(" T[%.4f]",getCalibratedT());
		printf(" U[%.4f]",getCalibratedU());		
		printf(" V[%.4f]",getCalibratedV());
		printf(" W[%.4f]",getCalibratedW());
	}

	printf(" tempF[%.4f]",getTemperatureF());
	printf("\r\n");
    return 0;
}
