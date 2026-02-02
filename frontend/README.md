# OFSAA Installation Frontend

Modern Next.js frontend for Oracle Financial Services installation automation.

## Features

- **Distinctive Design**: Tokyo Night themed interface with IBM Plex Mono typography
- **Modern Stack**: Next.js 15 with TypeScript and Framer Motion animations  
- **Responsive**: Mobile-first design with elegant interactions
- **Real-time Status**: Connection monitoring and installation progress

## Quick Start

### Option 1: Use the start script (Windows)
```bash
# Double-click or run
start.bat
```

### Option 2: Manual commands
```bash
# Install dependencies
bun install

# Start development server
bun dev

# Build for production
bun run build
bun start
```

### Option 3: Using npm (if bun is not available)
```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
npm start
```

## Getting Started

1. **Start the Backend** (in another terminal):
   ```bash
   cd ../backend
   .venv\Scripts\activate
   python main.py
   ```

2. **Start the Frontend**:
   ```bash
   cd frontend
   bun install
   bun dev
   ```

3. **Access the Application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

## Design System

- **Typography**: IBM Plex Mono (300, 400, 700 weights)
- **Color Palette**: Tokyo Night theme with cyan/amber accents
- **Animation**: Framer Motion with staggered reveals and micro-interactions
- **Components**: Modular React components with TypeScript

## Project Structure

```
src/
├── app/                    # Next.js App Router
│   ├── globals.css         # Global styles
│   ├── layout.tsx          # Root layout
│   └── page.tsx            # Home page
├── components/             # React components
│   ├── BackgroundMatrix.tsx
│   └── InstallationForm.tsx
└── lib/                    # Utilities (future)
```

## API Integration

The frontend communicates with the FastAPI backend to:
- Submit installation credentials (host, username, password)
- Start installation processes
- Poll real-time status updates
- Display progress and logs

## Troubleshooting

**Port conflicts**: If port 3000 is in use, Next.js will automatically use the next available port.

**Backend connection**: Ensure the backend is running on port 8000 before submitting forms.

**Dependencies**: If bun is not installed, you can use npm/yarn instead.