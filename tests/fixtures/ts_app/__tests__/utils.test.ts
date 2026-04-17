import { greet, sum } from '../src/utils';

test('greet returns greeting', () => {
  expect(greet('world')).toBe('Hello, world!');
});

test('sum adds numbers', () => {
  expect(sum([1, 2, 3])).toBe(6);
});

test('sum empty array', () => {
  expect(sum([])).toBe(0);
});
