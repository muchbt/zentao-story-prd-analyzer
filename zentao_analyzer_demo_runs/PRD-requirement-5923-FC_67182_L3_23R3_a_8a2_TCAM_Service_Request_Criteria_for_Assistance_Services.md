# PRD: FC_67182_L3 23R3.a(8a2)_TCAM Service Request Criteria for Assistance Services

## 来源信息

- 条目类型: requirement
- 条目 ID: 5923
- 状态: active
- 优先级: 1
- 生成时间: 2026-05-22T15:29:24.421192+08:00


## 原始需求摘要

Service Request Criteria for Emergency Assist, Roadside Assist and Automatic Assist




Service Request criteria
Request Description
Resource group
Service Release Request criteria
Release Request description
See requirements for activation criterias for each service.
REQPROD  : TCAM Start conditions for AA service
REQPROD  : TCAM Start conditions for EA service

send the signal:TelmAsscMgrActvNetSrvInt
The telematic application need to communicate current state of the telematic services to the telematic application on the DHU.
RESOURCE_GROUP=2
See REQPROD  : TCAM Ending service EA and AA.
When the service is deactivated the IP network shall be released.
 
 
 
 
 
 




Note: Information about ServiceIDs and handling of Service Requests is specified in LCs ‘IPLM’ in the document, SRD SPA Infotainment Platform and in section ‘IP Link Manager’ in the document,  IP Command Protocol.

## LLM 理解摘要

结论：部分完成

证据：
- application/xcallapp/callaudio/src/xcall_call_control.c:2291-2360 xcall_start_ecall 实现了 EA(ManualECall)、AA(AutoECall)、RA(BCall) 的 eCall 服务启动逻辑，包含服务激活条件检查
- application/xcallapp/callaudio/src/xcall_call_control.c:2263-2289 xcall_check_service_active_condition 实现了服务激活条件检查：车配置检查、使用模式检查、车辆模式检查
- application/xcallapp/callextern/src/xcall_comm_over_somip.cpp:170-188 xcall_request_resource_group_and_pri / xcall_release_resource_group_and_pri 实现了 RG2 (RESOURCE_GROUP=2) 资源组的请求和释放，服务停用时释放 IP 网络
- application/xcallapp/callaudio/src/xcall_call_control.c:29-75 SERVICE_DELAY_TIME_EA/RA_DEFAULT, SERVICE_STANDBY_TIME_AA/EA/RA_DEFAULT 定义了 EA/RA/AA 服务的延迟时间和待机时间参数
- service/parameter/inc/param_keys.h:136-147 param_keys (SERVICE_DELAY_TIME_EA/RA, SERVICE_STANDBY_TIME_AA/EA/RA, AS_RESOURCE_GROUP, NO_NETWORK_SERVICE_DELAY_TIME) 参数键定义：EA/RA 服务延迟时间、AA/EA/RA 待机时间、资源组、无网络服务延迟时间
- service/someip/tcamservice/SOMEIP_DB_2243900_GEN/AsscMgrSrv/server/impl/src/AsscMgrSrvStubImpl.cpp:58-110 AsscMgrSrvStubImpl::Init/Act/Stop, XCallStatusMtd, ECALLButtonStatusMtd AsscMgrSrv SOMEIP 服务骨架已构建，提供了 XCallStatus 和 ECALLButtonStatus 方法，但业务逻辑委托给 IPC 层，Act() 自定义逻辑为空
- service/someip/tcamservice/SOMEIP_DB_2243900_GEN/AsscMgrSrv/datatypes/AsscMgrSrv_types.h:40-46 CallType4 enum 定义了呼叫类型枚举：ICall=1, BCall=2(RA), ManualeCall=3(EA), AutoeCall=4(AA)
- service/someip/tcamservice/utils/src/ServiceManager/ServiceAsscMgrSrv.cpp:19-119 ServiceIfManager::XCallStatusMtd, AsscMgrSrvIpcXCallStatusMtd AsscMgrSrv 的 IPC 通信层已实现：请求转发和响应处理
- service/someip/inc/service_operation_id.h:98-107 AsscMgrSrv operation IDs AsscMgrSrv 的所有方法/事件操作 ID 已定义：XCallStatusMtd, ECALLButtonStatusMtd, XCallStatusEvt, MUTECommandEvt, POIInfoPushEvt, CallBackStsEvt, ETAInfoEvt, ECALLButtonStatusEvt

未实现：信号 TelmAsscMgrActvNetSrvInt 未在源代码中找到——该信号在需求中明确要求用于向 DHU 通报远程信息处理服务状态; AsscMgrSrvStubImpl::Act() 中自定义业务逻辑为空——仅有一个空循环线程，未填充具体的服务请求标准处理逻辑; 需求引用了 REQPROD: TCAM Start conditions for AA/EA service 和 TCAM Ending service EA/AA 等外部需求，但这些启停条件的完整标准链无法在代码中验证; AS_RESOURCE_GROUP 默认值为 1，但代码中硬编码为 RG2，与需求描述的 RESOURCE_GROUP=2 部分一致但参数未使用

