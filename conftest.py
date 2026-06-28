import asyncio, inspect

collect_ignore = ["data/postgres"]

def pytest_pyfunc_call(pyfuncitem):
    """Execute async test functions without pytest-asyncio plugin."""
    if inspect.iscoroutinefunction(pyfuncitem.function):
        # Run the coroutine with asyncio
        asyncio.run(pyfuncitem.function(**pyfuncitem.funcargs))
        return True
    return None
