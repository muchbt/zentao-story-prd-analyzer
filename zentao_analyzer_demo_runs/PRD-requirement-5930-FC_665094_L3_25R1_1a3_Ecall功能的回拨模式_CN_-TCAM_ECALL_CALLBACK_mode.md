# PRD: FC_665094_L3 25R1(1a3)_Ecall功能的回拨模式(CN)-TCAM ECALL  CALLBACK mode

## 来源信息

- 条目类型: requirement
- 条目 ID: 5930
- 状态: active
- 优先级: 1
- 生成时间: 2026-05-22T15:18:23.733346+08:00


## 原始需求摘要

After the follow cases ,TCAM should enter new  call back mode ,the time of the call back mode should be retimed 25mins.
发生以下情况后，TCAM应该进入一个新的回叫模式，回叫模式时间为25分钟
1. If user cancel a voice call, after callstatus=callend,TCAM enter into call back mode
如果用户取消语音呼叫，即callstatus=callend，TCAM进入回叫模式
2. If a voice call is hung up by call center(not terminate by TSP),TCAM enter into callback mode
如果语音呼叫被电话中心挂断（不是被TSP终止），TCAM进入回叫模式
1) when TCAM is in call back mode TCAM shoud send the XCallStatusSrv.XCallStatusEvt.XCallStatusStruct.CallBackMode=0x01( CallBack) and TCAM send the remainTime of CallBackStsSrv.CallBackStsEvt.CallBackSts  periodic with 1s to DHU by Ethernet bus;
当TCAM处于回叫模式，TCAM发送以太网信号到DHU：CallBackMode=0x01( CallBack)，且以1s的周期发送CallBackSts
2) when the ecall service is working TCAM shoud send the XCallStatusSrv.XCallStatusEvt.XCallStatusStruct.CallBackMode=0x0( Normal)  to DHU by Ethernet bus;
当Ecall服务在工作中时，TCAM发送以太网信号CallBackMode=0x0( Normal)到DHU

3..If  triggered a voice call, call center not answer the call,will directly enter into call back mode.
触发语音呼叫后，电话中心没有响应呼叫，直接进入回叫模式
For incoming call:
对于来电回拨
If an incoming call is received set XCallStatusSrv.XCallStatusEvt.XCallStatusStruct.CallStatus to incomingCall (1) ,after CallStatus changed to incomingCall (1) when a EA or AA service is active. Then an automatic answer shall be made by the TCAM and CallStatus shall be set to callConnecting (4) or callConnected (5).
如果TCAM收到来电回拨，设置以太网信号CallStatus=1:(incomingCall)，在EA/AA服务被激活时，CallStatus变为incomingCall(1)之后，TCAM会自动应答并将CallStatus设置为callConnecting (4)||callConnected (5)
Note:
1) when service is call back mode ,during the call back mode ,TCAM is in incoming call ,TCAM receive a new AA call or EA call ,TCAM should send a MSD to call center ,do not end the incoming call ,when the incoming call completed,TCAM should renew the call back mode timer;
在回叫模式期间，且TCAM处于来电回拨中，收到了新的AA或EA触发，需要发送MSD信息到坐席中心，且不能结束当前的来电回拨，当来电回拨完成后，TCAM重启回叫模式的计时器
2) when TCAM is in call back mode if TCAM receive  I call or BCall request ,TCAM should ignore the Icall or BCall reuqest;
在回叫模式期间，如果TCAM收到了Icall或Bcall的请求，直接忽略
3) when TCAM is in call back mode ,if TCAM receive a income call ,when the voice call end ,the call back keep the timer until the call back time end ,and end the ecall service;
在回叫模式期间，如果TCAM收到了来电回拨，当语音通话结束后，回叫模式的计时器继续计时，直到回叫模式的计时器超时结束Ecall服务

4）During the callback mode, while waiting for the callback call, TCAM receive a new AA call or EA call,TCAM should send a MSD to call center and establish a voice call.
在回叫模式期间，等待回拨来电过程中，收到了新的AA或EA触发，需要发送MSD信息到坐席中心并拨打电话



2. When no EA/AA service is active, all incoming calls shall be rejected.
当没有EA/AA服务激活时，所有的来电回拨都将被拒绝
3. When in ECALL callback mode, the BCALL incoming call should be rejected.
当Ecall处于回叫模式，BCall的来电回拨会被拒绝

## LLM 理解摘要

结论：部分完成

