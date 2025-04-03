import express, { json, urlencoded ,Request, Response, Application } from 'express';
import session from 'express-session';
import passport from 'passport';
import cors from 'cors';
import dotenv from 'dotenv';
import authRouter from './auth';

dotenv.config();

const app: Application = express();
const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 3001;

if (!process.env.CLIENT_URL || !process.env.SECRET) {
  console.error('❌ Missing required environment variables');
  process.exit(1);
}

// ✅ CORS setup
app.use(cors({
  origin: process.env.CLIENT_URL,
  credentials: true,
}));

// ✅ Body parsing
app.use(json());
app.use(urlencoded({ extended: true }));

// ✅ Session configuration
app.use(session({
  secret: process.env.SECRET,
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: process.env.NODE_ENV === 'production',
    httpOnly: true,
    maxAge: 1000 * 60 * 60 * 24,
  },
}));

// ✅ Passport initialization
app.use(passport.initialize());
app.use(passport.session());

// ✅ Auth routes
app.use('/api/auth', authRouter);

// ✅ Health check route
app.get('/', (_req: Request, res: Response) => {
  res.send('🚀 Backend is running!');
});

// ✅ Start the server
app.listen(PORT, () => {
  console.log(`🚀 Server running on http://localhost:${PORT}`);
});
