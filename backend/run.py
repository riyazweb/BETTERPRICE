import os
from app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=True,
        reloader_type="stat",
        extra_files=[],
        exclude_patterns=[os.path.join(os.path.expanduser("~"), "AppData")],
    )
