/**
 * Migration script: moves content/main → hierarchical structure
 *
 * Usage: npx tsx scripts/migrate-to-hierarchy.ts
 */

import { initializeApp, cert } from 'firebase-admin/app';
import { getFirestore } from 'firebase-admin/firestore';
import * as fs from 'fs';
import * as path from 'path';

const serviceAccountPath = path.join(__dirname, '..', 'rav-fudi-firebase-adminsdk.json');
const serviceAccount = JSON.parse(fs.readFileSync(serviceAccountPath, 'utf8'));

const app = initializeApp({
  credential: cert(serviceAccount),
});

const db = getFirestore(app);

async function migrate() {
  console.log('Starting migration from content/main to hierarchy...\n');

  // Read existing content/main
  const contentDoc = await db.doc('content/main').get();
  if (!contentDoc.exists) {
    console.log('No content/main document found. Nothing to migrate.');
    process.exit(0);
  }

  const content = contentDoc.data()!;
  console.log('Found content/main:');
  console.log(`  Book: ${content.book}`);
  console.log(`  Seder: ${content.seder}`);
  console.log(`  Chapter: ${content.chapter}`);
  console.log(`  Paragraph: ${content.paragraphTitle}`);
  console.log(`  Commentary items: ${(content.commentary || []).length}`);
  console.log(`  Comments: ${(content.comments || []).length}`);
  console.log(`  Questions: ${(content.questionsForRabbi || []).length}`);

  // Step 1: Create book
  console.log('\n1. Creating book...');
  const bookRef = await db.collection('books').add({
    title: content.book || 'אורות הקודש',
    description: '',
    orderIndex: 0,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  });
  console.log(`   Book created: ${bookRef.id} (${content.book})`);

  // Step 2: Create seder (if exists)
  let sederRef: FirebaseFirestore.DocumentReference | null = null;
  if (content.seder) {
    console.log('2. Creating seder...');
    sederRef = await db.collection('sedarim').add({
      bookId: bookRef.id,
      title: content.seder,
      orderIndex: 0,
      createdAt: new Date().toISOString(),
    });
    console.log(`   Seder created: ${sederRef.id} (${content.seder})`);
  }

  // Step 3: Create chapter
  console.log('3. Creating chapter...');
  const chapterRef = await db.collection('chapters').add({
    bookId: bookRef.id,
    sederId: sederRef ? sederRef.id : null,
    title: content.chapter || 'פרק א׳',
    orderIndex: 0,
    createdAt: new Date().toISOString(),
  });
  console.log(`   Chapter created: ${chapterRef.id} (${content.chapter})`);

  // Step 4: Create paragraph with all content
  console.log('4. Creating paragraph...');

  // Convert tags from comma-separated string to array
  let tags: string[] = [];
  if (content.tags) {
    if (typeof content.tags === 'string') {
      tags = content.tags.split(',').map((t: string) => t.trim()).filter(Boolean);
    } else if (Array.isArray(content.tags)) {
      tags = content.tags;
    }
  }

  const paragraphRef = await db.collection('paragraphs').add({
    bookId: bookRef.id,
    sederId: sederRef ? sederRef.id : null,
    chapterId: chapterRef.id,
    title: content.paragraphTitle || 'פסקה א׳',
    originalText: content.originalText || '',
    isEdited: content.isEdited || false,
    tags,
    orderIndex: 0,
    bookTitle: content.book || 'אורות הקודש',
    chapterTitle: content.chapter || 'פרק א׳',
    commentary: content.commentary || [],
    comments: content.comments || [],
    questionsForRabbi: content.questionsForRabbi || [],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  });
  console.log(`   Paragraph created: ${paragraphRef.id} (${content.paragraphTitle})`);

  console.log('\n--- Migration complete ---');
  console.log('\nNew document IDs:');
  console.log(`  Book:      ${bookRef.id}`);
  if (sederRef) console.log(`  Seder:     ${sederRef.id}`);
  console.log(`  Chapter:   ${chapterRef.id}`);
  console.log(`  Paragraph: ${paragraphRef.id}`);

  process.exit(0);
}

migrate().catch(err => {
  console.error('Migration failed:', err);
  process.exit(1);
});
