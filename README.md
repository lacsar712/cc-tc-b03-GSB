# 隧道收敛测缝台

测量员登记里程桩号与收敛毫米值。接口进程内后台线程认领待判行（不另起 worker 容器），按绝对值是否不超过 3.0 mm 给出合格或超限。页面是 Svelte。

页眉挂两个专页：**记录列表**（提交与台账）和**色块墙**（平面图）。色块墙左边维护断面坐标，右边整面墙每 2 秒刷新，每个断面一个色块，颜色表示该断面最近一次办结单据的结论：绿=合格、红=超限、灰=从未办结（不暗示合格）。颜色以 `GET /api/wall` 返回为准，页面与接口同源。同一桩号只认已办结单据中编号最大的那一张。测量员可在墙上拖拽色块或在左侧改坐标；巡检岗只读，不能改坐标也不能填报。提交新桩号读数时自动在墙上落位建断面。

## 技术栈

- 后端：Flask、Gunicorn、SQLAlchemy、进程内认领线程
- 前端：Svelte、Vite、nginx 反代 `/api`
- 数据库：PostgreSQL 16

## 端口

| 服务 | 地址 |
|------|------|
| 页面 | http://localhost:3201 |
| 接口 | http://localhost:8201 |
| PostgreSQL | localhost:54401（库名 `tunnelconv`） |

## 账号

| 用户 | 密码 | 权限 |
|------|------|------|
| surveyor | surv123456 | 测量员：可提交读数、建断面、拖/改坐标 |
| inspector | insp123456 | 巡检岗：只读，不能改坐标也不能填报 |

## 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 登录取 token |
| GET | `/api/logs` | 读数台账（登录） |
| POST | `/api/logs` | 提交读数（仅测量员），新桩号自动建断面 |
| GET | `/api/wall` | 色块墙：断面坐标 + 最近办结结论与颜色（登录） |
| POST | `/api/sections` | 建断面（仅测量员），桩号唯一，坐标留空自动落位 |
| PATCH | `/api/sections/<id>` | 改断面桩号/坐标（仅测量员） |

`/api/wall` 每行：`{id, chainage, x, y, verdict, color, last_log_id, processed_at}`；`verdict` 为 `合格`/`超限`/`null`，`color` 对应 `green`/`red`/`gray`。

## 启动

```bash
cd projects/21-tunnel-convergence-desk
docker compose up --build
```

健康检查：`GET http://localhost:8201/api/health`

## 种子

| 桩号 | 收敛 | 结论 | 墙色 |
|------|------|------|------|
| K12+180 | 1.2 mm | 合格 | 绿 |
| K18+040 | 5.6 mm | 超限 | 红 |
| K25+300 | —（无办结单据） | — | 灰 |