可能根因：TelmAsscMgrActvNetSrvInt 信号可能定义在未纳入代码上下文的平台级配置或 ARXML 描述文件中; 服务请求标准的具体业务逻辑可能实现在运行时的 TSP 端或其他 MCU 层，而不是 SOC 侧; AsscMgrSrv 的 Act() 注释为'自定义逻辑编写,添加代码在下面'，表明该占位逻辑尚未实现

影响范围：AsscMgrSrv（Association Manager Service）——服务请求标准的主要服务接口; xcallapp（callaudio + callextern）——eCall/辅助服务的实际调用逻辑实现; SOMEIP 通信基础设施——服务状态上报通道

建议：实现 TelmAsscMgrActvNetSrvInt 信号的生成和发送逻辑，将当前远程信息处理服务状态（EA/RA/AA 激活/空闲）上报至 DHU; 填充 AsscMgrSrvStubImpl::Act() 中的自定义业务逻辑，完善服务请求标准的主动判断和状态机管理; 验证 AS_RESOURCE_GROUP 参数的使用方式：代码中硬编码了 RG2，应考虑通过参数表动态获取

验证：在代码库中全局搜索 TelmAsscMgrActvNetSrvInt 确认是否真的不存在; 检查平台级 ARXML 或 SOMEIP 数据库文件（SDB）中是否定义了该信号; 验证 xcall_check_service_active_condition() 中激活标准是否完整覆盖需求中的 EA/RA/AA 启动条件; 编译验证 AsscMgrSrv 服务并能正常运行

## 实现完成度

- **结论**：部分完成
- **优先级**：中
- **可信度**：中

## 实现证据

- application/xcallapp/callaudio/src/xcall_call_control.c:2291-2360 xcall_start_ecall 实现了 EA(ManualECall)、AA(AutoECall)、RA(BCall) 的 eCall 服务启动逻辑，包含服务激活条件检查
- application/xcallapp/callaudio/src/xcall_call_control.c:2263-2289 xcall_check_service_active_condition 实现了服务激活条件检查：车配置检查、使用模式检查、车辆模式检查
- application/xcallapp/callextern/src/xcall_comm_over_somip.cpp:170-188 xcall_request_resource_group_and_pri / xcall_release_resource_group_and_pri 实现了 RG2 (RESOURCE_GROUP=2) 资源组的请求和释放，服务停用时释放 IP 网络
- application/xcallapp/callaudio/src/xcall_call_control.c:29-75 SERVICE_DELAY_TIME_EA/RA_DEFAULT, SERVICE_STANDBY_TIME_AA/EA/RA_DEFAULT 定义了 EA/RA/AA 服务的延迟时间和待机时间参数
- service/parameter/inc/param_keys.h:136-147 param_keys (SERVICE_DELAY_TIME_EA/RA, SERVICE_STANDBY_TIME_AA/EA/RA, AS_RESOURCE_GROUP, NO_NETWORK_SERVICE_DELAY_TIME) 参数键定义：EA/RA 服务延迟时间、AA/EA/RA 待机时间、资源组、无网络服务延迟时间
- service/someip/tcamservice/SOMEIP_DB_2243900_GEN/AsscMgrSrv/server/impl/src/AsscMgrSrvStubImpl.cpp:58-110 AsscMgrSrvStubImpl::Init/Act/Stop, XCallStatusMtd, ECALLButtonStatusMtd AsscMgrSrv SOMEIP 服务骨架已构建，提供了 XCallStatus 和 ECALLButtonStatus 方法，但业务逻辑委托给 IPC 层，Act() 自定义逻辑为空
- service/someip/tcamservice/SOMEIP_DB_2243900_GEN/AsscMgrSrv/datatypes/AsscMgrSrv_types.h:40-46 CallType4 enum 定义了呼叫类型枚举：ICall=1, BCall=2(RA), ManualeCall=3(EA), AutoeCall=4(AA)
- service/someip/tcamservice/utils/src/ServiceManager/ServiceAsscMgrSrv.cpp:19-119 ServiceIfManager::XCallStatusMtd, AsscMgrSrvIpcXCallStatusMtd AsscMgrSrv 的 IPC 通信层已实现：请求转发和响应处理
- service/someip/inc/service_operation_id.h:98-107 AsscMgrSrv operation IDs AsscMgrSrv 的所有方法/事件操作 ID 已定义：XCallStatusMtd, ECALLButtonStatusMtd, XCallStatusEvt, MUTECommandEvt, POIInfoPushEvt, CallBackStsEvt, ETAInfoEvt, ECALLButtonStatusEvt

## 关键代码证据

