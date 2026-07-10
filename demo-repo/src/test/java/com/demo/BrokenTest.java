package com.demo;

import org.junit.Test;
import static org.junit.Assert.assertEquals;

/**
 * Intentionally BROKEN test for the self-correction / feasibility demo.
 *
 * <p>Foo.add(1,2) returns 3, but this asserts 99, so surefire reports a
 * failure: "expected:&lt;99&gt; but was:&lt;3&gt;". Probe's TestValidator
 * parses the surefire XML and feeds the failure into the self-correction
 * pipeline. Do NOT "fix" this assertion — the failure is the point.
 */
public class BrokenTest {

    @Test
    public void broken() {
        assertEquals(99, new Foo().add(1, 2));
    }
}
