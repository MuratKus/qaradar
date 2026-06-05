import 'package:test/test.dart';
import '../lib/calculator.dart';

void main() {
  test('adds', () {
    expect(Calculator().add(1, 2), 3);
  });
  test('subtracts', () {
    expect(Calculator().sub(5, 2), 3);
  });
}
