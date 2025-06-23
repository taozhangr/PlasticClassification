#ifndef __CMD_PROCESS_H
#define __CMD_PROCESS_H

typedef struct 
{
    char 		*pcCmd;																					//指令
    int 		(*pcFunction)(void);			//指令对应的执行函数
    char		*pcMark;																				//指令说明
}Cmd_list_TypeDef;

//指令宏定义
#define MEASUREMENT		"sc" //测量
//指令处理函数
void cmd_process(void);
int measurement(void);
#endif // !__CMD_PROCESS_H