证据：
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/inc/xcall_call_control.h:38-38 XCALL_STATUS_INTERNAL_CALLBACK_MODE 定义了回拨模式内部状态（enum值3），是回调模式状态机的基础
- /home/ubuntu/code/github/geea30_app/application/xcallapp/common/inc/xcall_common.h:96-98 XCALL_TIMER_ID_CALLBACK_MODE/XCALL_TIMER_ID_REPORT_CALLBACK_MODE_STATUS 定义了回调模式定时器和1s周期状态上报定时器ID
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:74-74 XCALL_CALLBACK_MODE_TIME_DEFAULT CN版本默认回调时间为25分钟，符合需求
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:299-310 xcall_is_need_enter_callback 判断是否进入回调模式：TSP未终止服务(isStopService=FALSE)时允许进入
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:520-533 xcall_set_callback_mode_remain_time/xcall_fetch_callback_mode_remain_time 管理回调模式剩余时间，1s递减一次，支持DB持久化
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:1128-1138 xcall_start_report_callback_mode_status_timer 启动1s周期的状态上报定时器(duration=1, E_GEE_TIMER_TYPE_CIRCLE)，满足1s周期上报要求
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:1116-1126 xcall_report_callback_mode_status_timer_expired_handler 定时到期处理：检查当前状态是否为CALLBACK_MODE，调用xcall_report_callback_status上报剩余时间
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_ihu_interaction.c:107-113 xcall_report_callback_status 构造XCallCallbackStatus(含remainTime)，通过XCALL_EXTERN_EVENT_NOTIFY_CALLBACK_STATUS推送消息
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callextern/src/xcall_comm_over_somip.cpp:445-471 xcall_notify_callback_status_to_ihu 通过SOME/IP的AsscMgrSrv_Server_CallBackStsEvt事件上报CallBackSts剩余时间到DHU
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_ihu_interaction.c:56-64 xcall_send_xcall_status_message_to_ihu 回调模式(第61行)设置callbackMode=TRUE发送到IHU(DHU)，满足CallBackMode=0x01需求
- /home/ubuntu/code/github/geea30_app/application/xcallapp/common/inc/xcall_ext_message.h:353-357 XCallStatusMessageToIHU 结构体包含BOOL callbackMode字段，用于向DHU上报CallBackMode信号
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:1159-1210 transition_internal_xcall_status_to_callback_mode 完整实现回拨模式状态切换：向IHU/ASM/RVDC发送状态、启动计时器、上报剩余时间
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:1077-1114 transition_internal_xcall_status_to_incoming_call 从回调模式到来电的转换处理(第1083-1098行)：回调期间来电可被接受并自动应答
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:2768-2791 xcall_tsp_stop_ecall_service TSP终止服务时设置isStopService=TRUE，阻止进入回调模式(第2784行)，区分正常挂断与TSP终止
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:2880-2932 xcall_voice_call_state_indication 通话结束(GSW_VOICE_CALL_END)时的回调模式切换逻辑(第2891-2925行)：处理正常挂断和来电挂断
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:1861-2000 xcall_coldstart_check_timer_expired_handler 冷启动恢复回调模式：从DB读取剩余时间并恢复CALLBACK_MODE状态(第1971-1999行)
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:2469-2495 xcall_physical_ecall_button_event_handler 回调/来电期间收到AA触发的处理(第2478-2486行)：发送MSD并重置回调计时器

未实现：BCALL/ICALL业务请求在回调模式期间的忽略处理未在xcallapp核心代码中找到显式实现; 回调模式下BCALL来电的拒绝处理未在通话状态机中找到显式实现（来电处理中无呼叫类型区分）; 无EA/AA服务激活时所有来电拒绝逻辑未在xcallapp核心层找到显式实现

可能根因：BCALL/ICALL请求可能在更高层的ServiceManager中处理，未在xcallapp代码中体现; 来电类型区分可能在模组驱动层完成，应用层仅处理ECALL相关来电

影响范围：exception flow: 回调模式期间BCALL/ICALL被错误接受

建议：1. 在BCALL/ICALL触发入口处增加回调模式检查，回调模式下直接忽略; 2. 在来电处理(GSW_VOICE_CALL_INCOMING)中增加回调模式下的BCALL来电检查与拒绝逻辑; 3. 建议在xcall_start_ecall入口处对BCALL/ICALL增加回调模式阻断条件; 4. 增加回调模式下无EA/AA服务时来电拒绝的明确实现

验证：1. 模拟回调模式：通话结束后检查CallBackMode=0x01上报和CallBackSts 1s周期上报; 2. 回调模式中触发BCALL按键：验证BCALL业务被忽略; 3. 回调模式中收到BCALL来电：验证来电被拒绝而非自动应答; 4. 验证25分钟回调超时后Ecall服务正确结束; 5. 验证TSP终止服务后不进入回调模式; 6. 验证回调模式中收到新AA触发时正确发送MSD并重置计时器

