import XCTest

final class CalculatorTests: XCTestCase {
    func testAdd() {
        XCTAssertEqual(Calculator().add(1, 2), 3)
    }
    func testSub() {
        XCTAssertEqual(Calculator().sub(5, 2), 3)
    }
}
