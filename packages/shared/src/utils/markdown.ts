/**
 * 极简 Markdown → HTML。
 *
 * 只支持后台实际会写的语法：标题、加粗、行内代码、段落与换行。
 * 刻意不引入完整的 Markdown 解析器：
 * - 门户是 SSR，多一个解析器就多一份首屏体积；
 * - 渲染结果会进 `v-html`，支持得越少，XSS 面越小（先整体转义再拼标签）。
 *
 * 门户详情页与后台预览共用同一份实现，避免"预览和线上长得不一样"。
 */
export function renderMarkdown(source: string | null | undefined): string {
  const text = source ?? ''
  const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

  return escaped
    .replace(/^### (.*)$/gm, '<h3>$1</h3>')
    .replace(/^## (.*)$/gm, '<h2>$1</h2>')
    .replace(/^# (.*)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .split(/\n{2,}/)
    .map((block) =>
      block.trim().startsWith('<h') ? block : `<p>${block.replace(/\n/g, '<br />')}</p>`,
    )
    .join('\n')
}
