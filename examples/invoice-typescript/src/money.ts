export function totalCents(prices: number[]): number {
  return prices.reduce((sum, amount) => sum + Math.round(amount), 0);
}
