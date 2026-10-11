# 发票管家 · 软件需求与规格说明

> 版本：v1.0（MVP）  |  日期：2026-09-21

---

## 一、功能需求

### 1.1 邮箱配置

| 编号 | 需求 | 优先级 |
|---|---|---|
| F-101 | 用户可配置邮箱信息：邮箱地址、IMAP 服务器地址、端口、授权码 | P0 |
| F-102 | 支持 QQ 邮箱（imap.qq.com:993）和 163 邮箱（imap.163.com:993）的默认配置一键填充 | P0 |
| F-103 | 配置后可测试连接，显示成功/失败及原因 | P0 |
| F-104 | 授权码加密存储在本地数据库，不明文保存 | P1 |
| F-105 | 支持修改和删除邮箱配置 | P1 |

### 1.2 发票采集

| 编号 | 需求 | 优先级 |
|---|---|---|
| F-201 | 用户点击"一键采集"，系统连接邮箱拉取邮件 | P0 |
| F-202 | 服务端粗过滤：按日期范围（默认最近 90 天）+ 文件夹（收件箱） | P0 |
| F-203 | 客户端精过滤：发件人域名白名单（如 sinopec.com、didi.com 等可配置）+ 主题关键词（"发票"、"电子发票"、"数电票"、"invoice"） | P0 |
| F-204 | 增量同步：记录已处理邮件 UID，只拉取新邮件，不重复处理 | P0 |
| F-205 | 下载邮件附件，仅保留 .pdf / .ofd 扩展名文件 | P0 |
| F-206 | PDF 魔数校验（%PDF-），非真实 PDF 丢弃 | P0 |
| F-207 | 文件名/主题命中黑名单关键词（"结账单"、"对账单"、"行程单"、"账单"）则跳过 | P0 |
| F-208 | 采集完成后显示统计：本次扫描邮件数、识别到发票数、下载成功数、失败数 | P0 |
| F-209 | 采集过程中可查看实时进度 | P1 |
| F-210 | 支持指定采集日期范围 | P1 |

### 1.3 大模型识别

| 编号 | 需求 | 优先级 |
|---|---|---|
| F-301 | 对每张下载的发票 PDF 调用通义千问 Qwen-VL API 进行识别 | P0 |
| F-302 | 提取以下结构化字段：发票号码、开票日期、价税合计（含税金额）、不含税金额、税额、销售方名称、销售方税号、购买方名称、购买方税号、发票类型、消费类目 | P0 |
| F-303 | 识别结果以 JSON 格式返回并解析 | P0 |
| F-304 | 去重：发票号码已存在则跳过识别，标记为重复 | P0 |
| F-305 | 识别失败的发票记录错误日志，可在前端查看并手动重试 | P0 |
| F-306 | 支持手动编辑识别出的字段内容 | P1 |
| F-307 | 识别耗时单张 ≤ 10 秒 | P1 |

### 1.4 归类与存储

| 编号 | 需求 | 优先级 |
|---|---|---|
| F-401 | 按销售方名称自动归类分组 | P0 |
| F-402 | 按购买方名称自动归类分组 | P0 |
| F-403 | 发票文件保存在本地目录，按"销售方/年份"二级目录组织 | P0 |
| F-404 | 发票元数据（识别字段）存入 SQLite 数据库 | P0 |
| F-405 | 文件命名规则：`{开票日期}_{销售方简称}_{发票号后6位}.pdf` | P1 |
| F-406 | 支持手动修改发票的归类（销售方/购买方） | P1 |

### 1.5 检索与查询

| 编号 | 需求 | 优先级 |
|---|---|---|
| F-501 | 按销售方筛选（下拉选择已有的销售方列表） | P0 |
| F-502 | 按购买方筛选 | P0 |
| F-503 | 按开票日期范围筛选（起止日期） | P0 |
| F-504 | 按金额区间筛选（最小金额、最大金额） | P0 |
| F-505 | 按发票类型筛选（电子普票/数电票/增值税专票等） | P1 |
| F-506 | 按使用状态筛选（全部/未使用/已使用），默认显示"未使用" | P0 |
| F-507 | 关键词搜索（发票号、销售方、购买方模糊匹配） | P1 |
| F-508 | 多条件组合筛选，结果实时更新 | P0 |
| F-509 | 列表支持按日期、金额排序 | P1 |

### 1.6 使用标记

