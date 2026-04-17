export function greet(name: string): string {
  return `Hello, ${name}!`;
}

export function sum(nums: number[]): number {
  return nums.reduce((a, b) => a + b, 0);
}
