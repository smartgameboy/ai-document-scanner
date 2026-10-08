import base64
import json
import sys
from pathlib import Path
import numpy as np
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROUTES = {".pdf": "read_pdf", ".csv": "read_csv", ".xlsx": "read_excel", ".docx": "read_docx"}

def chunk_units(units, size=1200, overlap=180):
    if not 0 <= overlap < size:
        raise ValueError("Overlap must be smaller than chunk size")
    chunks = []
    for item in units:
        text = item["text"].strip()
        for start in range(0, len(text), size-overlap):
            chunks.append({**item, "text": text[start:start+size]})
            if start+size >= len(text):
                break
    return chunks

class ManagerAgent:
    async def ingest(self, files):
        server = Path(__file__).with_name("mcp_server.py")
        params = StdioServerParameters(command=sys.executable, args=[str(server)])
        units, trace, errors = [], [], []
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                for filename, data in files:
                    tool = ROUTES.get(Path(filename).suffix.lower())
                    if tool is None:
                        errors.append(f"{filename}: unsupported format")
                        continue
                    try:
                        result = await session.call_tool(tool, {"filename": filename,
                            "content_base64": base64.b64encode(data).decode()})
                        if result.isError:
                            raise ValueError("Reader could not parse this file")
                        structured = result.structuredContent
                        if isinstance(structured, dict) and "result" in structured:
                            parsed = structured["result"]
                        else:
                            parsed = json.loads("".join(c.text for c in result.content if c.type == "text"))
                        nonempty = [u for u in parsed if u["text"].strip()]
                        if not nonempty:
                            raise ValueError("No text found; scanned PDFs require OCR")
                        units.extend(nonempty)
                        trace.append({"file": filename, "agent": tool, "units": len(nonempty)})
                    except Exception as exc:
                        errors.append(f"{filename}: {exc}")
        return chunk_units(units), trace, errors

class RAGIndex:
    def __init__(self, chunks, provider):
        if not chunks:
            raise ValueError("No extractable text")
        if len(chunks) > 3000:
            raise ValueError("Demo limit: 3,000 chunks. Upload fewer or smaller files.")
        self.chunks = chunks
        self.vectors = provider.embed([c["text"] for c in chunks])

    def retrieve(self, question, provider, k=5):
        query = provider.embed([question], query=True)[0]
        scores = self.vectors @ query
        ids = np.argsort(-scores)[:k]
        return [{**self.chunks[int(i)], "score": float(scores[i]), "citation": f"S{n}"}
                for n, i in enumerate(ids, 1)]

    def ask(self, question, provider, k=5):
        hits = self.retrieve(question, provider, k)
        evidence = "\n\n".join(f"[{h['citation']}] {h['source']} — {h['location']}\n{h['text']}" for h in hits)
        return provider.answer(question, evidence), hits
