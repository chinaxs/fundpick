/** CSV 导出：纯前端生成，避免为导出单独开接口。
 *
 * 限制：导出的是当前列表页数据（与服务端所见一致），超大数据量导出
 * 属于数据仓库需求，不在后台管理端做。
 */

interface ExportColumn<Row> {
  /** CSV 表头 */
  header: string
  /** 取值：返回 string | number | null */
  value: (row: Row) => string | number | null
}

/** 转义单元格：含分隔符 / 引号 / 换行的值加引号包裹 */
function escapeCell(value: string | number | null): string {
  if (value === null || value === undefined) return ''
  const text = String(value)
  if (/[",\n\r]/.test(text)) {
    return `"${text.replaceAll('"', '""')}"`
  }
  return text
}

/** Excel 打开 CSV 乱码是经典问题：加 UTF-8 BOM */
function toCsvBlob<Row>(rows: Row[], columns: ExportColumn<Row>[]): Blob {
  const lines = [columns.map((c) => escapeCell(c.header)).join(',')]
  for (const row of rows) {
    lines.push(columns.map((c) => escapeCell(c.value(row))).join(','))
  }
  return new Blob(['\uFEFF' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' })
}

/** 触发浏览器下载。 */
export function exportCsv<Row>(filename: string, rows: Row[], columns: ExportColumn<Row>[]): void {
  const blob = toCsvBlob(rows, columns)
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename.endsWith('.csv') ? filename : `${filename}.csv`
  link.click()
  URL.revokeObjectURL(url)
}

/** 文件名统一加时间戳，避免同名文件覆盖且方便归档 */
export function csvFilename(prefix: string): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${prefix}-${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}${pad(
    now.getHours(),
  )}${pad(now.getMinutes())}.csv`
}
