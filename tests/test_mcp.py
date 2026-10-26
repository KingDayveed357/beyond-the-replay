import asyncio
import json
import sys
import unittest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def _session_calls():
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server"], cwd=".")
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = [t.name for t in (await s.list_tools()).tools]
            matches = json.loads((await s.call_tool("list_matches", {})).content[0].text)
            mid = matches["match_id"] if isinstance(matches, dict) else matches[0]["match_id"]
            state = json.loads((await s.call_tool("match_state", {"match_id": mid, "minute": 45})).content[0].text)
            bad = await s.call_tool("key_moments", {"match_id": mid, "lang": "xx"})
            return tools, state, bad


class McpServerTests(unittest.TestCase):
    def test_tools_answer_over_stdio(self):
        tools, state, bad = asyncio.run(_session_calls())
        self.assertEqual(set(tools), {"list_matches", "match_state", "key_moments", "player_summary", "why_goal", "overlay_track"})
        self.assertEqual(state["minute"], 45)
        self.assertEqual(len(state["teams"]), 2)
        self.assertTrue(bad.is_error)


if __name__ == "__main__":
    unittest.main()
