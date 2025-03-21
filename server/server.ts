// auth.ts
import express from 'express';
import passport from 'passport';
import { Strategy as GoogleStrategy } from 'passport-google-oauth20';
import dotenv from 'dotenv';
import { findUserById, createUser, findUserByEmail } from './userDb';

// Load environment variables
dotenv.config();

const router = express.Router();

// Check if required environment variables are set
if (!process.env.GOOGLE_CLIENT_ID || !process.env.GOOGLE_CLIENT_SECRET) {
  console.error('Missing required environment variables for Google OAuth');
  process.exit(1);
}

// Configure Passport Google OAuth Strategy
passport.use(new GoogleStrategy({
  clientID: process.env.GOOGLE_CLIENT_ID,
  clientSecret: process.env.GOOGLE_CLIENT_SECRET,
  callbackURL: process.env.GOOGLE_CALLBACK_URL || 'http://localhost:3001/api/auth/google/callback',
  scope: ['profile', 'email']
}, async (accessToken, refreshToken, profile, done) => {
  try {
    // Find or create user
    const email = profile.emails?.[0]?.value;
    if (!email) {
      return done(new Error('No email found in Google profile'), null);
    }

    let user = await findUserByEmail(email);
    
    if (!user) {
      // Create new user
      user = await createUser({
        email,
        name: profile.displayName,
        googleId: profile.id,
        avatar: profile.photos?.[0]?.value
      });
    }
    
    return done(null, user);
  } catch (error) {
    return done(error, null);
  }
}));

// Serialize and deserialize user
passport.serializeUser((user, done) => {
  done(null, user.id);
});

passport.deserializeUser(async (id, done) => {
  try {
    const user = await findUserById(id);
    done(null, user);
  } catch (error) {
    done(error, null);
  }
});

// Auth routes
router.get('/google', passport.authenticate('google', { scope: ['profile', 'email'] }));

router.get('/google/callback',
  passport.authenticate('google', { 
    failureRedirect: process.env.CLIENT_URL ? `${process.env.CLIENT_URL}/login` : 'http://localhost:3000/login'
  }),
  (req, res) => {
    // Successful authentication
    res.redirect(process.env.CLIENT_URL || 'http://localhost:3000');
  }
);

// Get current user
router.get('/user', (req, res) => {
  if (req.isAuthenticated()) {
    res.json(req.user);
  } else {
    res.status(401).json({ error: 'Not authenticated' });
  }
});

// Logout
router.get('/logout', (req, res) => {
  req.logout((err) => {
    if (err) {
      return res.status(500).json({ error: 'Error during logout' });
    }
    res.redirect(process.env.CLIENT_URL || 'http://localhost:3000');
  });
});

export default router;