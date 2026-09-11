from fastmcp import FastMCP
import random

mcp = FastMCP("Demo Remote MCP Server")


@mcp.tool
def add_numbers(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


@mcp.tool
def random_number(min_value: int, max_value: int) -> int:
    """Generate a random integer within a specified range."""

    if min_value > max_value:
        raise ValueError("min_value must be less than or equal to max_value")

    return random.randint(min_value, max_value)


if __name__ == "__main__":
    mcp.run(
        transport="http",
        host="0.0.0.0",
        port=8000,
    )