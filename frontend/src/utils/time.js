/**
 * 后端返回的时间是 UTC，但 SQLite 不保留时区信息，
 * 序列化后的 ISO 字符串可能没有 `Z` / `+00:00` 后缀，
 * 浏览器会按本地时间解析，导致显示偏差。
 * 这里统一按 UTC 解析，再以北京时间（Asia/Shanghai）展示。
 */

const BJ_FORMATTER = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
})

function toDate(input) {
  if (input == null || input === '') return null
  if (input instanceof Date) return Number.isNaN(input.getTime()) ? null : input

  let s = String(input).trim()
  // 没有时区标识时（既没有 Z 也没有 ±HH:MM 后缀），按 UTC 处理
  const hasTz = /[zZ]$/.test(s) || /[+-]\d{2}:?\d{2}$/.test(s)
  if (!hasTz) {
    // 兼容 "YYYY-MM-DD HH:MM:SS" 这种空格分隔的形式
    s = s.replace(' ', 'T') + 'Z'
  }
  const d = new Date(s)
  return Number.isNaN(d.getTime()) ? null : d
}

/**
 * 格式化为北京时间字符串，例如：2026/04/25 16:05:30
 */
export function formatBeijingTime(input) {
  const d = toDate(input)
  if (!d) return ''
  // Intl 输出形如 "2026/04/25 16:05:30"
  return BJ_FORMATTER.format(d).replace(/\//g, '-')
}
