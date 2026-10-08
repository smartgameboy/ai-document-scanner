"""Private stdio server: file content is passed directly, no arbitrary paths."""
from mcp.server.fastmcp import FastMCP
from readers import decode, PDFReaderAgent, CSVReaderAgent, ExcelReaderAgent, WordReaderAgent

mcp = FastMCP("AI Document Scanner")

@mcp.tool()
def read_pdf(filename: str, content_base64: str) -> list[dict]:
    """Extract PDF text with page references."""
    return PDFReaderAgent().read(filename, decode(content_base64))

@mcp.tool()
def read_csv(filename: str, content_base64: str) -> list[dict]:
    """Extract UTF-8 CSV records with column labels."""
    return CSVReaderAgent().read(filename, decode(content_base64))

@mcp.tool()
def read_excel(filename: str, content_base64: str) -> list[dict]:
    """Extract XLSX sheet rows with column labels."""
    return ExcelReaderAgent().read(filename, decode(content_base64))

@mcp.tool()
def read_docx(filename: str, content_base64: str) -> list[dict]:
    """Extract Word paragraphs and table rows."""
    return WordReaderAgent().read(filename, decode(content_base64))

if __name__ == "__main__":
    mcp.run(transport="stdio")
