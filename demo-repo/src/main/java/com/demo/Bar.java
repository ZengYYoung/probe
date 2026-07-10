package com.demo;

/**
 * Second demo class: extends {@link Foo}, implements {@link Runnable},
 * and holds a {@link Foo} field so the class graph shows an associates
 * edge in addition to extends/implements.
 */
public class Bar extends Foo implements Runnable {

    private Foo foo;

    public Bar() {
        this.foo = new Foo();
    }

    @Override
    public void run() {
        // no-op: exists so Runnable is genuinely implemented
    }
}
