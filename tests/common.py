import asynctest

async_noop = asynctest.CoroutineMock(return_value=None)
async_raises = asynctest.CoroutineMock(side_effect=Exception)
