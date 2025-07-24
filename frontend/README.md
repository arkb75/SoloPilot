# Frontend Applications

This directory contains all frontend applications for the SoloPilot platform.

## Applications

### email-intake/
React-based dashboard for monitoring and managing email conversations with clients.

**Features:**
- Real-time conversation tracking
- Manual/automatic response modes
- Proposal generation and preview
- Integration with AWS Lambda backend

**Tech Stack:**
- React 18 with TypeScript
- Vite for fast development
- Tailwind CSS for styling
- React Query for data fetching

**Development:**
```bash
cd frontend/email-intake
npm install
npm run dev  # Start dev server on http://localhost:5173
```

## Future Applications

### client-portal/ (Planned)
- Client login and project tracking
- Progress updates and milestones
- File uploads and feedback

### portfolio-site/ (Planned)
- Auto-generated from completed projects
- Case studies and testimonials
- Lead capture forms

## Shared Components

Common UI components and utilities will be extracted to:
- `frontend/shared/components/`
- `frontend/shared/utils/`

## Deployment

Frontend apps are deployed to:
- **Development**: Vercel preview deployments
- **Production**: Custom domains via Vercel/Netlify

## Contributing

1. Follow React best practices
2. Use TypeScript for type safety
3. Write unit tests for components
4. Ensure accessibility (WCAG 2.1 AA)
5. Mobile-first responsive design
