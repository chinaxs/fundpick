# 部署说明

首次体验推荐先完成[README的开发安装](../README.md#快速开始)。本文件说明生产配置边界，不声称已经完成一键生产部署。

## 服务组成

- 后台：`pnpm build:admin`产物为`apps/admin/dist`，由Nginx等静态服务器托管。
- 官网：`pnpm build:portal`产物为`apps/portal/.output`，用`node .output/server/index.mjs`启动。
- API：`services/api/Dockerfile`或直接运行uvicorn。
- 数据库：MySQL，使用专用非root账号、持久卷及独立备份。

根目录`docker-compose.yml`只编排MySQL和API，不包含两个前端和HTTPS反向代理；`compose.dev.yml`只用于本机开发。Compose的变量来自根目录`.env`，API直接运行时读取`services/api/.env`，不要混淆。

## 必须配置

生产API设`APP_ENV=production`、`DEBUG=false`；提供唯一且至少32字节的`SECRET_KEY`、专用数据库账号和强密码，库名不可包含`test`。`CORS_ORIGINS`明确列出自己的HTTPS域名，禁止通配来源。启用AI时另行注入密钥。

管理员使用`python -m scripts.seed`创建。无人值守时从部署平台的Secret注入`INITIAL_ADMIN_PASSWORD`；重复运行不覆盖已有密码，也不提升同名普通员工权限。

## 前端代理

后台浏览器请求`/api/v1`，应由站点反向代理转发到API。官网SSR通过`NUXT_API_BASE`访问API，浏览器通过同源`/api/v1`访问Nitro代理。

**当前Nitro的routeRules代理目标在构建时读取`NUXT_API_BASE`。** 若后端地址与本机不同，应在构建和运行时都提供同一个正确地址：

```bash
NUXT_API_BASE=http://api:8000/api/v1 pnpm build:portal
# 在apps/portal中执行
NUXT_API_BASE=http://api:8000/api/v1 node .output/server/index.mjs
```

公开页面的API文档和管理后台入口分别由`NUXT_PUBLIC_API_DOCS_URL`与`NUXT_PUBLIC_ADMIN_URL`配置。

## 运行与数据

部署前执行Alembic迁移，并保留日志、数据库卷和备份卷。备份脚本需要`mysql`/`mysqldump`客户端；恢复演练需要只针对隔离演练库的相应权限。不要把清理数据快照误认为已经验证的全库备份。

当前版本的生产真实备份→隔离恢复验收仍未完成。请在自己的部署环境完成恢复、登录、基金查询、交易日期与费用核对后，再对外提供服务。
