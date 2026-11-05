-- 建库 + 建专用账号（用 root 执行一次）
-- 用法：/usr/local/mysql/bin/mysql -u root -p < scripts/init_db.sql

CREATE DATABASE IF NOT EXISTS `test_study`
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

-- 应用账号：只授权 test_study 库，避免应用用 root 连库
CREATE USER IF NOT EXISTS 'study_app'@'localhost' IDENTIFIED BY 'study_app_123456';
CREATE USER IF NOT EXISTS 'study_app'@'127.0.0.1' IDENTIFIED BY 'study_app_123456';

GRANT ALL PRIVILEGES ON `test_study`.* TO 'study_app'@'localhost';
GRANT ALL PRIVILEGES ON `test_study`.* TO 'study_app'@'127.0.0.1';

FLUSH PRIVILEGES;
