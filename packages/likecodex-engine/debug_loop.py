"""Debug script for AgentLoop refactoring."""
import asyncio
import tempfile
from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.tools.registry import ToolRegistry


async def test():
    with tempfile.TemporaryDirectory() as tmp:
        tools = ToolRegistry(str(tmp))
        context = ContextManager()
        llm = MockProvider.for_hello_world()
        loop = AgentLoop(
            llm, tools, context,
            permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
        )
        outputs = []
        async for resp in loop.run("create hello.py and run it"):
            outputs.append(resp)
        for i, o in enumerate(outputs):
            c = (o.content or "")[:60]
            print(f"Event[{i}]: type={o.event_type} content={c!r}")
            if o.tool_calls:
                for tc in o.tool_calls:
                    print(f"  Tool: {tc.name}")
        print(f"\nTotal outputs: {len(outputs)}")
        last = outputs[-1]
        print(f"Last: type={last.event_type}, content={last.content!r}")
        hello = tmp / "hello.py"
        print(f"hello.py exists: {hello.exists()}")


asyncio.run(test())
"""Debug script for AgentLoop refactoring."""
import asyncio
import tempfile
from likecodex_engine.agent.loop import AgentLoop
from likecodex_engine.context.manager import ContextManager
from likecodex_engine.llm.mock import MockProvider
from likecodex_engine.permissions.evaluator import ApprovalMode, PermissionEvaluator
from likecodex_engine.tools.registry import ToolRegistry


async def test():
    with tempfile.TemporaryDirectory() as tmp:
        tools = ToolRegistry(str(tmp))
        context = ContextManager()
        llm = MockProvider.for_hello_world()
        loop = AgentLoop(
            llm, tools, context,
            permission_evaluator=PermissionEvaluator(ApprovalMode.FULL_ACCESS),
        )
        outputs = []
        async for resp in loop.run("create hello.py and run it"):
            outputs.append(resp)
        for i, o in enumerate(outputs):
            c = (o.content or "")[:60]
            print(f"Event[{i}]: type={o.event_type} content={c!r}")
            if o.tool_calls:
                for tc in o.tool_calls:
                    print(f"  Tool: {tc.name}")
        print(f"\nTotal outputs: {len(outputs)}")
        last = outputs[-1]
        print(f"Last: type={last.event_type}, content={last.content!r}")
        hello = tmp / "hello.py"
        print(f"hello.py exists: {hello.exists()}")


asyncio.run(test())
