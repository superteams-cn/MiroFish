"""核心横切层：配置、数据库、安全、日志、错误信封、依赖。

依赖方向单向：api → services → repositories → models，横切的 core 谁都可用。
本包只放与具体业务无关的基础设施。
"""
