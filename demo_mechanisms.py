"""A.6 机制演示 CLI 入口（shim）。

实际实现已迁入 probe.demo，本文件保留以兼容 `import demo_mechanisms`
与 `python demo_mechanisms.py` 两种用法。
"""
from probe.demo import (  # noqa: F401
    demo_feedback_loop,
    demo_guardrail,
    demo_no_progress,
)

if __name__ == "__main__":
    print("=== demo_guardrail ===")
    print(demo_guardrail())
    print()
    print("=== demo_feedback_loop ===")
    for line in demo_feedback_loop():
        print(line)
    print()
    print("=== demo_no_progress ===")
    print(demo_no_progress())
