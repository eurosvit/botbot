"""Тести silpo_agent без мережі: транспорт MCP і агентний цикл на моках."""

import json
import os
import tempfile
import unittest
from unittest import mock

from app.silpo_agent.mcp_client import MCPError, SilpoMCPClient
from app.silpo_agent.agent import (
    DECLINED_RESULT,
    READ_ONLY_RESULT,
    SilpoAgent,
    mcp_tools_to_anthropic,
)
from app.silpo_agent.guardrails import is_write_tool
from app.silpo_agent.preferences import UserPrefs


def fake_response(payload=None, *, sse=False, status=200, headers=None):
    resp = mock.Mock()
    resp.status_code = status
    resp.headers = headers or {}
    if sse:
        resp.headers.setdefault("Content-Type", "text/event-stream")
        body = "event: message\ndata: " + json.dumps(payload) + "\n\n"
        resp.text = body
        resp.content = body.encode()
    elif payload is not None:
        resp.headers.setdefault("Content-Type", "application/json")
        resp.json.return_value = payload
        resp.content = json.dumps(payload).encode()
    else:
        resp.content = b""
    resp.raise_for_status = mock.Mock()
    return resp


TOOLS = [{
    "name": "searchProducts",
    "description": "Пошук товарів Сільпо",
    "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
}]


def make_client(responses):
    client = SilpoMCPClient(endpoint="https://mcp.silpo.ua/mcp", token="test-token")
    client._http = mock.Mock()
    client._http.post = mock.Mock(side_effect=responses)
    return client


def init_responses():
    return [
        fake_response({"jsonrpc": "2.0", "id": 1,
                       "result": {"serverInfo": {"name": "silpo"}}},
                      headers={"Mcp-Session-Id": "sess-1"}),
        fake_response(None, status=202),  # notifications/initialized
    ]


class TestMCPClient(unittest.TestCase):
    def test_list_tools_json(self):
        client = make_client(init_responses() + [
            fake_response({"jsonrpc": "2.0", "id": 2, "result": {"tools": TOOLS}}),
        ])
        tools = client.list_tools()
        self.assertEqual(tools[0]["name"], "searchProducts")
        # Сесія з initialize має підхопитись у заголовки наступних запитів
        self.assertEqual(client.session_id, "sess-1")
        headers = client._http.post.call_args.kwargs["headers"]
        self.assertEqual(headers["Mcp-Session-Id"], "sess-1")
        self.assertEqual(headers["Authorization"], "Bearer test-token")

    def test_call_tool_sse(self):
        client = make_client(init_responses() + [
            fake_response({"jsonrpc": "2.0", "id": 2, "result": {
                "content": [{"type": "text", "text": "Борщовий набір — 129 грн"}]
            }}, sse=True),
        ])
        result = client.call_tool("searchProducts", {"query": "борщ"})
        self.assertIn("129 грн", result)

    def test_jsonrpc_error_raises(self):
        client = make_client(init_responses() + [
            fake_response({"jsonrpc": "2.0", "id": 2,
                           "error": {"code": -32602, "message": "bad params"}}),
        ])
        with self.assertRaises(MCPError):
            client.call_tool("searchProducts", {})

    def test_auth_error_message(self):
        client = make_client([fake_response(None, status=401)])
        with self.assertRaises(MCPError) as ctx:
            client.initialize()
        self.assertIn("SILPO_MCP_TOKEN", str(ctx.exception))


class TestGuardrails(unittest.TestCase):
    def test_read_tools(self):
        for name in ("searchProducts", "getCart", "listStores", "batchSearch",
                     "findNovaPoshtaBranch", "suggestSubstitutes",
                     "checkDeliverySlots", "getLoyaltyBalance"):
            self.assertFalse(is_write_tool(name), name)

    def test_write_tools(self):
        for name in ("addToCart", "removeFromCart", "updateDelivery",
                     "applyPromoCode", "redeemBonuses", "setAddress",
                     "createOrder", "checkout", "clearCart"):
            self.assertTrue(is_write_tool(name), name)

    def test_unknown_verb_is_conservative(self):
        # Невідоме перше дієслово -> вважаємо write
        self.assertTrue(is_write_tool("zpakuvatyKoshyk"))


