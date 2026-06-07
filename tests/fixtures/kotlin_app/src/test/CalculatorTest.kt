import org.junit.Test
import org.junit.Assert.assertEquals

class CalculatorTest {
    @Test
    fun addsNumbers() {
        assertEquals(3, Calculator().add(1, 2))
    }

    @Test
    fun subtractsNumbers() {
        assertEquals(3, Calculator().sub(5, 2))
    }
}
