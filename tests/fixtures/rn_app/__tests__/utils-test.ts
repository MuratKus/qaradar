import { greet, shout } from '../src/utils';

test('greets', () => {
  expect(greet('Ada')).toBe('Hello, Ada');
});

it('shouts', () => {
  expect(shout('Ada')).toBe('HELLO, ADA');
});
