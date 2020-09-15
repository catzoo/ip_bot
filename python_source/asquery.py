"""
Made by catzoo

This is a very basic class that uses loop.run_in_executor
to make Query awaitable
"""

import asyncio
from .query import Query


class Aquery:
    def __init__(self, *args, **kwargs):
        self.query = Query(*args, **kwargs)
        self.loop = asyncio.get_event_loop()

    async def info(self):
        return await self.loop.run_in_executor(None, self.query.info)

    async def rules(self):
        return await self.loop.run_in_executor(None, self.query.rules)

    async def players(self):
        return await self.loop.run_in_executor(None, self.query.players)
