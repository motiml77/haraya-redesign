# תוכנית מעבר ל-Firebase

## סקירה
מעבר מ-JSON files מקומיים ל-Firebase Auth + Firestore, תוך תיקון כל בעיות האבטחה שזוהו.

## קבצים חדשים ליצירה

### 1. `lib/firebase.ts` - Firebase Client SDK
- אתחול Firebase app עם ה-config
- ייצוא `auth` (Firebase Auth) ו-`db` (Firestore)

### 2. `lib/firebase-admin.ts` - Firebase Admin SDK (שרת)
- אתחול עם Service Account
- ייצוא `adminAuth` ו-`adminDb`
- פונקציית עזר `verifyAuth(request)` - מוציאה token מה-header ומוודאת אותו

### 3. `.env.local` - משתני סביבה
- `NEXT_PUBLIC_FIREBASE_API_KEY`
- `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN`
- `NEXT_PUBLIC_FIREBASE_PROJECT_ID`
- `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET`
- `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID`
- `NEXT_PUBLIC_FIREBASE_APP_ID`
- `FIREBASE_SERVICE_ACCOUNT_KEY` (JSON string של ה-service account)

### 4. `scripts/seed-firestore.ts` - סקריפט לאתחול נתונים
- יוצר את המשתמשים הראשוניים ב-Firebase Auth עם סיסמאות חזקות
- מעלה את התוכן הקיים ל-Firestore
- מאתחל analytics

## קבצים קיימים לעדכון

### 5. `.gitignore` - הוספות
- `rav-fudi-firebase-adminsdk.json` (קובץ service account)

### 6. `app/api/auth/route.ts` - שכתוב מלא
- **לפני:** השוואת plaintext מול JSON file
- **אחרי:** Firebase Auth sign-in בצד שרת
  - POST: מקבל email+password, מחזיר custom token
  - מסיר את כל ה-hardcoded users
  - מסיר את ה-demo users מה-UI

### 7. `app/api/users/route.ts` - שכתוב מלא
- **לפני:** קריאה/כתיבה ל-JSON ללא הגנה
- **אחרי:**
  - GET: בודק שהמשתמש מחובר (verifyAuth), קורא מ-Firestore
  - POST: בודק שהמשתמש הוא admin, יוצר user ב-Firebase Auth + שומר role ב-Firestore

### 8. `app/api/content/route.ts` - שכתוב מלא
- **לפני:** קריאה/כתיבה ל-JSON ללא הגנה
- **אחרי:**
  - GET: קורא מ-Firestore (ציבורי)
  - POST: בודק שהמשתמש מחובר ושהוא admin/editor (verifyAuth + role check)

### 9. `app/api/analytics/route.ts` - שכתוב מלא
- **לפני:** קריאה/כתיבה ל-JSON
- **אחרי:** Firestore document `analytics/general` עם `FieldValue.increment(1)`

### 10. `app/admin/page.tsx` - עדכונים
- הוספת Firebase Auth client-side (signInWithEmailAndPassword)
- שמירת ה-ID token ושליחתו בכל request כ-Authorization header
- הסרת demo users מה-UI
- הוספת persistent login (onAuthStateChanged)
- logout אמיתי עם `signOut()`

### 11. `app/page.tsx` - עדכון קטן
- שינוי ה-DB status indicator מ"Local DB" (אדום) ל"Firebase" (ירוק)
- שליחת comment דרך API עם validation

### 12. `app/layout.tsx` - ללא שינוי

## מבנה Firestore

```
users/{uid}
  ├── email: string
  ├── name: string
  ├── role: "admin" | "editor" | "rabbi"

content/main
  ├── book: string
  ├── seder: string
  ├── chapter: string
  ├── paragraphTitle: string
  ├── isEdited: boolean
  ├── originalText: string
  ├── tags: string
  ├── commentary: array
  ├── comments: array
  ├── questionsForRabbi: array

analytics/general
  ├── visitors: number
```

## סדר ביצוע
1. התקנת חבילות + הגדרת environment
2. יצירת lib/firebase.ts + lib/firebase-admin.ts
3. עדכון כל 4 ה-API routes
4. עדכון admin page (login + token)
5. עדכון page.tsx (indicator)
6. סקריפט seed + יצירת משתמשים ראשוניים
7. בדיקה
