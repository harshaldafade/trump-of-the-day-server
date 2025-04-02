const express = require('express');
const session = require('express-session');
const passport = require('passport');
const cors = require('cors');
const dotenv = require('dotenv');
const authRouter = require('./auth'); // Make sure auth.ts uses `export = router`

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3001;

// ✅ CORS setup
app.use(cors({
  origin: process.env.CLIENT_URL, 
  credentials: true,
}));

// ✅ Body parsing
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// ✅ Session configuration
app.use(session({
  secret: 'your-secret-key', // ideally store this in process.env.SECRET
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: false, // true if using HTTPS in production
    httpOnly: true,
    maxAge: 1000 * 60 * 60 * 24, // 1 day
  },
}));

// ✅ Passport initialization
app.use(passport.initialize());
app.use(passport.session());

// ✅ Auth routes (make sure auth.ts exports with `export = router`)
app.use('/api/auth', authRouter);

// ✅ Health check route
app.get('/', (_req, res) => {
  res.send('🚀 Backend is running!');
});

// ✅ Start the server
app.listen(PORT, () => {
  console.log(`🚀 Server running on http://localhost:${PORT}`);
});
