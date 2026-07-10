package com.demo;

import org.junit.Test;
import static org.junit.Assert.assertEquals;

/**
 * Passing test: Foo.add(1,2) == 3.
 */
public class FooTest {

    @Test
    public void addReturnsSum() {
        assertEquals(3, new Foo().add(1, 2));
    }
}
