# Proposed Database Schema

This schema is designed for a relational database (like PostgreSQL via Supabase) or a document database (like MongoDB or Firebase). The structure below is presented in a relational format for clarity.

## 1. Books (`books`)
Stores the top-level books by Rabbi Kook.
- `id` (UUID, Primary Key)
- `title` (String) - e.g., "Orot Kodesh"
- `description` (Text)
- `cover_image_url` (String)
- `created_at` (Timestamp)
- `updated_at` (Timestamp)

## 2. Orders / Sedarim (`orders`)
Subdivisions within a book.
- `id` (UUID, Primary Key)
- `book_id` (UUID, Foreign Key -> `books.id`)
- `title` (String) - e.g., "Seder Aleph"
- `order_index` (Integer) - For sorting
- `created_at` (Timestamp)

## 3. Chapters / Prakim (`chapters`)
Subdivisions within an order.
- `id` (UUID, Primary Key)
- `order_id` (UUID, Foreign Key -> `orders.id`)
- `title` (String) - e.g., "Perek Aleph"
- `chapter_index` (Integer) - For sorting
- `created_at` (Timestamp)

## 4. Paragraphs / Piskaot (`paragraphs`)
The core content unit containing Rabbi Kook's original text.
- `id` (UUID, Primary Key)
- `chapter_id` (UUID, Foreign Key -> `chapters.id`)
- `paragraph_index` (Integer) - For sorting
- `original_text` (Text) - The Hebrew text of the paragraph
- `created_at` (Timestamp)
- `updated_at` (Timestamp)

## 5. Commentaries (`commentaries`)
Detailed explanations and commentaries linked to a specific paragraph.
- `id` (UUID, Primary Key)
- `paragraph_id` (UUID, Foreign Key -> `paragraphs.id`)
- `author_id` (UUID, Foreign Key -> `users.id`) - The commentator
- `content` (Text) - The commentary text (can include rich text/markdown)
- `created_at` (Timestamp)
- `updated_at` (Timestamp)

## 6. Sources / Footnotes (`sources`)
References and sources linked to specific parts of the commentary or original text.
- `id` (UUID, Primary Key)
- `commentary_id` (UUID, Foreign Key -> `commentaries.id`, nullable)
- `paragraph_id` (UUID, Foreign Key -> `paragraphs.id`, nullable)
- `reference_text` (String) - e.g., "Talmud Bavli, Berakhot 5a"
- `url` (String, nullable) - Link to external source (e.g., Sefaria)
- `created_at` (Timestamp)

## 7. Tags / Topics (`tags`)
Topics for the Hashtags System.
- `id` (UUID, Primary Key)
- `name` (String, Unique) - e.g., "Tshuva", "Eretz Yisrael"
- `created_at` (Timestamp)

## 8. Paragraph Tags (`paragraph_tags`)
Many-to-many relationship between Paragraphs and Tags.
- `paragraph_id` (UUID, Foreign Key -> `paragraphs.id`)
- `tag_id` (UUID, Foreign Key -> `tags.id`)
- Primary Key (`paragraph_id`, `tag_id`)

## 9. Users (`users`)
Registered users, admins, and commentators.
- `id` (UUID, Primary Key)
- `name` (String)
- `email` (String, Unique)
- `role` (Enum: 'admin', 'editor', 'user')
- `created_at` (Timestamp)

## 10. Comments (`comments`)
User discussions and Q&A on paragraphs.
- `id` (UUID, Primary Key)
- `paragraph_id` (UUID, Foreign Key -> `paragraphs.id`)
- `user_id` (UUID, Foreign Key -> `users.id`)
- `parent_comment_id` (UUID, Foreign Key -> `comments.id`, nullable) - For nested replies
- `content` (Text)
- `created_at` (Timestamp)
- `updated_at` (Timestamp)
