import { useEffect, useRef, useState } from 'react'

/** Rendered width of an element in CSS pixels, kept current with a ResizeObserver (0 until first measured). */
export function useWidth<T extends Element>() {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  return [ref, width] as const
}