## 实现完成度

- **结论**：部分完成
- **优先级**：高
- **可信度**：中

## 实现证据

- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/inc/xcall_call_control.h:38-38 XCALL_STATUS_INTERNAL_CALLBACK_MODE 定义了回拨模式内部状态（enum值3），是回调模式状态机的基础
- /home/ubuntu/code/github/geea30_app/application/xcallapp/common/inc/xcall_common.h:96-98 XCALL_TIMER_ID_CALLBACK_MODE/XCALL_TIMER_ID_REPORT_CALLBACK_MODE_STATUS 定义了回调模式定时器和1s周期状态上报定时器ID
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:74-74 XCALL_CALLBACK_MODE_TIME_DEFAULT CN版本默认回调时间为25分钟，符合需求
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:299-310 xcall_is_need_enter_callback 判断是否进入回调模式：TSP未终止服务(isStopService=FALSE)时允许进入
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:520-533 xcall_set_callback_mode_remain_time/xcall_fetch_callback_mode_remain_time 管理回调模式剩余时间，1s递减一次，支持DB持久化
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:1128-1138 xcall_start_report_callback_mode_status_timer 启动1s周期的状态上报定时器(duration=1, E_GEE_TIMER_TYPE_CIRCLE)，满足1s周期上报要求
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:1116-1126 xcall_report_callback_mode_status_timer_expired_handler 定时到期处理：检查当前状态是否为CALLBACK_MODE，调用xcall_report_callback_status上报剩余时间
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_ihu_interaction.c:107-113 xcall_report_callback_status 构造XCallCallbackStatus(含remainTime)，通过XCALL_EXTERN_EVENT_NOTIFY_CALLBACK_STATUS推送消息
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callextern/src/xcall_comm_over_somip.cpp:445-471 xcall_notify_callback_status_to_ihu 通过SOME/IP的AsscMgrSrv_Server_CallBackStsEvt事件上报CallBackSts剩余时间到DHU
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_ihu_interaction.c:56-64 xcall_send_xcall_status_message_to_ihu 回调模式(第61行)设置callbackMode=TRUE发送到IHU(DHU)，满足CallBackMode=0x01需求
- /home/ubuntu/code/github/geea30_app/application/xcallapp/common/inc/xcall_ext_message.h:353-357 XCallStatusMessageToIHU 结构体包含BOOL callbackMode字段，用于向DHU上报CallBackMode信号
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:1159-1210 transition_internal_xcall_status_to_callback_mode 完整实现回拨模式状态切换：向IHU/ASM/RVDC发送状态、启动计时器、上报剩余时间
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:1077-1114 transition_internal_xcall_status_to_incoming_call 从回调模式到来电的转换处理(第1083-1098行)：回调期间来电可被接受并自动应答
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:2768-2791 xcall_tsp_stop_ecall_service TSP终止服务时设置isStopService=TRUE，阻止进入回调模式(第2784行)，区分正常挂断与TSP终止
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:2880-2932 xcall_voice_call_state_indication 通话结束(GSW_VOICE_CALL_END)时的回调模式切换逻辑(第2891-2925行)：处理正常挂断和来电挂断
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:1861-2000 xcall_coldstart_check_timer_expired_handler 冷启动恢复回调模式：从DB读取剩余时间并恢复CALLBACK_MODE状态(第1971-1999行)
- /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c:2469-2495 xcall_physical_ecall_button_event_handler 回调/来电期间收到AA触发的处理(第2478-2486行)：发送MSD并重置回调计时器

## 关键代码证据

