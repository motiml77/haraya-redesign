/**
 * Seed script - initializes Firebase with first users and content
 *
 * Usage: npx tsx scripts/seed-firestore.ts
 *
 * Requires: .env.local to be loaded (or set FIREBASE_SERVICE_ACCOUNT_KEY env var)
 */

import { initializeApp, cert } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { getFirestore } from 'firebase-admin/firestore';
import * as fs from 'fs';
import * as path from 'path';

// Load service account from file
const serviceAccountPath = path.join(__dirname, '..', 'rav-fudi-firebase-adminsdk.json');
const serviceAccount = JSON.parse(fs.readFileSync(serviceAccountPath, 'utf8'));

const app = initializeApp({
  credential: cert(serviceAccount),
});

const auth = getAuth(app);
const db = getFirestore(app);

const USERS = [
  { email: 'admin@ravfudi.com', password: 'Admin123!', role: 'admin', name: 'מנהל ראשי' },
  { email: 'editor@ravfudi.com', password: 'Editor123!', role: 'editor', name: 'עורך א׳' },
  { email: 'rabbi@ravfudi.com', password: 'Rabbi123!', role: 'rabbi', name: 'הרב המשיב' },
];

const CONTENT = {
  book: 'אורות הקודש',
  seder: 'חלק א׳',
  chapter: 'פרק א׳',
  paragraphTitle: 'חכמת הקודש',
  isEdited: false,
  originalText: 'חכמת הקודש היא למעלה מכל חכמה. היא אינה רק ידיעה שכלית, אלא חיות פנימית המאירה את כל חדרי הנפש.',
  tags: 'קודש, חכמה, אורות',
  commentary: [
    { id: 1, text: 'הפסקה מדברת על ההבדל בין חכמה רגילה לחכמת הקודש.' }
  ],
  comments: [],
  questionsForRabbi: []
};

async function seed() {
  console.log('Starting Firebase seed...\n');

  // Create users
  for (const user of USERS) {
    try {
      // Check if user already exists
      try {
        const existing = await auth.getUserByEmail(user.email);
        console.log(`User already exists: ${user.email} (${existing.uid})`);

        // Make sure Firestore doc exists
        await db.collection('users').doc(existing.uid).set({
          email: user.email,
          name: user.name,
          role: user.role,
        }, { merge: true });

        continue;
      } catch {
        // User doesn't exist, create it
      }

      const userRecord = await auth.createUser({
        email: user.email,
        password: user.password,
        displayName: user.name,
      });

      await db.collection('users').doc(userRecord.uid).set({
        email: user.email,
        name: user.name,
        role: user.role,
        createdAt: new Date().toISOString(),
      });

      console.log(`Created user: ${user.email} (${user.role}) - uid: ${userRecord.uid}`);
    } catch (error: any) {
      console.error(`Failed to create user ${user.email}:`, error.message);
    }
  }

  // Seed content
  try {
    const contentDoc = await db.doc('content/main').get();
    if (!contentDoc.exists) {
      await db.doc('content/main').set(CONTENT);
      console.log('\nContent seeded successfully');
    } else {
      console.log('\nContent already exists, skipping');
    }
  } catch (error: any) {
    console.error('Failed to seed content:', error.message);
  }

  // Seed analytics
  try {
    const analyticsDoc = await db.doc('analytics/general').get();
    if (!analyticsDoc.exists) {
      await db.doc('analytics/general').set({ visitors: 0 });
      console.log('Analytics initialized');
    } else {
      console.log('Analytics already exists, skipping');
    }
  } catch (error: any) {
    console.error('Failed to seed analytics:', error.message);
  }

  console.log('\n--- Seed complete ---');
  console.log('\nLogin credentials:');
  for (const user of USERS) {
    console.log(`  ${user.role}: ${user.email} / ${user.password}`);
  }

  process.exit(0);
}

seed().catch(console.error);
