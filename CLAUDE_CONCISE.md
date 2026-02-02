# CLAUDE.md

Oracle Financial Services Installation Agent - Development Guidelines

## Project Overview

Intelligent automation system for Oracle Financial Services products (OFSAA, Flexcube, etc.) with:
- **Backend**: Linux commands, conditional logic, and future AI agents
- **Frontend**: Next.js web interface for installation management and monitoring


## Architecture

**Backend**: Linux scripts with conditional logic → AI agents + command execution  
**Frontend**: Next.js 15+ with TypeScript for installation dashboard and control panel

### Directory Structure
```
installation_workspace/
├── backend/                           # Python FastAPI backend
│   ├── agents/                            # AI agent implementations
│   │ 
│   ├── core/                              # Core infrastructure
│   │  
│   │   
│   ├── routers/                           # FastAPIroutehandlers
│   │  
│   ├── services/                          # Business logic layer
│ 
│   ├── tests/                             # pytest test suite
│   │ 
│   ├── scripts/                           # Installation shell scripts
│   │   
│   ├── config/                            # Configuration files
│   │   
│   ├── logs/                              # Application logs
│   ├── pyproject.toml                     # UV project configuration
│   ├── requirements.txt                   # Dependencies (legacy)
│   └── main.py                            # FastAPI application entry point
├── frontend/                          # Next.js React frontend
│   ├── src/
│   │   ├── app/                               # Next.js App Router
│   │   │   
│   │   │  
│   │   ├── components/                        # Reusable React components
│   │   │   
│   │   ├── lib/                               # Utility functions
│   │   │   
│   │   └── styles/                            # CSS/Tailwind styles
│   ├── public/                            # Static assets
│   ├── package.json                       # Bun dependencies
│   ├── bun.lockb                          # Bun lock file
│   ├── next.config.js                     # Next.js configuration
│   ├── tailwind.config.js                 # Tailwind CSS config
│   └── tsconfig.json                      # TypeScript configuration
└── docs/                              # Project documentation
    ├── API.md                                 # API documentation
    ├── INSTALLATION.md                        # Installation guide
    └── DEVELOPMENT.md                         # Development guide
```

### Key Patterns
- **Product registry**: Dynamic product discovery and registration
- **Template system**: Extensible configuration templates
- **Dependency resolution**: Cross-product dependency management
- **Modular installation**: Product and module-based installation units
- **Validation pipeline**: Multi-stage validation (pre, during, post)
- **Command orchestration**: Secure Linux command execution with logging
- **Real-time dashboard**: Next.js interface for installation monitoring and control
- **API integration**: Backend-frontend communication via REST/WebSocket APIs

## Environment Variables

**Global**: `JAVA_HOME`, `ORACLE_HOME`, `OFS_HOME`, `TNS_ADMIN`, `PATH`  
**Product-specific**: `{PRODUCT}_HOME`, `PRODUCT_CONFIG_HOME`, `PRODUCT_LOG_HOME`

## Package Management

**Backend (UV)**:
```toml
# pyproject.toml
[project]
name = "ofsaa-installation-agent"
version = "1.0.0"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.104.1",
    "uvicorn[standard]>=0.24.0",
    "pydantic>=2.5.0",
    "sqlalchemy>=2.0.23",
    "pytest>=7.4.3",
    "ruff>=0.1.8"
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 88
target-version = "py313"
```

**Frontend (Bun)**:
```json
{
  "name": "ofsaa-frontend",
  "version": "1.0.0",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "^15.0.0",
    "react": "^19.0.0",
    "typescript": "^5.3.0",
    "tailwindcss": "^3.4.0"
  }
}
```

## Development Standards

### 1. Code Quality & Style

#### Python Style (Backend)
- Uses UV package manager (never pip)
- Python 3.13+ required
- Type hints throughout with Pydantic models
- Async/await for concurrency
- Pathlib for file operations
- Google-style docstrings

#### TypeScript Style (Frontend)
- Uses Bun package manager (never npm or pnpm)
- React 19 with TypeScript
- ESLint for linting
- Tailwind CSS for styling

#### Code Quality Tools
- **Ruff**: Comprehensive Python linting with 80+ rule categories
- **ESLint**: TypeScript/React linting with Next.js config
- **Pytest**: Async testing with fixtures, mocking, and HTTP response mocking

**Always write and run unit tests instead of executing scripts directly:**
- Write comprehensive unit tests for all new code and changes
- Use mock data and pytest fixtures to avoid side effects
- Test all edge cases, error scenarios, and validation logic
- Run `uv run pytest` to validate changes before implementation
- Never run actual Python scripts during development to avoid triggering unintended operations

**Shell Scripts (Installation Engine)**:
- POSIX-compliant, comprehensive error handling
- Structured logging with timestamps
- Input validation and sanitization

### 2. Architecture Principles
- **Modular**: Each product as separate installation unit
- **Extensible**: Easy addition of new products via registry system
- **Generic**: Product-agnostic core with product-specific extensions
- **Dependency-aware**: Cross-product dependency resolution
- **Real-time**: Live installation progress and status updates

### 3. Installation Safety
- Validate system prerequisites before execution
- Backup configurations before changes
- Implement rollback capabilities
- Use atomic operations with transaction-like behavior
- Web interface provides safe installation controls

### 4. Configuration Management
- Hierarchical configuration (global → product → module)
- Template-based generation with environment variable substitution
- Configuration validation before application
- Version control and rollback capability
- Web-based configuration editor and validator

## Installation Workflow

**Phase 1**: System analysis, product selection, prerequisites  
**Phase 2**: Configuration preparation, database setup, templates  
**Phase 3**: Product installation, modules, dependency resolution  
**Phase 4**: Validation, service startup, integration testing

## Current Features

**Backend Engine**:
- Multi-product support (OFSAA, Flexcube, etc.)
- Linux command orchestration with logging
- Cross-product dependency management  
- Template-based configuration system
- Error recovery and rollback capabilities
- System validation and prerequisite checking

**Frontend Interface**:
- Installation dashboard and progress monitoring
- Product selection and configuration management
- Real-time log viewing and system status
- Configuration editor with validation
- Installation history and reporting

## Future AI Features (Planned)

**Backend AI Agents**:
- Intelligent installation planning and optimization
- Automated troubleshooting and issue resolution
- Predictive maintenance and health monitoring
- Learning from installation patterns

**Frontend AI Integration**:
- Natural language installation interface
- AI-powered installation recommendations
- Intelligent error diagnosis with guided resolution
- Conversational installation assistant