# Onda · 双端电商 Agent

面向消费者的客服助手与面向商家的经营助手。React 页面沿用 `素材图/` 的视觉设计；真实模型调用、业务数据与审批由 Python 后端处理，不再用前端固定回复模拟 Agent。

消费者采用 **OpenAI Agents SDK**，商家采用 **LangGraph**，共享受权限约束的工具和业务服务。默认模型为 **DeepSeek V4.1 Flash**，官方接口标识 `deepseek-flash`，地址 `https://api.deepseek.com`。OpenAI SDK 在这里用于编排与协议适配，不需要 OpenAI API 密钥。[DeepSeek 官方文档](https://api-docs.deepseek.com/)

## 本地启动

需要 Node.js 22、Python 3.12。Windows PowerShell：

```powershell
cd D:\找实习\电商agent
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r backend/requirements.lock --cache-dir .pip-cache
npm.cmd ci --cache .npm-cache
```

将 `backend/.env.example` 复制为 `backend/.env`，填写自己的密钥，本地运行时将 `ONDA_DEV_MODE` 改为 `true`。

```dotenv
DEEPSEEK_API_KEY=在这里填写自己的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
ONDA_DEV_MODE=true
```

后端终端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start-backend.ps1
```

另一个终端：

```powershell
cd D:\找实习\电商agent
npm.cmd run dev
```

打开 [Onda 本地页面](http://127.0.0.1:5173)，后端监听本机 8000 端口。Vite 将 `/api` 转发给后端。`npm run build` 生成静态前端；`npm run preview` **没有业务 API 代理**，不能替代上述完整启动方式。

首次启动自动创建 `.runtime/onda.db`，生成 **9 件商品、63 笔订单、4 个工单**；消费者只能看到自己的 3 笔订单。日期相对首次启动当天生成，业务 ID 固定，便于测试。再次启动不会覆盖已有记录。原始 DataCo 数据未读取、未提交。

## 功能

| 消费者 | 商家 |
| --- | --- |
| 商品咨询、预算筛选、推荐 | 7 / 30 / 90 天经营看板 |
| 自己的订单与基础物流查询 | 销售、库存、订单和工单分析 |
| 待发货订单取消申请 | 商品信息、价格、库存、上下架管理 |
| 已签收订单全额退款申请 | 登记发货、审核退款 |
| 售后规则查询、创建人工工单 | 工单回复、更新和完成 |
| 多轮对话、反馈、历史恢复 | 多轮对话、反馈、历史恢复 |

消费者导航为「商品页｜Onda智能助手｜个人中心」；商家为「数据看板｜商品管理｜订单管理｜工单管理｜Onda智能助手」。入口整张角色卡片可点击，GitHub 图标指向本仓库，默认头像不显示真人身份。

双端“展开详情”显示后端真实执行事件、依据摘要与风险等级，**不显示模型私有思维链**。状态通过 SSE 更新；最终回答整体返回，并非逐字流式输出。

## 人工确认与安全边界

业务修改先在服务端生成方案，展示目标与前后差异。只有本人点击“确认执行”才提交，无额外勾选。拒绝或仅关闭弹窗不修改业务数据。

- 后端再次检查权限、归属、状态、参数与数据版本；模型不能批准自己的方案。
- 方案 15 分钟有效；过期或数据变更后不能执行，可拒绝旧方案再发起。
- 同一方案重复确认不重复执行，事务与版本条件保护更新，操作记录进入审计日志。
- 退款申请 → 商家审核 → 退款处理中；**未接支付渠道，不声称资金到账**。完成工单不等于完成退款。
- 取消、退款、发货、商品更新、上下架及已有工单更新均走高风险确认。新商品只存草稿，创建咨询工单不改变订单或资金状态。
- 密钥仅在后端环境变量中使用。`.env`、数据库、缓存和运行报告被 Git 忽略。不要将密钥写入 `VITE_` 变量。

当前是**本机运行的功能原型，不是可直接公网部署的生产商城**。开发身份入口使用固定买家/商家身份，限回环地址且默认关闭；角色选择不是正式登录。禁止把开发服务器通过公网隧道或反向代理开放。生产上线需要真正的登录、租户成员关系、限流、任务队列、数据库迁移和运维配置。

## 架构

```text
React 页面 ── FastAPI 身份校验 / SSE / 审批接口
                    ├─ 消费者：OpenAI Agents SDK
                    │     tools → needs_approval → 保存 / 恢复 RunState
                    └─ 商家：LangGraph
                          analysis → review interrupt → checkpoint / resume
                              ↓
                    共享工具 → 业务服务 → 事务 / 审计
                              ↓
                    SQLAlchemy + SQLite 本地数据库
```

- `backend/agent_runtime.py`：双端编排、意图与情绪辅助识别、受控工具。
- `backend/services.py`：权限、状态流转、审批、经营指标计算。
- `backend/app.py`：会话、对话、SSE、审批与反馈接口。
- `backend/policies.py`：版本化售后规则；当前不是向量知识库。
- `backend/seed.py`：精简合成数据。
- `backend/evaluate.py`：隔离业务库的真实模型回归。
- `backend/improve.py`：失败与负反馈离线复盘，候选不自动上线。
- `src/LiveAgent.jsx`：真实对话、执行详情、确认与反馈。
- `src/DataDashboard.jsx`：由订单计算的图表。

业务数据采用带版本号的 JSON 聚合记录，聊天、事件、审批、审计独立持久化。`DATABASE_URL` 可配置 PostgreSQL，但**本轮只验证了 SQLite**；LangGraph 检查点仍是本地 SQLite，尚非多机部署架构。

对话上下文读取最近 16 条消息，历史保存在数据库；尚未实现跨会话长期偏好记忆。意图与情绪识别只辅助服务，不授予权限或改变退款条件。模型没有任意 SQL、文件系统或 Shell 工具。

## 评测与复盘

不调用模型的业务测试与前端构建：

```powershell
.venv\Scripts\python.exe -m pytest backend/tests -q
npm.cmd run build
```

真实模型回归会产生 API 费用，需显式选择：

```powershell
.venv\Scripts\python.exe -m backend.evaluate --live
```

每次使用新的 `.runtime/eval-*.db`，不修改正常业务库。覆盖查询、越权、否定请求、不可取消状态、取消确认、调价确认、经营分析及退款申请/审核。主要判断最终状态、违规方案和确认后数据变化；**不等于全面语言质量或事实准确性认证**。本仓库没有运行 VitaBench / MerchantBench 官方评测，没有其官方成绩。

反馈复盘：

```powershell
.venv\Scripts\python.exe -m backend.improve
.venv\Scripts\python.exe -m backend.improve --suggest
```

第一条只做本地统计；第二条将基础脱敏后的失败案例发给当前模型生成建议，会产生费用。产物仅保存于 `.runtime/`，不改线上提示词、权限或审批策略。使用真实客户数据前需加强脱敏。候选须人工审核、增加回归用例并通过独立冻结测试集，再手动发布。

详细说明见 [架构与评测说明](docs/architecture-and-evaluation.md)。`scripts/browser-check.js` 通过 Playwright CLI 的 `run-code --filename=scripts/browser-check.js` 执行，需要前后端启动且初始耳机订单仍待发货；会调用真实模型，但不确认业务修改。

## 未接入的部分

真实支付、真实物流、下单与库存预占、部分退款、退货运输、优惠活动、供应链采购、生产用户认证、自动上线的提示词优化不在本轮实现中。购物袋仅在浏览器本地保存，不等于下单；库存是可管理的独立字段，不模拟预占/回补。

看板显示销售统计口径，缺少成本与流量时不计算利润或转化率。素材图用于版式参考和照片裁切，复用或公开部署前请确认图片素材使用权。
