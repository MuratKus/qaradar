package math

import "testing"

func TestAdd(t *testing.T) {
	if Add(1, 2) != 3 {
		t.Fail()
	}
}

func TestSubtract(t *testing.T) {
	if Subtract(5, 3) != 2 {
		t.Fail()
	}
}
