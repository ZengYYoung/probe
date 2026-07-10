package com.demo.model;

/** 一个简单模型类，被 service 层使用。 */
public class Model {
    private String name;

    public Model(String name) {
        this.name = name;
    }

    public String getName() {
        return name;
    }
}
