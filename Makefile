# Science Animation System — Makefile
# ─────────────────────────────────────────────────────────────────────────────
# Common commands for development, setup, and running the system.
# Requires: Python 3.11+, Docker, FFMPEG installed on host.

.PHONY: setup setup-web setup-full install install-frontend build-rag validate-examples run run-web run-backend run-frontend test clean help

## ─── Setup ──────────────────────────────────────────────────────────────────

setup: install build-manim-image
	@echo ""
	@echo "✓ Setup complete!"
	@echo "  Next steps:"
	@echo "    1. Copy .env.example to .env and fill in your API keys"
	@echo "    2. Run: make validate-examples"
	@echo "    3. Run: make build-rag"
	@echo "    4. Run: make run"

setup-web: install install-frontend
	@if [ ! -f .env ]; then cp .env.example .env; echo "✓ Created .env from .env.example"; fi
	@echo ""
	@echo "✓ Web setup complete!"
	@echo "  Edit .env with your API keys, then run: make run-web"

setup-full: setup-web build-manim-image
	@echo ""
	@echo "✓ Full setup complete!"
	@echo "  Docker image is ready for Manim rendering."

install:
	@echo "Installing Python dependencies..."
	pip install -r requirements.txt

install-frontend:
	@echo "Installing frontend dependencies..."
	npm --prefix frontend install

build-manim-image:
	@echo "Building Manim Docker image..."
	docker build -f Dockerfile.manim -t manim-science-animation .
	@echo "✓ Manim image built: manim-science-animation"

## ─── RAG Knowledge Base ──────────────────────────────────────────────────────

validate-examples:
	@echo "Validating Manim examples via Docker rendering..."
	python rag/validate_examples.py
	@echo "✓ Validation complete. See rag/examples/validation_results.json"

build-rag:
	@echo "Building Manim RAG knowledge base..."
	python rag/build_index.py
	@echo "✓ RAG index built. Only validated examples are included."

build-rag-full:
	@echo "Validating examples AND building RAG index..."
	python rag/build_index.py --validate

rebuild-rag:
	@echo "Rebuilding RAG index from scratch..."
	python rag/build_index.py --rebuild --validate

## ─── Run ─────────────────────────────────────────────────────────────────────

run:
	@echo "Starting Streamlit HITL interface..."
	streamlit run app.py --server.port=8501

run-backend:
	@echo "Starting FastAPI backend at http://127.0.0.1:8000 ..."
	python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

run-frontend:
	@echo "Starting React frontend at http://127.0.0.1:5173 ..."
	npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173

run-web:
	@echo "Starting FastAPI backend + React frontend..."
	@echo "Frontend: http://127.0.0.1:5173"
	@echo "Backend:  http://127.0.0.1:8000"
	@trap 'kill 0' INT TERM EXIT; \
	python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000 & \
	npm --prefix frontend run dev -- --host 127.0.0.1 --port 5173 & \
	wait

run-headless:
	@echo "Usage: make run-headless TEXT='your article text here'"
	@echo "       make run-headless PDF=path/to/file.pdf"
	@echo "       make run-headless URL=https://example.com/article"
ifdef TEXT
	python main.py --text "$(TEXT)"
else ifdef PDF
	python main.py --pdf $(PDF)
else ifdef URL
	python main.py --url $(URL)
else
	@echo "Error: Specify TEXT, PDF, or URL variable."
	@exit 1
endif

## ─── Testing ─────────────────────────────────────────────────────────────────

test:
	@echo "Running test suite..."
	python -m pytest tests/ -v --tb=short

test-unit:
	@echo "Running unit tests only (no Docker/API required)..."
	python -m pytest tests/test_state.py tests/test_document_parser.py -v --tb=short

test-integration:
	@echo "Running integration tests (requires API keys and Docker)..."
	python -m pytest tests/ -v --tb=short -m integration

## ─── Cleanup ─────────────────────────────────────────────────────────────────

clean:
	@echo "Cleaning output directory..."
	rm -rf output/audio/ output/video/ output/final/ output/state.json
	mkdir -p output/audio output/video output/final
	@echo "✓ Output directory cleaned"

clean-rag:
	@echo "Removing RAG index..."
	rm -rf rag/chroma_db/
	@echo "✓ RAG index removed. Run 'make build-rag' to rebuild."

clean-all: clean clean-rag
	@echo "✓ Full cleanup complete"

## ─── Help ────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "Science Animation System — Available Commands"
	@echo "─────────────────────────────────────────────"
	@echo "  make setup              Full setup (install + build Docker image)"
	@echo "  make setup-web          Install backend/frontend deps and create .env"
	@echo "  make setup-full         Web setup + build Manim Docker image"
	@echo "  make install            Install Python dependencies"
	@echo "  make install-frontend   Install frontend dependencies"
	@echo "  make build-manim-image  Build Manim Docker rendering image"
	@echo ""
	@echo "  make validate-examples  Validate LLM-generated Manim examples"
	@echo "  make build-rag          Build RAG knowledge base (validated examples only)"
	@echo "  make build-rag-full     Validate + build RAG in one step"
	@echo "  make rebuild-rag        Force rebuild RAG from scratch"
	@echo ""
	@echo "  make run                Start Streamlit HITL interface (port 8501)"
	@echo "  make run-web            Start FastAPI + React frontend"
	@echo "  make run-backend        Start FastAPI backend only (port 8000)"
	@echo "  make run-frontend       Start React frontend only (port 5173)"
	@echo "  make run-headless TEXT='...'  Run pipeline headlessly"
	@echo ""
	@echo "  make test               Run full test suite"
	@echo "  make test-unit          Run unit tests only (no API/Docker needed)"
	@echo ""
	@echo "  make clean              Remove generated output files"
	@echo "  make clean-rag          Remove RAG index"
	@echo "  make clean-all          Full cleanup"
	@echo ""
