# 数据库迁移（Alembic）

## 关键文件
| 文件 | 作用 |
| --- | --- |
| `env.py` | 读取 `settings.database_url`，异步引擎，`target_metadata = Base.metadata` |
| `versions/` | 迁移脚本（按时间顺序） |
| `../alembic.ini` | 配置；连接串留空，由 env.py 注入 |

## 常用命令
```bash
make revision m="add product"   # 生成迁移（autogenerate）
make migrate                    # 应用到最新
uv run alembic downgrade -1     # 回滚一步
uv run alembic current          # 当前版本
```

## 规约
- 只允许通过迁移改表结构，禁止手改库。
- 生成后必须 review：`compare_type` 已开启，注意 MySQL 的 `Boolean`/`BigInteger`/枚举默认值差异。
- 迁移文件随代码提交；生产发布前先在预发库跑一遍。

## 依赖
上游：`app.models`、`app.core.config`
