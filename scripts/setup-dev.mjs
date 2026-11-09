/** Generate local development configuration without overwriting existing files. */
import { randomBytes } from 'node:crypto'
import { access, readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const root = fileURLToPath(new URL('../', import.meta.url))
const destinations = [resolve(root, '.env'), resolve(root, 'services/api/.env')]
const exists = async (path) =>
  access(path).then(
    () => true,
    () => false,
  )
if ((await Promise.all(destinations.map(exists))).some(Boolean)) {
  console.error(
    '本地配置已经存在，未修改任何文件。首次安装请在干净目录运行；已有环境按README手动配置。',
  )
  process.exitCode = 1
} else {
  const password = randomBytes(32).toString('hex')
  const secret = randomBytes(48).toString('hex')
  const values = {
    MYSQL_HOST: '127.0.0.1',
    MYSQL_PORT: '3307',
    MYSQL_USER: 'fundpick_app',
    MYSQL_PASSWORD: password,
    MYSQL_DB: 'fundpick',
    SECRET_KEY: secret,
  }
  let api = await readFile(resolve(root, 'services/api/.env.example'), 'utf8')
  for (const [key, value] of Object.entries(values))
    api = api.replace(new RegExp(`^${key}=.*$`, 'm'), `${key}=${value}`)
  const compose = [
    '# Local development only. Generated secrets; do not commit.',
    `MYSQL_ROOT_PASSWORD=${randomBytes(32).toString('hex')}`,
    ...Object.entries(values)
      .filter(([key]) => key !== 'MYSQL_HOST')
      .map(([key, value]) => `${key}=${value}`),
    'CORS_ORIGINS=http://localhost:5174,http://localhost:3000',
    '',
  ].join('\n')
  await writeFile(destinations[0], compose, { flag: 'wx', mode: 0o600 })
  try {
    await writeFile(destinations[1], api, { flag: 'wx', mode: 0o600 })
  } catch (error) {
    console.error('根目录.env已生成，但后端配置写入失败；请检查文件状态后继续。')
    throw error
  }
  console.log(
    '已生成根目录.env和services/api/.env，密钥未输出。下一步：docker compose -f compose.dev.yml up -d --wait',
  )
}
