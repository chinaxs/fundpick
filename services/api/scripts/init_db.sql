-- 仅创建空数据库，不创建带固定密码的账号。
-- 推荐新安装使用项目根目录的compose.dev.yml，由环境变量初始化专用账号。
-- 自备MySQL时，由数据库管理员创建专用账号并授予此库权限，
-- 再将真实连接信息填入services/api/.env；不要使用root运行应用。
CREATE DATABASE IF NOT EXISTS `fundpick`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;
