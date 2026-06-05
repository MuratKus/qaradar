import { add, mul } from '../math';

describe('math', () => {
  test('add', () => {
    expect(add(1, 2)).toBe(3);
  });
  test('mul', () => {
    expect(mul(2, 3)).toBe(6);
  });
});