class TestPreferences(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(self.path)

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_roundtrip(self):
        prefs = UserPrefs(path=self.path)
        prefs.watch("Сир козиний")
        prefs.ban_brand("БрендХ")
        prefs.data["hide_np_only"] = True
        prefs.save()

        reloaded = UserPrefs(path=self.path)
        self.assertEqual(reloaded.data["watchlist"], ["Сир козиний"])
        self.assertEqual(reloaded.data["banned_brands"], ["БрендХ"])
        self.assertTrue(reloaded.data["hide_np_only"])

    def test_render_for_prompt(self):
        prefs = UserPrefs(path=self.path)
        prefs.ban_brand("БрендХ")
        prefs.data["hide_np_only"] = True
        block = prefs.render_for_prompt()
        self.assertIn("БрендХ", block)
        self.assertIn("Новою Поштою", block)

    def test_empty_prefs_render_empty(self):
        self.assertEqual(UserPrefs(path=self.path).render_for_prompt(), "")

    def test_prefs_injected_into_agent_system(self):
        prefs = UserPrefs(path=self.path)
        prefs.ban_brand("БрендХ")
        agent = SilpoAgent(mcp_client=mock.Mock(), anthropic_client=mock.Mock(),
                           prefs=prefs)
        self.assertIn("БрендХ", agent.system)


class TestToolConversion(unittest.TestCase):
    def test_converts_schema(self):
        converted = mcp_tools_to_anthropic(TOOLS)
        self.assertEqual(converted[0]["name"], "searchProducts")
        self.assertIn("query", converted[0]["input_schema"]["properties"])


def text_block(text):
    block = mock.Mock()
    block.type = "text"
    block.text = text
    return block


def tool_use_block(name, tool_input, block_id="tu_1"):
    block = mock.Mock()
    block.type = "tool_use"
    block.name = name
    block.input = tool_input
    block.id = block_id
    return block


class TestAgentLoop(unittest.TestCase):
    def test_tool_use_then_answer(self):
        mcp = mock.Mock()
        mcp.list_tools.return_value = TOOLS
        mcp.call_tool.return_value = "Буряк 12 грн/кг"

        first = mock.Mock(stop_reason="tool_use",
                          content=[tool_use_block("searchProducts", {"query": "буряк"})])
        final = mock.Mock(stop_reason="end_turn",
                          content=[text_block("Ваш кошик: буряк, 12 грн")])
        llm = mock.Mock()
        llm.beta.messages.create.side_effect = [first, final]

        agent = SilpoAgent(mcp_client=mcp, anthropic_client=llm)
        answer = agent.run("Купи буряк")

        self.assertIn("кошик", answer)
        mcp.call_tool.assert_called_once_with("searchProducts", {"query": "буряк"})
        # У другому запиті має бути tool_result із правильним id
        second_call_messages = llm.beta.messages.create.call_args.kwargs["messages"]
        tool_result = second_call_messages[-1]["content"][0]
        self.assertEqual(tool_result["type"], "tool_result")
        self.assertEqual(tool_result["tool_use_id"], "tu_1")

    def test_write_tool_declined_not_executed(self):
        mcp = mock.Mock()
        mcp.list_tools.return_value = TOOLS + [{
            "name": "addToCart", "description": "Додає товар у кошик",
            "inputSchema": {"type": "object", "properties": {}},
        }]
        first = mock.Mock(stop_reason="tool_use",
                          content=[tool_use_block("addToCart", {"id": 1})])
        final = mock.Mock(stop_reason="end_turn", content=[text_block("Ок")])
        llm = mock.Mock()
        llm.beta.messages.create.side_effect = [first, final]

        agent = SilpoAgent(mcp_client=mcp, anthropic_client=llm,
                           confirm_write=lambda name, args: False)
        agent.run("Додай у кошик")

        mcp.call_tool.assert_not_called()
        messages = llm.beta.messages.create.call_args.kwargs["messages"]
        self.assertEqual(messages[-1]["content"][0]["content"], DECLINED_RESULT)
        self.assertFalse(agent.audit.entries[-1]["allowed"])

    def test_read_only_blocks_write(self):
        mcp = mock.Mock()
        mcp.list_tools.return_value = TOOLS
        first = mock.Mock(stop_reason="tool_use",
                          content=[tool_use_block("applyPromoCode", {"code": "X"})])
        final = mock.Mock(stop_reason="end_turn", content=[text_block("Ок")])
        llm = mock.Mock()
        llm.beta.messages.create.side_effect = [first, final]

        agent = SilpoAgent(mcp_client=mcp, anthropic_client=llm, read_only=True)
        agent.run("Застосуй промокод")

        mcp.call_tool.assert_not_called()
        messages = llm.beta.messages.create.call_args.kwargs["messages"]
        result = messages[-1]["content"][0]
        self.assertEqual(result["content"], READ_ONLY_RESULT)
        self.assertTrue(result["is_error"])

    def test_refusal_handled(self):
        mcp = mock.Mock()
        mcp.list_tools.return_value = TOOLS
        llm = mock.Mock()
        llm.beta.messages.create.return_value = mock.Mock(
            stop_reason="refusal", content=[]
        )
        agent = SilpoAgent(mcp_client=mcp, anthropic_client=llm)
        answer = agent.run("тест")
        self.assertIn("відхилено", answer)


if __name__ == "__main__":
    unittest.main()
