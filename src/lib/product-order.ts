/** Negative display orders are pinned; the newest pin appears first. */
export function isProductPinned(order: number): boolean {
  return order < 0;
}

export function nextProductOrder(orders: number[], pin: boolean): number {
  return pin ? Math.min(0, ...orders) - 1 : Math.max(0, ...orders) + 1;
}
