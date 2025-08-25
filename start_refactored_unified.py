#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
簡化啟動器：統一入口指向 app_refactored_unified:app
"""

import os
import sys


def main():
    import uvicorn

    host = os.getenv("FASTAPI_HOST", "0.0.0.0")
    port = int(os.getenv("PORT", os.getenv("FASTAPI_PORT", 8000)))

    uvicorn.run(
        "app_refactored_unified:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    sys.exit(main())
