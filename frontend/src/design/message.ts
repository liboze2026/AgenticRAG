/**
 * 学术档案 · 轻量消息提示
 * 替代 element-plus ElMessage，挂载到 body，自动消失。
 */

type Variant = 'info' | 'success' | 'warn' | 'error'

interface Options {
  text: string
  variant?: Variant
  duration?: number
}

let container: HTMLDivElement | null = null

function ensureContainer() {
  if (container) return container
  container = document.createElement('div')
  container.className = 'msg-container'
  Object.assign(container.style, {
    position: 'fixed',
    top: '24px',
    right: '24px',
    zIndex: '9999',
    display: 'flex',
    flexDirection: 'column',
    gap: '10px',
    pointerEvents: 'none',
  } as Partial<CSSStyleDeclaration>)
  document.body.appendChild(container)
  return container
}

function variantColor(v: Variant): { bg: string; bd: string; fg: string; tag: string } {
  switch (v) {
    case 'success': return { bg: '#e8f0e3', bd: '#3d7a3d', fg: '#1a3a1a', tag: '通　过' }
    case 'warn':    return { bg: '#f5ecd8', bd: '#b8742a', fg: '#5a3814', tag: '注　意' }
    case 'error':   return { bg: '#f6ecec', bd: '#a83232', fg: '#5a1818', tag: '错　误' }
    case 'info':
    default:        return { bg: '#e6ecf4', bd: '#1a365d', fg: '#0f2543', tag: '提　示' }
  }
}

export function showMessage({ text, variant = 'info', duration = 3500 }: Options) {
  const root = ensureContainer()
  const c = variantColor(variant)
  const card = document.createElement('div')

  Object.assign(card.style, {
    minWidth: '280px',
    maxWidth: '440px',
    background: c.bg,
    border: `1px solid ${c.bd}`,
    borderLeftWidth: '4px',
    color: c.fg,
    padding: '12px 18px',
    fontFamily: "'Noto Serif SC', 'Songti SC', SimSun, serif",
    fontSize: '15px',
    lineHeight: '1.6',
    boxShadow: '0 1px 0 rgba(0,0,0,.08), 0 12px 28px -10px rgba(20,20,40,.25)',
    pointerEvents: 'auto',
    opacity: '0',
    transform: 'translateY(-8px)',
    transition: 'opacity .25s, transform .25s',
    display: 'flex',
    alignItems: 'flex-start',
    gap: '12px',
  } as Partial<CSSStyleDeclaration>)

  const tag = document.createElement('span')
  Object.assign(tag.style, {
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: '11px',
    fontWeight: '700',
    letterSpacing: '0.15em',
    color: c.bd,
    border: `1px solid ${c.bd}`,
    padding: '2px 8px',
    flexShrink: '0',
    textTransform: 'uppercase',
    background: '#f7f4ed',
  } as Partial<CSSStyleDeclaration>)
  tag.textContent = c.tag

  const body = document.createElement('span')
  body.textContent = text
  body.style.flex = '1'

  card.appendChild(tag)
  card.appendChild(body)
  root.appendChild(card)

  requestAnimationFrame(() => {
    card.style.opacity = '1'
    card.style.transform = 'translateY(0)'
  })

  setTimeout(() => {
    card.style.opacity = '0'
    card.style.transform = 'translateY(-8px)'
    setTimeout(() => card.remove(), 300)
  }, duration)
}

export const msg = {
  info:    (text: string, duration?: number) => showMessage({ text, variant: 'info', duration }),
  success: (text: string, duration?: number) => showMessage({ text, variant: 'success', duration }),
  warn:    (text: string, duration?: number) => showMessage({ text, variant: 'warn', duration }),
  error:   (text: string, duration?: number) => showMessage({ text, variant: 'error', duration }),
}