| 文件 | 行号 | 符号 | 说明 |
|---|---:|---|---|
| /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/inc/xcall_call_control.h | 38-38 | XCALL_STATUS_INTERNAL_CALLBACK_MODE | 定义了回拨模式内部状态（enum值3），是回调模式状态机的基础 |
| /home/ubuntu/code/github/geea30_app/application/xcallapp/common/inc/xcall_common.h | 96-98 | XCALL_TIMER_ID_CALLBACK_MODE/XCALL_TIMER_ID_REPORT_CALLBACK_MODE_STATUS | 定义了回调模式定时器和1s周期状态上报定时器ID |
| /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c | 74-74 | XCALL_CALLBACK_MODE_TIME_DEFAULT | CN版本默认回调时间为25分钟，符合需求 |
| /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c | 299-310 | xcall_is_need_enter_callback | 判断是否进入回调模式：TSP未终止服务(isStopService=FALSE)时允许进入 |
| /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c | 520-533 | xcall_set_callback_mode_remain_time/xcall_fetch_callback_mode_remain_time | 管理回调模式剩余时间，1s递减一次，支持DB持久化 |
| /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c | 1128-1138 | xcall_start_report_callback_mode_status_timer | 启动1s周期的状态上报定时器(duration=1, E_GEE_TIMER_TYPE_CIRCLE)，满足1s周期上报要求 |
| /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c | 1116-1126 | xcall_report_callback_mode_status_timer_expired_handler | 定时到期处理：检查当前状态是否为CALLBACK_MODE，调用xcall_report_callback_status上报剩余时间 |
| /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_ihu_interaction.c | 107-113 | xcall_report_callback_status | 构造XCallCallbackStatus(含remainTime)，通过XCALL_EXTERN_EVENT_NOTIFY_CALLBACK_STATUS推送消息 |
| /home/ubuntu/code/github/geea30_app/application/xcallapp/callextern/src/xcall_comm_over_somip.cpp | 445-471 | xcall_notify_callback_status_to_ihu | 通过SOME/IP的AsscMgrSrv_Server_CallBackStsEvt事件上报CallBackSts剩余时间到DHU |
| /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_ihu_interaction.c | 56-64 | xcall_send_xcall_status_message_to_ihu | 回调模式(第61行)设置callbackMode=TRUE发送到IHU(DHU)，满足CallBackMode=0x01需求 |
| /home/ubuntu/code/github/geea30_app/application/xcallapp/common/inc/xcall_ext_message.h | 353-357 | XCallStatusMessageToIHU | 结构体包含BOOL callbackMode字段，用于向DHU上报CallBackMode信号 |
| /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c | 1159-1210 | transition_internal_xcall_status_to_callback_mode | 完整实现回拨模式状态切换：向IHU/ASM/RVDC发送状态、启动计时器、上报剩余时间 |
| /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c | 1077-1114 | transition_internal_xcall_status_to_incoming_call | 从回调模式到来电的转换处理(第1083-1098行)：回调期间来电可被接受并自动应答 |
| /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c | 2768-2791 | xcall_tsp_stop_ecall_service | TSP终止服务时设置isStopService=TRUE，阻止进入回调模式(第2784行)，区分正常挂断与TSP终止 |
| /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c | 2880-2932 | xcall_voice_call_state_indication | 通话结束(GSW_VOICE_CALL_END)时的回调模式切换逻辑(第2891-2925行)：处理正常挂断和来电挂断 |
| /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c | 1861-2000 | xcall_coldstart_check_timer_expired_handler | 冷启动恢复回调模式：从DB读取剩余时间并恢复CALLBACK_MODE状态(第1971-1999行) |
| /home/ubuntu/code/github/geea30_app/application/xcallapp/callaudio/src/xcall_call_control.c | 2469-2495 | xcall_physical_ecall_button_event_handler | 回调/来电期间收到AA触发的处理(第2478-2486行)：发送MSD并重置回调计时器 |

## 差异与缺口

- BCALL/ICALL业务请求在回调模式期间的忽略处理未在xcallapp核心代码中找到显式实现
- 回调模式下BCALL来电的拒绝处理未在通话状态机中找到显式实现（来电处理中无呼叫类型区分）
- 无EA/AA服务激活时所有来电拒绝逻辑未在xcallapp核心层找到显式实现

## 修改建议

- 1. 在BCALL/ICALL触发入口处增加回调模式检查，回调模式下直接忽略
- 2. 在来电处理(GSW_VOICE_CALL_INCOMING)中增加回调模式下的BCALL来电检查与拒绝逻辑
- 3. 建议在xcall_start_ecall入口处对BCALL/ICALL增加回调模式阻断条件
- 4. 增加回调模式下无EA/AA服务时来电拒绝的明确实现

## 验证建议

- 1. 模拟回调模式：通话结束后检查CallBackMode=0x01上报和CallBackSts 1s周期上报
- 2. 回调模式中触发BCALL按键：验证BCALL业务被忽略
- 3. 回调模式中收到BCALL来电：验证来电被拒绝而非自动应答
- 4. 验证25分钟回调超时后Ecall服务正确结束
- 5. 验证TSP终止服务后不进入回调模式
- 6. 验证回调模式中收到新AA触发时正确发送MSD并重置计时器

## 追踪信息

- 输出文件: docs/prd/PRD-requirement-5930-FC_665094_L3_25R1_1a3_Ecall功能的回拨模式_CN_-TCAM_ECALL_CALLBACK_mode.md
- 回写禅道: not_implemented


---
*本文档由 zentao-story-prd-analyzer 自动生成，仅供参考。*
