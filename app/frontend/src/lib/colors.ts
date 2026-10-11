// Mesma regra de cor usada no GraphView e na Legend: cor estável por tipo.
const cache: Record<string, string> = {};
export function colorFor(seed: string): string {
  if (cache[seed]) return cache[seed];
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = seed.charCodeAt(i) + ((hash << 5) - hash);
  cache[seed] = `hsl(${Math.abs(hash) % 360}, 70%, 60%)`;
  return cache[seed];
}