| 编号 | 需求 | 优先级 |
|---|---|---|
| F-601 | 单张发票可标记为"已使用"或"未使用" | P0 |
| F-602 | 支持批量标记（勾选多张后批量操作） | P0 |
| F-603 | 标记已使用时可填写使用备注（如报销单号） | P1 |
| F-604 | 标记已使用后，默认查询不再显示该发票（可通过筛选查看） | P0 |
| F-605 | 可撤销已使用标记，恢复为未使用 | P0 |
| F-606 | 记录标记时间和操作历史 | P2 |

### 1.7 预览与下载

| 编号 | 需求 | 优先级 |
|---|---|---|
| F-701 | 点击发票可在线预览 PDF 内容 | P0 |
| F-702 | 支持下载发票 PDF 到本地 | P0 |
| F-703 | 发票详情页展示所有识别字段 | P0 |
| F-704 | 支持批量下载选中的发票 | P1 |

### 1.8 仪表盘

| 编号 | 需求 | 优先级 |
|---|---|---|
| F-801 | 显示发票总数、总金额、未使用数量、未使用金额 | P0 |
| F-802 | 显示按销售方的发票数量和金额 TOP 排行 | P1 |
| F-803 | 显示按月度的发票数量和金额趋势图 | P1 |
| F-804 | 显示最近采集的发票列表 | P1 |

---

## 二、非功能需求

| 编号 | 需求 | 指标 |
|---|---|---|
| NF-1 | 性能：单张发票识别响应时间 | ≤ 10 秒 |
| NF-2 | 性能：列表查询响应时间 | ≤ 1 秒（1000 条以内） |
| NF-3 | 性能：一键采集 100 封邮件耗时 | ≤ 2 分钟 |
| NF-4 | 兼容性：前端浏览器 | Chrome / Edge / Safari 最新 2 个版本 |
| NF-5 | 兼容性：移动端 | iOS Safari / Android Chrome，宽度 ≥ 375px |
| NF-6 | 数据安全：授权码存储 | AES 加密存储，不明文保存 |
| NF-7 | 数据安全：API Key 存储 | 本地加密存储，不上传第三方 |
| NF-8 | 可靠性：采集异常 | 单封邮件失败不影响整体流程，记录错误日志 |
| NF-9 | 可维护性：代码 | 模块化，邮箱采集/OCR/存储/API 分层 |
| NF-10 | 部署：启动方式 | 单命令启动（后端 + 前端静态文件） |

---

## 三、数据模型

### 3.1 邮箱配置表（email_account）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 主键 |
| email | TEXT | 邮箱地址 |
| imap_host | TEXT | IMAP 服务器地址 |
| imap_port | INTEGER | 端口（默认 993） |
| auth_code | TEXT | 授权码（加密存储） |
| use_ssl | BOOLEAN | 是否启用 SSL（默认 True） |
| last_uid | INTEGER | 上次处理到的邮件 UID（增量同步用） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### 3.2 发票表（invoice）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 主键 |
| invoice_no | TEXT | 发票号码（唯一，去重用） |
| invoice_type | TEXT | 发票类型（电子普票/数电票/专票等） |
| invoice_date | DATE | 开票日期 |
| amount_total | DECIMAL(12,2) | 价税合计（含税金额） |
| amount_without_tax | DECIMAL(12,2) | 不含税金额 |
| tax_amount | DECIMAL(12,2) | 税额 |
| seller_name | TEXT | 销售方名称 |
| seller_tax_no | TEXT | 销售方税号 |
| buyer_name | TEXT | 购买方名称 |
| buyer_tax_no | TEXT | 购买方税号 |
| category | TEXT | 消费类目（如餐饮/交通/住宿） |
| file_path | TEXT | 发票文件本地路径 |
| file_name | TEXT | 原始文件名 |
| source_email | TEXT | 来源邮箱 |
| source_mail_uid | INTEGER | 来源邮件 UID |
| status | TEXT | 状态：unused（未使用）/ used（已使用） |
| used_remark | TEXT | 使用备注 |
| used_at | DATETIME | 使用时间 |
| ocr_status | TEXT | OCR 状态：success / failed |
| ocr_error | TEXT | OCR 错误信息 |
| created_at | DATETIME | 入库时间 |
| updated_at | DATETIME | 更新时间 |

### 3.3 采集日志表（sync_log）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 主键 |
| started_at | DATETIME | 采集开始时间 |
| finished_at | DATETIME | 采集结束时间 |
| total_scanned | INTEGER | 扫描邮件数 |
| invoices_found | INTEGER | 识别到发票数 |
| invoices_downloaded | INTEGER | 下载成功数 |
| invoices_skipped | INTEGER | 跳过数（重复/非发票） |
| invoices_failed | INTEGER | 失败数 |
| error_detail | TEXT | 错误详情（JSON） |

