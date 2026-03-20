"""
Standardized JSON response builder for all MCP tools.
"""


def success_response(tool_name, inputs, summary, timeseries=None, metadata=None):
    return {
        "tool": tool_name,
        "inputs": inputs,
        "result": {
            "summary": summary,
            "timeseries": timeseries or [],
            "metadata": metadata or {},
        },
        "status": "ok",
        "errors": [],  # No errors
    }


def error_response(tool_name, inputs, error_msg):
    return {
        "tool": tool_name,
        "inputs": inputs,
        "result": None,
        "status": "error",
        "errors": [error_msg],
    }