| 文件 | 行号 | 符号 | 说明 |
|---|---:|---|---|
| application/xcallapp/callaudio/src/xcall_call_control.c | 2291-2360 | xcall_start_ecall | 实现了 EA(ManualECall)、AA(AutoECall)、RA(BCall) 的 eCall 服务启动逻辑，包含服务激活条件检查 |
| application/xcallapp/callaudio/src/xcall_call_control.c | 2263-2289 | xcall_check_service_active_condition | 实现了服务激活条件检查：车配置检查、使用模式检查、车辆模式检查 |
| application/xcallapp/callextern/src/xcall_comm_over_somip.cpp | 170-188 | xcall_request_resource_group_and_pri / xcall_release_resource_group_and_pri | 实现了 RG2 (RESOURCE_GROUP=2) 资源组的请求和释放，服务停用时释放 IP 网络 |
| application/xcallapp/callaudio/src/xcall_call_control.c | 29-75 | SERVICE_DELAY_TIME_EA/RA_DEFAULT, SERVICE_STANDBY_TIME_AA/EA/RA_DEFAULT | 定义了 EA/RA/AA 服务的延迟时间和待机时间参数 |
| service/parameter/inc/param_keys.h | 136-147 | param_keys (SERVICE_DELAY_TIME_EA/RA, SERVICE_STANDBY_TIME_AA/EA/RA, AS_RESOURCE_GROUP, NO_NETWORK_SERVICE_DELAY_TIME) | 参数键定义：EA/RA 服务延迟时间、AA/EA/RA 待机时间、资源组、无网络服务延迟时间 |
| service/someip/tcamservice/SOMEIP_DB_2243900_GEN/AsscMgrSrv/server/impl/src/AsscMgrSrvStubImpl.cpp | 58-110 | AsscMgrSrvStubImpl::Init/Act/Stop, XCallStatusMtd, ECALLButtonStatusMtd | AsscMgrSrv SOMEIP 服务骨架已构建，提供了 XCallStatus 和 ECALLButtonStatus 方法，但业务逻辑委托给 IPC 层，Act() 自定义逻辑为空 |
| service/someip/tcamservice/SOMEIP_DB_2243900_GEN/AsscMgrSrv/datatypes/AsscMgrSrv_types.h | 40-46 | CallType4 enum | 定义了呼叫类型枚举：ICall=1, BCall=2(RA), ManualeCall=3(EA), AutoeCall=4(AA) |
| service/someip/tcamservice/utils/src/ServiceManager/ServiceAsscMgrSrv.cpp | 19-119 | ServiceIfManager::XCallStatusMtd, AsscMgrSrvIpcXCallStatusMtd | AsscMgrSrv 的 IPC 通信层已实现：请求转发和响应处理 |
| service/someip/inc/service_operation_id.h | 98-107 | AsscMgrSrv operation IDs | AsscMgrSrv 的所有方法/事件操作 ID 已定义：XCallStatusMtd, ECALLButtonStatusMtd, XCallStatusEvt, MUTECommandEvt, POIInfoPushEvt, CallBackStsEvt, ETAInfoEvt, ECALLButtonStatusEvt |

## 差异与缺口

- 信号 TelmAsscMgrActvNetSrvInt 未在源代码中找到——该信号在需求中明确要求用于向 DHU 通报远程信息处理服务状态
- AsscMgrSrvStubImpl::Act() 中自定义业务逻辑为空——仅有一个空循环线程，未填充具体的服务请求标准处理逻辑
- 需求引用了 REQPROD: TCAM Start conditions for AA/EA service 和 TCAM Ending service EA/AA 等外部需求，但这些启停条件的完整标准链无法在代码中验证
- AS_RESOURCE_GROUP 默认值为 1，但代码中硬编码为 RG2，与需求描述的 RESOURCE_GROUP=2 部分一致但参数未使用

## 修改建议

- 实现 TelmAsscMgrActvNetSrvInt 信号的生成和发送逻辑，将当前远程信息处理服务状态（EA/RA/AA 激活/空闲）上报至 DHU
- 填充 AsscMgrSrvStubImpl::Act() 中的自定义业务逻辑，完善服务请求标准的主动判断和状态机管理
- 验证 AS_RESOURCE_GROUP 参数的使用方式：代码中硬编码了 RG2，应考虑通过参数表动态获取

## 验证建议

- 在代码库中全局搜索 TelmAsscMgrActvNetSrvInt 确认是否真的不存在
- 检查平台级 ARXML 或 SOMEIP 数据库文件（SDB）中是否定义了该信号
- 验证 xcall_check_service_active_condition() 中激活标准是否完整覆盖需求中的 EA/RA/AA 启动条件
- 编译验证 AsscMgrSrv 服务并能正常运行

## 追踪信息

- 输出文件: docs/prd/PRD-requirement-5923-FC_67182_L3_23R3_a_8a2_TCAM_Service_Request_Criteria_for_Assistance_Services.md
- 回写禅道: not_implemented


---
*本文档由 zentao-story-prd-analyzer 自动生成，仅供参考。*
