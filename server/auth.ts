// auth.ts - OAuth Authentication API

import { Router } from 'express';
import passport from 'passport';
import { Strategy as GoogleStrategy } from 'passport-google-oauth20';
import { Strategy as FacebookStrategy } from 'passport-facebook';
import { Strategy as GithubStrategy } from 'passport-github2';
import jwt from 'jsonwebtoken';
import { createUser, findUserByEmail, findUserByProviderId } from './userDb';

const router = Router();

// Configure environment variables (in production, use a proper env management solution)
const JWT_SECRET = process.env.JWT_SECRET || 'your-jwt-secret';
const CLIENT_URL = process.env.CLIENT_URL || 'http://localhost:3000';

// OAuth provider configurations
const GOOGLE_CONFIG = {
  clientID: process.env.GOOGLE_CLIENT_ID || '',
  clientSecret: process.env.GOOGLE_CLIENT_SECRET || '',
  callbackURL: '/api/auth/google/callback'
};

const FACEBOOK_CONFIG = {
  clientID: process.env.FACEBOOK_CLIENT_ID || '',
  clientSecret: process.env.FACEBOOK_CLIENT_SECRET || '',
  callbackURL: '/api/auth/facebook/callback',
  profileFields: ['id', 'emails', 'name']
};

const GITHUB_CONFIG = {
  clientID: process.env.GITHUB_CLIENT_ID || '',
  clientSecret: process.env.GITHUB_CLIENT_SECRET || '',
  callbackURL: '/api/auth/github/callback'
};

// Passport serialize/deserialize
passport.serializeUser((user: any, done) => {
  done(null, user.id);
});

passport.deserializeUser(async (id: string, done) => {
  try {
    // Implement user lookup by ID from your database
    // const user = await findUserById(id);
    done(null, { id });
  } catch (error) {
    done(error, null);
  }
});

// Google Strategy
passport.use(new GoogleStrategy(GOOGLE_CONFIG, async (accessToken, refreshToken, profile, done) => {
  try {
    // Check if user already exists
    let user = await findUserByProviderId('google', profile.id);
    
    if (!user && profile.emails && profile.emails.length > 0) {
      // Check if user exists with this email
      user = await findUserByEmail(profile.emails[0].value);
    }
    
    if (!user) {
      // Create new user
      const email = profile.emails && profile.emails.length > 0 ? profile.emails[0].value : '';
      const username = profile.displayName || email.split('@')[0];
      
      user = await createUser({
        username,
        email,
        authProvider: 'google',
        providerId: profile.id
      });
    }
    
    return done(null, user);
  } catch (error) {
    return done(error as Error);
  }
}));

// Facebook Strategy
passport.use(new FacebookStrategy(FACEBOOK_CONFIG, async (accessToken, refreshToken, profile, done) => {
  try {
    // Check if user already exists
    let user = await findUserByProviderId('facebook', profile.id);
    
    if (!user && profile.emails && profile.emails.length > 0) {
      // Check if user exists with this email
      user = await findUserByEmail(profile.emails[0].value);
    }
    
    if (!user) {
      // Create new user
      const email = profile.emails && profile.emails.length > 0 ? profile.emails[0].value : '';
      const username = profile.displayName || email.split('@')[0];
      
      user = await createUser({
        username,
        email,
        authProvider: 'facebook',
        providerId: profile.id
      });
    }
    
    return done(null, user);
  } catch (error) {
    return done(error as Error);
  }
}));

// Github Strategy
passport.use(new GithubStrategy(GITHUB_CONFIG, async (accessToken, refreshToken, profile, done) => {
  try {
    // Check if user already exists
    let user = await findUserByProviderId('github', profile.id);
    
    if (!user && profile.emails && profile.emails.length > 0) {
      // Check if user exists with this email
      user = await findUserByEmail(profile.emails[0].value);
    }
    
    if (!user) {
      // Create new user
      const email = profile.emails && profile.emails.length > 0 ? profile.emails[0].value : '';
      const username = profile.username || profile.displayName || email.split('@')[0];
      
      user = await createUser({
        username,
        email,
        authProvider: 'github',
        providerId: profile.id
      });
    }
    
    return done(null, user);
  } catch (error) {
    return done(error as Error);
  }
}));

// Generate JWT token
const generateToken = (user: any) => {
  return jwt.sign(
    { 
      id: user.id,
      email: user.email,
      username: user.username
    }, 
    JWT_SECRET,
    { expiresIn: '7d' }
  );
};

// Auth routes
router.get('/google', passport.authenticate('google', { scope: ['profile', 'email'] }));
router.get('/facebook', passport.authenticate('facebook', { scope: ['email'] }));
router.get('/github', passport.authenticate('github', { scope: ['user:email'] }));

// Callback routes
const handleCallback = (req: any, res: any) => {
  const token = generateToken(req.user);
  res.redirect(`${CLIENT_URL}/auth/callback?token=${token}`);
};

router.get('/google/callback', 
  passport.authenticate('google', { failureRedirect: '/login', session: false }),
  handleCallback
);

router.get('/facebook/callback', 
  passport.authenticate('facebook', { failureRedirect: '/login', session: false }),
  handleCallback
);

router.get('/github/callback', 
  passport.authenticate('github', { failureRedirect: '/login', session: false }),
  handleCallback
);

// Get current user
router.get('/me', (req, res) => {
  const token = req.headers.authorization?.split(' ')[1];
  
  if (!token) {
    return res.status(401).json({ message: 'No token provided' });
  }
  
  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    res.json({ user: decoded });
  } catch (error) {
    res.status(401).json({ message: 'Invalid token' });
  }
});

// Logout
router.post('/logout', (req, res) => {
  req.logout();
  res.json({ success: true });
});

export default router;