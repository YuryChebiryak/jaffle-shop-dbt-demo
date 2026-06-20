import asyncio
import json
import shlex

from dbt_mcp.config.config import load_config
from dbt_mcp.mcp.server import create_dbt_mcp


async def main():
    config = load_config()
    dbt_mcp = await create_dbt_mcp(config)

    # List available tools
    tools = await dbt_mcp.list_tools()
    print("Available tools:")
    for tool in tools:
        params = ", ".join(tool.inputSchema.get("properties", {}).keys())
        print(f"  - {tool.name}({params})")
    print()

    print("Enter tool calls in the format: tool_name arg1=value arg2=value")
    print("Type 'exit' or 'quit' to exit.")
    print()

    while True:
        try:
            user_input = input("dbt > ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                break

            # Parse input: tool_name arg1=value arg2=value
            parts = shlex.split(user_input)
            if not parts:
                continue
            tool_name = parts[0]
            args_str = " ".join(parts[1:])

            # Parse arguments as key=value pairs
            args = {}
            if args_str:
                for arg in shlex.split(args_str):
                    if "=" in arg:
                        key, value = arg.split("=", 1)
                        # Try to parse as JSON, otherwise keep as string
                        try:
                            args[key] = json.loads(value)
                        except json.JSONDecodeError:
                            args[key] = value
                    else:
                        print(f"Invalid argument format: {arg}. Use key=value")
                        continue

            print(f"Calling {tool_name} with {args}")
            result = await dbt_mcp.call_tool(tool_name, args)
            print("Result:")
            for content in result:
                if hasattr(content, 'text'):
                    print(content.text)
                else:
                    print(content)
            print()

        except KeyboardInterrupt:
            print("\nExiting.")
            break
        except Exception as e:
            print(f"Error: {e}")
            print()


if __name__ == "__main__":
    asyncio.run(main())
