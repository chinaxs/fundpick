"""进程级运行时信息。

放在 core 而不是 main：service 层需要读取启动时间，
直接 import main 会造成循环依赖。
"""

from datetime import datetime

# 进程启动时刻（模块首次被导入时）
STARTED_AT: datetime = datetime.now()
