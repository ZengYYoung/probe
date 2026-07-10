package com.demo.service;

import com.demo.Foo;
import com.demo.model.Model;

/** Service 层：依赖 com.demo.Foo 与 com.demo.model.Model，形成跨包依赖。 */
public class Service {
    private Foo foo;
    private Model model;

    public Service(Foo foo, Model model) {
        this.foo = foo;
        this.model = model;
    }

    public int compute() {
        return foo.add(1, model.getName().length());
    }
}
