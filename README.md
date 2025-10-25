# Blender AI Simulation Generator

An AI-powered system that generates Blender simulations from natural language descriptions using Claude API and a multi-agent architecture.

## Features

- Natural Language Input: Describe your simulation in plain English
- Multi-Agent Pipeline: 7 specialized agents handle different aspects
- Real-time Progress: Server-Sent Events (SSE) for live updates
- Glassmorphism UI: Modern chat-based interface
- Physics Validation: Automatic physics property enrichment
- Quality Assurance: Automated quality scoring and validation

## Quick Start

1. Install dependencies: `pip install -r requirements.txt`
2. Set up `.env` file with your Claude API key
3. Run server: `python3 -m uvicorn web.main:app --host 127.0.0.1 --port 8000`
4. Open http://localhost:8000

## Known Issues

Currently has Blender 4.5 API compatibility issue with rigid body baking.
See GitHub issues for details and progress.

## License

MIT
