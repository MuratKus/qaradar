#import <XCTest/XCTest.h>
#import "Calculator.h"

@interface CalculatorTests : XCTestCase
@end

@implementation CalculatorTests
- (void)testAdd {
    XCTAssertEqual([[Calculator new] add:1 to:2], 3);
}
- (void)testSub {
    XCTAssertEqual([[Calculator new] sub:5 by:2], 3);
}
@end
