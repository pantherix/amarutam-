import json
import os
import sys

# Ensure src/ is in the PYTHONPATH
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.app.main import app

def generate():
    openapi_schema = app.openapi()
    os.makedirs("docs", exist_ok=True)
    with open("docs/openapi.json", "w") as f:
        json.dump(openapi_schema, f, indent=2)
    print("OpenAPI schema generated successfully at docs/openapi.json")

if __name__ == "__main__":
    generate()
