"""模拟运行器的协作单元（从 SimulationRunner God 类逐步拆出）。

- process_control：无状态进程工具（PID 探活/启动时刻/杀进程组/simulation_end 检测）。
SimulationRunner 作为门面委托这些单元，集成测试 tests/test_simulation_runner.py 守护。
"""
