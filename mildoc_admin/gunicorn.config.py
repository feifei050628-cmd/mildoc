import os
from dotenv import load_dotenv
load_dotenv()

bind = os.getenv('FLASK_HOST', '0.0.0.0') + ":" + os.getenv('FLASK_PORT', '8870')
worker_class = "gthread"   # 线程模式
workers = 2                # 至少 2 个进程，一个卡住另一个还能服务
threads = 4                # 每个 worker 4 个线程，并发能力 = 8
keepalive = 5