---

## 四、核心业务规则

### 4.1 发票去重规则
- **唯一键**：发票号码（invoice_no）
- 入库前检查发票号是否已存在，存在则跳过，并在日志中记录"重复"
- 若发票号识别失败（OCR 未提取到），则用"文件 MD5 + 开票日期"作为备用去重键

### 4.2 邮件过滤规则
**第一层（服务端 IMAP SEARCH）：**
- 日期范围：默认最近 90 天
- 文件夹：INBOX

**第二层（客户端）：**
- 发件人域名白名单（可配置，默认包含常见发票发送方）
- 主题关键词命中：`发票` / `电子发票` / `数电票` / `invoice` / `Invoice`
- 附件扩展名白名单：`.pdf` / `.ofd`

**第三层（文件级）：**
- PDF 魔数校验：文件头必须是 `%PDF-`
- 黑名单关键词：文件名含 `结账单` / `对账单` / `行程单` / `账单` 则跳过

### 4.3 归类规则
- **销售方归类**：按 `seller_name` 字段分组，相同销售方的发票归为一组
- **购买方归类**：按 `buyer_name` 字段分组
- 分组名称取识别出的完整公司名称，前端可显示简称（取前 10 字）

### 4.4 使用状态规则
- 新入库发票默认状态为 `unused`（未使用）
- 标记为 `used` 后，默认列表查询不显示
- 用户可通过筛选"已使用"查看历史已用发票
- 可随时在 `unused` 和 `used` 之间切换

---

## 五、API 接口设计（RESTful）

### 5.1 邮箱配置

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/email` | 获取邮箱配置 |
| POST | `/api/email` | 新增/更新邮箱配置 |
| DELETE | `/api/email/{id}` | 删除邮箱配置 |
| POST | `/api/email/test` | 测试邮箱连接 |

### 5.2 发票采集

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/sync/start` | 开始一键采集（返回任务 ID） |
| GET | `/api/sync/status/{task_id}` | 查询采集进度 |
| GET | `/api/sync/logs` | 查询历史采集日志 |

### 5.3 发票管理

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/invoices` | 发票列表（支持筛选参数） |
| GET | `/api/invoices/{id}` | 发票详情 |
| PUT | `/api/invoices/{id}` | 更新发票字段（手动编辑） |
| DELETE | `/api/invoices/{id}` | 删除发票记录及文件 |
| GET | `/api/invoices/{id}/file` | 下载发票文件 |
| GET | `/api/invoices/{id}/preview` | 在线预览 PDF |
| POST | `/api/invoices/{id}/ocr-retry` | 重试 OCR 识别 |

### 5.4 使用标记

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/invoices/{id}/use` | 标记为已使用 |
| POST | `/api/invoices/{id}/unuse` | 取消使用标记 |
| POST | `/api/invoices/batch-use` | 批量标记已使用 |

### 5.5 归类与统计

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/groups/sellers` | 按销售方分组统计 |
| GET | `/api/groups/buyers` | 按购买方分组统计 |
| GET | `/api/dashboard` | 仪表盘统计数据 |

### 5.6 筛选参数说明（GET /api/invoices）

| 参数 | 类型 | 说明 |
|---|---|---|
| seller | string | 销售方名称（模糊匹配） |
| buyer | string | 购买方名称（模糊匹配） |
| date_from | date | 开票日期起 |
| date_to | date | 开票日期止 |
| amount_min | decimal | 最小金额 |
| amount_max | decimal | 最大金额 |
| type | string | 发票类型 |
| status | string | unused / used / all（默认 unused） |
| keyword | string | 关键词搜索 |
| page | int | 页码（默认 1） |
| page_size | int | 每页条数（默认 20） |
| sort | string | 排序字段：date / amount |
| order | string | asc / desc |

---

## 六、配置项说明

以下配置项通过 `.env` 文件管理：

| 配置项 | 示例值 | 说明 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./invoices.db` | 数据库路径 |
| `STORAGE_PATH` | `./invoices_files` | 发票文件存储目录 |
| `QWEN_API_KEY` | `sk-xxxxxxxx` | 通义千问 API Key |
| `QWEN_MODEL` | `qwen-vl-max` | 使用的模型名称 |
| `ENCRYPTION_KEY` | `随机生成的32位密钥` | 授权码加密密钥 |
| `DEFAULT_SYNC_DAYS` | `90` | 默认采集最近天数 |
| `HOST` | `0.0.0.0` | 后端监听地址 |
| `PORT` | `8000` | 后端端口 |
