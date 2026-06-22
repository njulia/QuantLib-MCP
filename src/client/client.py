"""基于 MCP 协议实现的文本计数智能助手

这个模块提供了一个智能文本计数助手，可以：
1. 通过自然语言进行文本分析
2. 支持多种交互方式（GUI、TUI、测试模式）
3. 通过 MCP 协议调用文本计数服务
"""

import asyncio
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# ====== System Prompt ======
system_prompt = ('You are an expert quantitative finance assistant equipped with an MCP connection to QuantLib, '  
                 'a premier library for modeling, pricing, and risk management of financial instruments. '
                 'Your role is to help users analyze derivatives, fixed-income assets, interest rate curves, '
                 'and structured products by translating their queries into exact QuantLib calculations.')
prompt_dir = Path("prompts")

# SYSTEM_PROMPT = "\n\n".join([
#     (prompt_dir / "system.md").read_text(encoding="utf-8"),
#     (prompt_dir / "workflow.md").read_text(),
#     (prompt_dir / "pricing.md").read_text(),
#     (prompt_dir / "coding.md").read_text(),
#     (prompt_dir / "documentation.md").read_text(),
#     (prompt_dir / "risk.md").read_text(),
# ])


# ====== MCP 客户端核心逻辑 ======
class MCPClient:
    """MCP client"""
    
    def __init__(self, server_script_path: str):
        self.server_script_path = server_script_path
        self.session = None
        self.tools = []
    
    async def connect(self):
        """Connect to the MCP server"""
        server_params = StdioServerParameters(
            command="python",
            args=[self.server_script_path],
        )
        
        self.stdio_transport = stdio_client(server_params)
        read, write = await self.stdio_transport.__aenter__()
        self.session = ClientSession(read, write)
        await self.session.__aenter__()
        
        # 初始化并获取可用工具
        await self.session.initialize()
        tools_response = await self.session.list_tools()
        self.tools = tools_response.tools
        
        print(f"Connected to the MCP server with tools: {[t.name for t in self.tools]}")
    
    async def call_tool(self, tool_name: str, arguments: dict = None):
        """Call the MCP tool"""
        if arguments is None:
            arguments = {}
        
        result = await self.session.call_tool(tool_name, arguments)
        return result.content[0].text if result.content else ""
    
    async def disconnect(self):
        """Disconnect from the MCP server"""
        if self.session:
            await self.session.__aexit__(None, None, None)
        if hasattr(self, 'stdio_transport'):
            await self.stdio_transport.__aexit__(None, None, None)

# ====== 对话逻辑 ======
async def chat_with_bot(client: MCPClient, messages: list) -> str:
    """Chat with the bot using the MCP client"""
    # 这里简化处理：直接解析用户消息，调用相应的 MCP 工具
    # 实际使用时可以结合 LLM 来决定调用哪个工具
    
    last_message = messages[-1]["content"]
    print(last_message)
    
    # quick filter for common requests
    if "price" in last_message.lower() and "european option" in last_message.lower():
        result = await client.call_tool("price_european_option")
        return f"Price of the european option: {result}"
    elif "列出" in last_message and "pdf" in last_message:
        result = await client.call_tool("list_desktop_pdf_files")
        return result
    elif "读取" in last_message and "pdf" in last_message:
        # 尝试从消息中提取 PDF  
        import re
        match = re.search(r'["\']?([\w-]+\.pdf)["\']?', last_message)
        if match:
            filename = match.group(1)
            result = await client.call_tool("read_pdf_file", {"filename": filename})
            return result
        else:
            return "Please specify the asset name."
    else:
        return "I am an expert quantitative finance assistant can help on modeling, pricing, and risk management of financial instruments. Please let me know what you need help with."

# ====== Test mode ======
async def test(query='帮我统计桌面上的 pdf 文件数量'):
    """Test mode"""
    try:
        project_root = Path(__file__).resolve().parent.parent.parent
        server_script = str(project_root / "src" / "server" / "server.py")
        
        client = MCPClient(server_script)
        await client.connect()
        
        messages = [{"role": "system", "content": system_prompt}]
        messages.append({"role": "user", "content": query})
        
        print("Processing request...")
        response = await chat_with_bot(client, messages)
        print('bot response:', response)
        
        await client.disconnect()
    except Exception as e:
        print(f"Error: {str(e)}")

# ====== TUI mode ======
async def app_tui():
    """Command-line interface mode"""
    project_root = Path(__file__).resolve().parent.parent.parent
    server_script = str(project_root / "src" / "server" / "server.py")
    
    client = MCPClient(server_script)
    await client.connect()
    
    messages = [{"role": "system", "content": system_prompt}]
    
    while True:
        try:
            query = input('user question: ')
            if not query:
                print('user question cannot be empty!')
                continue
            
            messages.append({"role": "user", "content": query})
            print("Processing request...")
            response = await chat_with_bot(client, messages)
            print('bot response:', response)
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {str(e)}")
            print("Please try again.")    
    await client.disconnect()

# ====== GUI mode ======
def app_gui():
    """Web interface mode"""
    try:
        import gradio as gr

        project_root = Path(__file__).resolve().parent.parent.parent
        server_script = str(project_root / "src" / "server" / "server.py")
        
        client = MCPClient(server_script)
        
        async def respond(message, history):
            # Lazy client connection and disconnection
            await client.connect()
            try:
                messages = [{"role": "system", "content": system_prompt}]
                for h in history:
                    messages.append({"role": h["role"], "content": h["content"]})
                messages.append({"role": "user", "content": message})
                response = await chat_with_bot(client, messages)
                return {"role": "assistant", "content": response}
            finally:
                await client.disconnect()
        
        demo = gr.ChatInterface(
            fn=respond,
            title="QuantLib MCP Client",
            chatbot=gr.Chatbot(type="messages"),
            examples=[
                'Create an interest rate swap.',
                'Bootstrap an OIS curve.',
                'Price an european option.',
                'Price a callable bond.',
                'Explain Hull White calibration.',
                'Explain the difference between Bachelier and Black.',
                'Build a SABR surface.',
                'Generate a Heston example.',
            ],
        )
        demo.launch(share=True)
        
    except ImportError:
        print("gradio not installed. Please run: pip install gradio")
        import asyncio
        asyncio.run(app_tui())

# ====== MAIN ======
if __name__ == '__main__':
    # asyncio.run(test())           # test
    # asyncio.run(app_tui())        # CLI
    app_gui()                       # GUI
