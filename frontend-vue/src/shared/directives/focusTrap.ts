import type { Directive } from 'vue'

const focusableSelector = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

const cleanupByElement = new WeakMap<HTMLElement, () => void>()

export const focusTrap: Directive<HTMLElement> = {
  mounted(element) {
    const previouslyFocused = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null

    const getFocusable = () => Array.from(
      element.querySelectorAll<HTMLElement>(focusableSelector),
    ).filter((item) => (
      item.offsetParent !== null
      && item.getAttribute('aria-hidden') !== 'true'
    ))

    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') {
        return
      }

      const focusable = getFocusable()
      if (focusable.length === 0) {
        event.preventDefault()
        return
      }

      const first = focusable[0]
      const last = focusable[focusable.length - 1]

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }

    element.addEventListener('keydown', handleKeydown)

    const animationFrame = window.requestAnimationFrame(() => {
      const preferred = element.querySelector<HTMLElement>('[autofocus]')
      const target = preferred && !preferred.hasAttribute('disabled')
        ? preferred
        : getFocusable()[0]
      target?.focus()
    })

    cleanupByElement.set(element, () => {
      window.cancelAnimationFrame(animationFrame)
      element.removeEventListener('keydown', handleKeydown)
      previouslyFocused?.focus()
    })
  },
  unmounted(element) {
    cleanupByElement.get(element)?.()
    cleanupByElement.delete(element)
  },
}
