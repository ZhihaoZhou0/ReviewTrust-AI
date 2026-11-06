# 本地 PostgreSQL 与首次导入

本流程使用 [DataHive Amazon Reviews 固定快照](data-audit.md)，供 A1、A2 和后续分析模块共享。数据库定义在 [schema.sql](../database/schema.sql)，导入逻辑在 [load_snapshot.sql](../database/load_snapshot.sql)。

## 前提

- Docker Compose 可用。
- Python 3 可用；清洗脚本只依赖标准库。
- `psql` 客户端在 `PATH` 中。导入脚本会检查它是否存在。
- `data/raw/products.csv` 与 `data/raw/reviews.csv` 已按 [数据审计文档](data-audit.md)中的固定版本下载。原始和清洗后的 CSV 都不会被 Git 跟踪。

## 启动和导入

在仓库根目录运行：

```bash
docker compose up -d --wait db
python3 pipeline/load_snapshot.py
```

第二条命令会重新清洗原始 CSV、创建 Schema、将两份清洗结果载入临时表，并在**一个数据库事务**中写入正式表。失败时导入事务回滚。再次运行同一命令不会产生重复商品或评论；已存在但来源内容变化的商品会更新，评论按 `source_row_hash` 去重。A2 负责未来版本的增量加载策略。

本地开发默认配置：

| 项目 | 值 |
| --- | --- |
| 主机 | `127.0.0.1` |
| 端口 | `5433` |
| 数据库 | `reviewtrust` |
| 用户 | `reviewtrust` |
| 密码 | `reviewtrust_dev`（仅本地开发） |
| 数据卷 | `reviewtrust-ai_postgres_data` |

Compose 的 `POSTGRES_PORT`、`POSTGRES_DB`、`POSTGRES_USER`、`POSTGRES_PASSWORD` 可通过环境变量覆盖。导入脚本使用对应值，也支持 `PGHOST`、`PGPORT`、`PGDATABASE`、`PGUSER`、`PGPASSWORD`。改动凭据时请确保 Compose 与导入脚本读到相同的设置。数据库仅绑定本机回环地址；其他容器连接时使用服务名 `db` 和容器端口 `5432`。

## 验证与查询

```bash
docker compose exec db psql -U reviewtrust -d reviewtrust -c \
  "SELECT count(*) FROM reviewtrust.products;"
docker compose exec db psql -U reviewtrust -d reviewtrust -c \
  "SELECT count(*) FROM reviewtrust.reviews;"
```

本次固定快照预期为 **2,727 个商品、252,134 条去重后评论**。字段口径和下游查询示例见 [数据契约](data-contract.md)。

`docker compose stop db` 可暂停数据库；再次 `docker compose up -d --wait db` 会使用原数据卷。`docker compose down` 会移除容器和网络，但保留数据卷。

## 已验证

在本机 PostgreSQL 16 上连续执行导入两次：首次插入 2,727 个商品、252,134 条评论；第二次两个正式表的插入数均为 0，最终行数保持不变。导入 SQL 的暂存表核对均通过。
