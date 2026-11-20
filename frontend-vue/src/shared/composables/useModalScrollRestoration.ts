import { onBeforeUnmount, onMounted } from 'vue'

// Preserve the background page while opening/closing cards and other dialogs.
// This is independent of the individual page components, so a modal can
// refresh its table without unexpectedly moving the user's viewport.
const modalSelector = [
  '.modal-backdrop',
  '.reference-manager-backdrop',
  '.task-modal-backdrop',
  '.task-delete-confirm-backdrop',
  '.p-dialog-mask',
  '.p-drawer-mask',
  '[role="dialog"][aria-modal="true"]',
  '[role="alertdialog"][aria-modal="true"]',
].join(', ')

type ScrolledElement = {
  element: HTMLElement
  top: number
  left: number
}

type ScrollSnapshot = {
  pathname: string
  top: number
  left: number
  elements: ScrolledElement[]
}

type InteractionSnapshot = {
  time: number
  scroll: ScrollSnapshot
}

function isModalOpen(): boolean {
  if (document.body.classList.contains('modal-open')) return true
  return Array.from(document.querySelectorAll<HTMLElement>(modalSelector)).some(
    (element) => element.getClientRects().length > 0,
  )
}

function isBackgroundElement(element: HTMLElement): boolean {
  return !element.closest(modalSelector)
}

function readScrollPosition(element: HTMLElement): ScrolledElement | null {
  if (!element.isConnected || !isBackgroundElement(element)) return null
  const { scrollTop, scrollLeft } = element
  return scrollTop !== 0 || scrollLeft !== 0
    ? { element, top: scrollTop, left: scrollLeft }
    : null
}

function captureScroll(): ScrollSnapshot {
  // Only scan all elements when a dialog actually opens; this catches nested
  // scrollable lists as well as horizontally-scrolled tables on every page.
  const elements: ScrolledElement[] = []
  for (const element of document.querySelectorAll('*')) {
    if (!(element instanceof HTMLElement)) continue
    const position = readScrollPosition(element)
    if (position) elements.push(position)
  }
  return {
    pathname: window.location.pathname,
    top: window.scrollY,
    left: window.scrollX,
    elements,
  }
}

function captureInteraction(target: EventTarget | null): ScrollSnapshot {
  const elements: ScrolledElement[] = []
  let current = target instanceof Element ? target : null
  // A click on a row can trigger the body's scroll lock before the modal is
  // inserted. Record the viewport and the row's scrollable ancestors first.
  while (current) {
    if (current instanceof HTMLElement) {
      const position = readScrollPosition(current)
      if (position) elements.push(position)
    }
    current = current.parentElement
  }
  return {
    pathname: window.location.pathname,
    top: window.scrollY,
    left: window.scrollX,
    elements,
  }
}

function restoreScroll(snapshot: ScrollSnapshot): void {
  if (snapshot.pathname !== window.location.pathname) return
  for (const { element, top, left } of snapshot.elements) {
    if (!element.isConnected) continue
    element.scrollTo({ top, left, behavior: 'instant' })
  }
  window.scrollTo({ top: snapshot.top, left: snapshot.left, behavior: 'instant' })
}

export function useModalScrollRestoration(): void {
  let observer: MutationObserver | null = null
  let bodyObserver: MutationObserver | null = null
  let modalOpen = false
  let snapshot: ScrollSnapshot | null = null
  let interaction: InteractionSnapshot | null = null
  let restoreFrame = 0

  function rememberInteraction(event: Event): void {
    if (modalOpen || isModalOpen()) return
    interaction = { time: performance.now(), scroll: captureInteraction(event.target) }
  }

  function rememberKeyboardInteraction(event: KeyboardEvent): void {
    if (event.key === 'Enter' || event.key === ' ') rememberInteraction(event)
  }

  function onBackgroundScroll(): void {
    // A subsequent manual scroll invalidates the pre-click position.
    if (!modalOpen && !isModalOpen()) interaction = null
  }

  function updateModalState(): void {
    const nextOpen = isModalOpen()
    if (nextOpen === modalOpen) return
    modalOpen = nextOpen

    if (nextOpen) {
      if (restoreFrame) window.cancelAnimationFrame(restoreFrame)
      restoreFrame = 0
      snapshot = captureScroll()
      if (interaction && performance.now() - interaction.time < 5000 && interaction.scroll.pathname === snapshot.pathname) {
        snapshot.top = interaction.scroll.top
        snapshot.left = interaction.scroll.left
        const existing = new Set(snapshot.elements.map(({ element }) => element))
        for (const position of interaction.scroll.elements) {
          if (existing.has(position.element)) {
            const current = snapshot.elements.find(({ element }) => element === position.element)
            if (current) { current.top = position.top; current.left = position.left }
          } else {
            snapshot.elements.push(position)
          }
        }
      }
      interaction = null
      return
    }

    const toRestore = snapshot
    snapshot = null
    interaction = null
    if (toRestore && toRestore.pathname === window.location.pathname) {
      // The closing v-if and any table updates must settle before restoring.
      restoreFrame = window.requestAnimationFrame(() => {
        restoreFrame = 0
        if (!isModalOpen()) restoreScroll(toRestore)
      })
    }
  }

  onMounted(() => {
    modalOpen = isModalOpen()
    observer = new MutationObserver(updateModalState)
    observer.observe(document.body, { childList: true, subtree: true })
    bodyObserver = new MutationObserver(updateModalState)
    bodyObserver.observe(document.body, { attributes: true, attributeFilter: ['class'] })
    document.addEventListener('pointerdown', rememberInteraction, true)
    document.addEventListener('keydown', rememberKeyboardInteraction, true)
    document.addEventListener('scroll', onBackgroundScroll, true)
  })

  onBeforeUnmount(() => {
    observer?.disconnect()
    bodyObserver?.disconnect()
    document.removeEventListener('pointerdown', rememberInteraction, true)
    document.removeEventListener('keydown', rememberKeyboardInteraction, true)
    document.removeEventListener('scroll', onBackgroundScroll, true)
    if (restoreFrame) window.cancelAnimationFrame(restoreFrame)
  })
}
