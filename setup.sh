#!/usr/bin/env bash
# setup.sh – Create venv, install dependencies
set -e

PYTHON=${PYTHON:-python3}
VENV_DIR="venv"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   GeoLite2 API – Environment Setup           ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

$PYTHON -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ required'" \
  || { echo "❌  Python 3.10+ required."; exit 1; }

if [ ! -d "$VENV_DIR" ]; then
  echo "▸ Creating virtual environment..."
  $PYTHON -m venv "$VENV_DIR"
fi

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
  source "$VENV_DIR/Scripts/activate"
else
  source "$VENV_DIR/bin/activate"
fi

echo "▸ Upgrading pip..."
pip install --upgrade pip --quiet

echo "▸ Installing dependencies..."
pip install -r requirements.txt

echo "▸ Copying .env.example → .env (if not exists)..."
[ ! -f .env ] && cp .env.example .env && echo "  ✅ .env created. Edit it to set your config." || echo "  ℹ️  .env already exists."

echo ""
if [ -f "GeoLite2-City.mmdb" ]; then
  echo "  ✅  GeoLite2-City.mmdb found."
else
  echo "  ⚠️   GeoLite2-City.mmdb NOT found."
  echo "      Download it from: https://www.maxmind.com/en/geolite2/signup"
fi

echo ""
echo "══════════════════════════════════════════════"
echo "  Ready! To start the API:"
echo ""
echo "    source venv/bin/activate"
echo "    python run.py"
echo ""
echo "  Then open: http://localhost:8074/docs"
echo "══════════════════════════════════════════════"
echo ""
