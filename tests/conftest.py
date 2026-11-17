"""Không nạp bí mật từ tệp môi trường khi chạy kiểm thử."""

import os

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
