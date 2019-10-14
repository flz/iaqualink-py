import asynctest

async_noop = asynctest.CoroutineMock(return_value=None)
async_raises = lambda x=Exception: asynctest.CoroutineMock(side_effect=x)
