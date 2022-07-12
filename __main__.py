#!/usr/local/bin/python
# -*- coding: UTF-8 -*-
"""
Python 3.7
"""

import uvicorn

from config import settings


if __name__ == '__main__':
    uvicorn.run(
        'main:app',
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=True
    )
