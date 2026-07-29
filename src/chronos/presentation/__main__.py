"""Run the local certified presentation API."""

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "chronos.presentation.api:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )
