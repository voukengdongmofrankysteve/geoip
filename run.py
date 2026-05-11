"""
run.py – Start the GeoLite2 API server
Usage:
    python run.py
    python run.py --host 0.0.0.0 --port 8089 --reload
"""

import argparse
import sys
import uvicorn
from app.config import settings
from app.database import engine, Base


def parse_args():
    p = argparse.ArgumentParser(description="GeoLite2 IP Geolocation API Server")
    p.add_argument("--host",   default=settings.HOST,        help="Bind host")
    p.add_argument("--port",   default=settings.PORT, type=int, help="Bind port")
    p.add_argument("--reload", action="store_true",           help="Auto-reload on code change")
    p.add_argument("--workers", default=1, type=int,          help="Number of worker processes")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    # Initialize database before starting the server
    print("🔧 Initializing database...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Database initialized successfully!")
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        sys.exit(1)
    
    print(f"""
╔══════════════════════════════════════════════╗
║   GeoLite2 IP Geolocation API                ║
╠══════════════════════════════════════════════╣
║  URL      →  http://{args.host}:{args.port:<20} ║
║  Docs     →  http://{args.host}:{args.port}/docs{' ' * 15}║
║  Database →  {str(settings.DB_PATH):<35}║
╚══════════════════════════════════════════════╝
""")
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
    )
